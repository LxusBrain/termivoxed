/**
 * TermiVoxed Cloud Functions
 *
 * Firebase Cloud Functions for:
 * - License verification and management
 * - Device registration and enforcement
 * - Stripe payment webhook handling
 * - Subscription lifecycle management
 * - Usage tracking and limits
 * - Fraud detection
 */

const functions = require("firebase-functions");
const admin = require("firebase-admin");
const stripe = require("stripe");
const jwt = require("jsonwebtoken");
const { v4: uuidv4 } = require("uuid");

// Initialize Firebase Admin
admin.initializeApp();
const db = admin.firestore();

// ============================================================
// SECURE CONFIGURATION - No hardcoded secrets
// ============================================================

// Initialize Stripe (MUST be configured in Firebase config)
const stripeSecretKey = functions.config().stripe?.secret_key;
if (!stripeSecretKey) {
  const errorMessage = "CRITICAL: Stripe secret key not configured! Run: firebase functions:config:set stripe.secret_key='sk_...'";
  console.error(errorMessage);
  // SECURITY: Throw error to prevent running without Stripe configuration
  throw new Error(errorMessage);
}
const stripeClient = stripe(stripeSecretKey);

// JWT Secret for license tokens (MUST be configured)
const JWT_SECRET = functions.config().jwt?.secret;
if (!JWT_SECRET) {
  const errorMessage = "CRITICAL: JWT secret not configured! Run: firebase functions:config:set jwt.secret='your-256-bit-secret'";
  console.error(errorMessage);
  // SECURITY: Throw error to prevent running without proper JWT configuration
  throw new Error(errorMessage);
}

// ============================================================
// INPUT VALIDATION HELPERS
// ============================================================

/**
 * Validate device fingerprint format
 * Must be exactly 32 hex characters
 */
function validateDeviceFingerprint(fingerprint) {
  if (!fingerprint) return { valid: false, error: "Device fingerprint is required" };
  if (typeof fingerprint !== "string") return { valid: false, error: "Device fingerprint must be a string" };
  if (fingerprint.length !== 32) return { valid: false, error: "Device fingerprint must be 32 characters" };
  if (!/^[a-f0-9]+$/i.test(fingerprint)) return { valid: false, error: "Device fingerprint must be hexadecimal" };
  return { valid: true };
}

/**
 * Validate app version format (semver)
 */
function validateAppVersion(version) {
  if (!version) return { valid: true }; // Optional
  if (typeof version !== "string") return { valid: false, error: "App version must be a string" };
  if (!/^\d+\.\d+\.\d+(-[a-zA-Z0-9.]+)?$/.test(version)) {
    return { valid: false, error: "App version must be in semver format (e.g., 1.0.0)" };
  }
  return { valid: true };
}

/**
 * Validate subscription tier
 */
function validateTier(tier) {
  const validTiers = ["FREE_TRIAL", "BASIC", "PRO", "ENTERPRISE", "LIFETIME"];
  if (!tier) return { valid: false, error: "Tier is required" };
  if (!validTiers.includes(tier)) {
    return { valid: false, error: `Invalid tier. Must be one of: ${validTiers.join(", ")}` };
  }
  return { valid: true };
}

/**
 * Validate billing cycle
 */
function validateBillingCycle(cycle) {
  if (!cycle) return { valid: true }; // Optional, defaults to monthly
  const validCycles = ["monthly", "yearly"];
  if (!validCycles.includes(cycle)) {
    return { valid: false, error: "Billing cycle must be 'monthly' or 'yearly'" };
  }
  return { valid: true };
}

/**
 * Sanitize string input (prevent injection)
 */
function sanitizeString(str, maxLength = 255) {
  if (!str) return "";
  if (typeof str !== "string") return "";
  // Remove control characters and limit length
  return str.replace(/[\x00-\x1F\x7F]/g, "").substring(0, maxLength);
}

// ============================================================
// RATE LIMITING
// ============================================================

/**
 * Check rate limit for a user/action combination
 * Uses Firestore to track request counts
 *
 * @param {string} userId - User ID or IP address
 * @param {string} action - Action being rate limited
 * @param {number} maxRequests - Maximum requests allowed
 * @param {number} windowSeconds - Time window in seconds
 * @returns {Promise<{allowed: boolean, remaining: number, resetAt: Date}>}
 */
async function checkRateLimit(userId, action, maxRequests, windowSeconds) {
  const now = Date.now();
  const windowStart = now - windowSeconds * 1000;
  const rateLimitId = `${userId}_${action}`;

  const rateLimitRef = db.collection("rate_limits").doc(rateLimitId);

  try {
    const result = await db.runTransaction(async (transaction) => {
      const doc = await transaction.get(rateLimitRef);

      let requests = [];
      if (doc.exists) {
        // Filter out old requests outside the window
        requests = (doc.data().requests || []).filter((t) => t > windowStart);
      }

      if (requests.length >= maxRequests) {
        const oldestRequest = Math.min(...requests);
        const resetAt = new Date(oldestRequest + windowSeconds * 1000);
        return {
          allowed: false,
          remaining: 0,
          resetAt: resetAt,
          retryAfter: Math.ceil((resetAt.getTime() - now) / 1000),
        };
      }

      // Add current request
      requests.push(now);
      transaction.set(rateLimitRef, { requests, updatedAt: admin.firestore.FieldValue.serverTimestamp() });

      return {
        allowed: true,
        remaining: maxRequests - requests.length,
        resetAt: new Date(now + windowSeconds * 1000),
      };
    });

    return result;
  } catch (error) {
    console.error("Rate limit check failed:", error);
    // Fail open - allow request if rate limiting fails
    return { allowed: true, remaining: maxRequests, resetAt: new Date() };
  }
}

/**
 * Rate limit configuration per action
 */
const RATE_LIMITS = {
  verifyLicense: { maxRequests: 60, windowSeconds: 60 }, // 60/minute
  createCheckoutSession: { maxRequests: 10, windowSeconds: 60 }, // 10/minute
  forceLogoutDevice: { maxRequests: 10, windowSeconds: 300 }, // 10/5 minutes
  trackUsage: { maxRequests: 100, windowSeconds: 60 }, // 100/minute
  getDevices: { maxRequests: 30, windowSeconds: 60 }, // 30/minute
};

/**
 * Apply rate limiting to a function
 */
async function applyRateLimit(context, action) {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const limits = RATE_LIMITS[action];
  if (!limits) return; // No rate limit configured

  const result = await checkRateLimit(context.auth.uid, action, limits.maxRequests, limits.windowSeconds);

  if (!result.allowed) {
    throw new functions.https.HttpsError(
      "resource-exhausted",
      `Rate limit exceeded. Try again in ${result.retryAfter} seconds.`,
      { retryAfter: result.retryAfter, resetAt: result.resetAt.toISOString() }
    );
  }
}

// ============================================================
// SECURITY HELPERS
// ============================================================

/**
 * Log security event for audit trail
 */
async function logSecurityEvent(userId, eventType, details) {
  try {
    await db.collection("security_logs").add({
      userId: userId || "anonymous",
      eventType: eventType,
      details: details,
      timestamp: admin.firestore.FieldValue.serverTimestamp(),
      ip: details.ip || null, // Would need to extract from request
    });
  } catch (error) {
    console.error("Failed to log security event:", error);
  }
}

/**
 * Clean up old rate limit entries (run periodically)
 */
exports.cleanupRateLimits = functions.pubsub.schedule("every 1 hours").onRun(async (context) => {
  const cutoff = Date.now() - 24 * 60 * 60 * 1000; // 24 hours ago

  const oldEntries = await db.collection("rate_limits").where("updatedAt", "<", new Date(cutoff)).limit(500).get();

  if (oldEntries.empty) return;

  const batch = db.batch();
  oldEntries.forEach((doc) => batch.delete(doc.ref));
  await batch.commit();

  console.log(`Cleaned up ${oldEntries.size} old rate limit entries`);
});

// Subscription tier configurations
const TIER_CONFIG = {
  FREE_TRIAL: {
    maxDevices: 1,
    maxExportsPerMonth: 2,
    maxTtsMinutesPerMonth: 10,
    maxAiGenerationsPerMonth: 3,
    maxVideoDurationMinutes: 5,
    features: {
      basic_export: true,
      multi_video_projects: true,
      advanced_tts_voices: true,
      export_4k: true,
      batch_export: true,
      custom_subtitle_styles: true,
      cross_video_segments: true,
      priority_support: false,
    },
  },
  BASIC: {
    maxDevices: 1,
    maxExportsPerMonth: 10,
    maxTtsMinutesPerMonth: 60,
    maxAiGenerationsPerMonth: 20,
    maxVideoDurationMinutes: 30,
    features: {
      basic_export: true,
      multi_video_projects: true,
      advanced_tts_voices: false,
      export_4k: false,
      batch_export: false,
      custom_subtitle_styles: true,
      cross_video_segments: false,
      priority_support: false,
    },
  },
  PRO: {
    maxDevices: 3,
    maxExportsPerMonth: -1, // Unlimited
    maxTtsMinutesPerMonth: -1,
    maxAiGenerationsPerMonth: -1,
    maxVideoDurationMinutes: -1,
    features: {
      basic_export: true,
      multi_video_projects: true,
      advanced_tts_voices: true,
      export_4k: true,
      batch_export: true,
      custom_subtitle_styles: true,
      cross_video_segments: true,
      priority_support: true,
    },
  },
  ENTERPRISE: {
    maxDevices: -1, // Unlimited
    maxExportsPerMonth: -1,
    maxTtsMinutesPerMonth: -1,
    maxAiGenerationsPerMonth: -1,
    maxVideoDurationMinutes: -1,
    features: {
      basic_export: true,
      multi_video_projects: true,
      advanced_tts_voices: true,
      export_4k: true,
      batch_export: true,
      custom_subtitle_styles: true,
      cross_video_segments: true,
      priority_support: true,
      sso_saml: true,
      admin_dashboard: true,
      api_access: true,
    },
  },
  LIFETIME: {
    maxDevices: 3,
    maxExportsPerMonth: -1,
    maxTtsMinutesPerMonth: -1,
    maxAiGenerationsPerMonth: -1,
    maxVideoDurationMinutes: -1,
    features: {
      basic_export: true,
      multi_video_projects: true,
      advanced_tts_voices: true,
      export_4k: true,
      batch_export: true,
      custom_subtitle_styles: true,
      cross_video_segments: true,
      priority_support: true,
    },
  },
};

// Stripe Price IDs (configure in Firebase config)
const STRIPE_PRICES = {
  BASIC: {
    monthly: functions.config().stripe?.basic_monthly || "price_basic_monthly",
    yearly: functions.config().stripe?.basic_yearly || "price_basic_yearly",
  },
  PRO: {
    monthly: functions.config().stripe?.pro_monthly || "price_pro_monthly",
    yearly: functions.config().stripe?.pro_yearly || "price_pro_yearly",
  },
  ENTERPRISE: {
    monthly: functions.config().stripe?.enterprise_monthly || "price_enterprise_monthly",
  },
  LIFETIME: {
    onetime: functions.config().stripe?.lifetime || "price_lifetime",
  },
};

// ============================================================
// AUTHENTICATION TRIGGERS
// ============================================================

/**
 * On user creation - set up initial subscription and trial
 */
exports.onUserCreated = functions.auth.user().onCreate(async (user) => {
  const userId = user.uid;
  const email = user.email;

  console.log(`New user created: ${userId} (${email})`);

  // Create user document
  await db.collection("users").doc(userId).set({
    email: email,
    displayName: user.displayName || email.split("@")[0],
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    emailVerified: user.emailVerified,
    phoneVerified: false,
    referralCode: generateReferralCode(),
    metadata: {
      signUpSource: "app",
      appVersion: "1.0.0",
    },
  });

  // Create FREE_TRIAL subscription
  const trialEndDate = new Date();
  trialEndDate.setDate(trialEndDate.getDate() + 7); // 7-day trial

  await db.collection("subscriptions").doc(userId).set({
    tier: "FREE_TRIAL",
    status: "ACTIVE",
    trialEndsAt: admin.firestore.Timestamp.fromDate(trialEndDate),
    currentPeriodStart: admin.firestore.FieldValue.serverTimestamp(),
    currentPeriodEnd: admin.firestore.Timestamp.fromDate(trialEndDate),
    maxDevices: TIER_CONFIG.FREE_TRIAL.maxDevices,
    activeDeviceCount: 0,
    features: TIER_CONFIG.FREE_TRIAL.features,
    usageLimits: {
      maxExportsPerMonth: TIER_CONFIG.FREE_TRIAL.maxExportsPerMonth,
      maxTtsMinutesPerMonth: TIER_CONFIG.FREE_TRIAL.maxTtsMinutesPerMonth,
      maxAiGenerationsPerMonth: TIER_CONFIG.FREE_TRIAL.maxAiGenerationsPerMonth,
      maxVideoDurationMinutes: TIER_CONFIG.FREE_TRIAL.maxVideoDurationMinutes,
    },
    usageThisMonth: {
      exportsCount: 0,
      ttsMinutes: 0,
      aiGenerations: 0,
    },
    history: [
      {
        action: "TRIAL_STARTED",
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
        details: { tier: "FREE_TRIAL", duration: 7 },
      },
    ],
  });

  console.log(`Trial subscription created for user: ${userId}`);
});

/**
 * On user deletion - clean up all user data
 */
exports.onUserDeleted = functions.auth.user().onDelete(async (user) => {
  const userId = user.uid;

  console.log(`User deleted: ${userId}`);

  // Delete user documents
  await db.collection("users").doc(userId).delete();
  await db.collection("subscriptions").doc(userId).delete();

  // Delete all devices for this user
  const devices = await db.collection("devices").where("userId", "==", userId).get();
  const batch = db.batch();
  devices.forEach((doc) => batch.delete(doc.ref));
  await batch.commit();

  // Delete sessions
  const sessions = await db.collection("sessions").where("userId", "==", userId).get();
  const sessionBatch = db.batch();
  sessions.forEach((doc) => sessionBatch.delete(doc.ref));
  await sessionBatch.commit();

  console.log(`Cleaned up data for deleted user: ${userId}`);
});

// ============================================================
// LICENSE VERIFICATION
// ============================================================

/**
 * Verify license and device - called on every app launch and periodically
 */
exports.verifyLicense = functions.https.onCall(async (data, context) => {
  // Require authentication
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  // Apply rate limiting
  await applyRateLimit(context, "verifyLicense");

  // Validate inputs
  const { deviceFingerprint, appVersion, currentToken } = data;

  const fingerprintValidation = validateDeviceFingerprint(deviceFingerprint);
  if (!fingerprintValidation.valid) {
    await logSecurityEvent(userId, "INVALID_FINGERPRINT", {
      error: fingerprintValidation.error,
      providedLength: deviceFingerprint?.length,
    });
    throw new functions.https.HttpsError("invalid-argument", fingerprintValidation.error);
  }

  const versionValidation = validateAppVersion(appVersion);
  if (!versionValidation.valid) {
    throw new functions.https.HttpsError("invalid-argument", versionValidation.error);
  }

  // Get subscription
  const subDoc = await db.collection("subscriptions").doc(userId).get();

  if (!subDoc.exists) {
    return {
      status: "NO_SUBSCRIPTION",
      message: "No subscription found",
    };
  }

  const subscription = subDoc.data();

  // Check subscription status
  if (subscription.status === "EXPIRED") {
    return {
      status: "EXPIRED",
      message: "Subscription has expired",
      renewUrl: `${functions.config().app?.url || "https://app.termivoxed.com"}/renew`,
    };
  }

  if (subscription.status === "CANCELLED") {
    // Check if still within paid period
    const periodEnd = subscription.currentPeriodEnd?.toDate();
    if (periodEnd && new Date() < periodEnd) {
      // Still valid until period end
    } else {
      return {
        status: "CANCELLED",
        message: "Subscription was cancelled",
      };
    }
  }

  // Check trial expiry
  if (subscription.tier === "FREE_TRIAL") {
    const trialEnd = subscription.trialEndsAt?.toDate();
    if (trialEnd && new Date() > trialEnd) {
      // Update to expired
      await db.collection("subscriptions").doc(userId).update({
        status: "EXPIRED",
      });

      return {
        status: "TRIAL_EXPIRED",
        message: "Free trial has expired",
        upgradeUrl: `${functions.config().app?.url || "https://app.termivoxed.com"}/upgrade`,
      };
    }
  }

  // Verify device
  const deviceId = hashFingerprint(deviceFingerprint);
  const deviceDoc = await db.collection("devices").doc(deviceId).get();

  if (deviceDoc.exists) {
    const device = deviceDoc.data();

    // Check if device belongs to this user
    if (device.userId !== userId) {
      return {
        status: "DEVICE_CONFLICT",
        message: "This device is registered to another account",
      };
    }

    // Check if device is active
    if (!device.isActive) {
      return {
        status: "DEVICE_DEACTIVATED",
        message: device.deactivationReason || "Device was deactivated",
      };
    }

    // Update last seen
    await db.collection("devices").doc(deviceId).update({
      lastSeen: admin.firestore.FieldValue.serverTimestamp(),
      appVersion: appVersion || device.appVersion,
    });
  } else {
    // New device - check device limit
    const maxDevices = subscription.maxDevices;
    const activeDeviceCount = subscription.activeDeviceCount || 0;

    if (maxDevices !== -1 && activeDeviceCount >= maxDevices) {
      // Get list of active devices
      const activeDevices = await db
        .collection("devices")
        .where("userId", "==", userId)
        .where("isActive", "==", true)
        .get();

      const deviceList = activeDevices.docs.map((d) => ({
        deviceId: d.id,
        deviceName: d.data().deviceName,
        lastSeen: d.data().lastSeen?.toDate().toISOString(),
        deviceType: d.data().deviceType,
      }));

      return {
        status: "DEVICE_LIMIT_EXCEEDED",
        message: `Maximum ${maxDevices} device(s) allowed`,
        activeDevices: deviceList,
        maxDevices: maxDevices,
      };
    }

    // Register new device
    await registerDevice(userId, deviceId, deviceFingerprint, data);
  }

  // Generate license token
  const token = generateLicenseToken(userId, deviceId, subscription);

  return {
    status: "VALID",
    token: token,
    subscription: {
      tier: subscription.tier,
      status: subscription.status,
      features: subscription.features,
      usageLimits: subscription.usageLimits,
      usageThisMonth: subscription.usageThisMonth,
      periodEnd: subscription.currentPeriodEnd?.toDate().toISOString(),
      trialEndsAt: subscription.trialEndsAt?.toDate().toISOString(),
    },
    device: {
      deviceId: deviceId,
      isNewDevice: !deviceDoc.exists,
    },
  };
});

/**
 * Force logout other devices (when device limit exceeded)
 */
exports.forceLogoutDevice = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  // Apply rate limiting (stricter - 10 per 5 minutes)
  await applyRateLimit(context, "forceLogoutDevice");

  const { deviceIdToLogout } = data;

  // Validate device ID format (should be 32 char hex hash)
  if (!deviceIdToLogout || typeof deviceIdToLogout !== "string") {
    throw new functions.https.HttpsError("invalid-argument", "Device ID required");
  }

  if (deviceIdToLogout.length !== 32 || !/^[a-f0-9]+$/i.test(deviceIdToLogout)) {
    throw new functions.https.HttpsError("invalid-argument", "Invalid device ID format");
  }

  // Log security event
  await logSecurityEvent(userId, "FORCE_LOGOUT_ATTEMPT", { targetDevice: deviceIdToLogout });

  // Verify device belongs to user
  const deviceDoc = await db.collection("devices").doc(deviceIdToLogout).get();

  if (!deviceDoc.exists || deviceDoc.data().userId !== userId) {
    throw new functions.https.HttpsError("permission-denied", "Cannot logout this device");
  }

  // Deactivate device
  await db.collection("devices").doc(deviceIdToLogout).update({
    isActive: false,
    deactivatedAt: admin.firestore.FieldValue.serverTimestamp(),
    deactivationReason: "Logged out from another device",
  });

  // Revoke all sessions for this device
  const sessions = await db
    .collection("sessions")
    .where("deviceId", "==", deviceIdToLogout)
    .where("isRevoked", "==", false)
    .get();

  const batch = db.batch();
  sessions.forEach((doc) => {
    batch.update(doc.ref, {
      isRevoked: true,
      revokedAt: admin.firestore.FieldValue.serverTimestamp(),
    });
  });
  await batch.commit();

  // Decrement active device count
  await db
    .collection("subscriptions")
    .doc(userId)
    .update({
      activeDeviceCount: admin.firestore.FieldValue.increment(-1),
    });

  console.log(`Device ${deviceIdToLogout} logged out by user ${userId}`);

  return { success: true, message: "Device logged out successfully" };
});

/**
 * Get list of user's devices
 */
exports.getDevices = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  // Apply rate limiting
  await applyRateLimit(context, "getDevices");

  const devices = await db.collection("devices").where("userId", "==", userId).get();

  return devices.docs.map((doc) => ({
    deviceId: doc.id,
    deviceName: doc.data().deviceName,
    deviceType: doc.data().deviceType,
    osVersion: doc.data().osVersion,
    appVersion: doc.data().appVersion,
    firstSeen: doc.data().firstSeen?.toDate().toISOString(),
    lastSeen: doc.data().lastSeen?.toDate().toISOString(),
    isActive: doc.data().isActive,
  }));
});

// ============================================================
// STRIPE PAYMENT WEBHOOKS
// ============================================================

/**
 * Stripe webhook handler with idempotency protection
 *
 * SECURITY: Prevents duplicate event processing which could cause:
 * - Double subscription activations
 * - Duplicate invoice processing
 * - Payment state inconsistencies
 */
exports.stripeWebhook = functions.https.onRequest(async (req, res) => {
  const sig = req.headers["stripe-signature"];
  const endpointSecret = functions.config().stripe?.webhook_secret || process.env.STRIPE_WEBHOOK_SECRET;

  let event;

  try {
    event = stripeClient.webhooks.constructEvent(req.rawBody, sig, endpointSecret);
  } catch (err) {
    console.error(`Webhook signature verification failed: ${err.message}`);
    return res.status(400).send(`Webhook Error: ${err.message}`);
  }

  console.log(`Received Stripe event: ${event.type} (id: ${event.id})`);

  // IDEMPOTENCY CHECK: Prevent duplicate event processing
  // Stripe may retry webhooks, so we track processed event IDs
  const eventRef = db.collection("stripe_events").doc(event.id);

  try {
    // Use a transaction to atomically check and mark the event
    const alreadyProcessed = await db.runTransaction(async (transaction) => {
      const eventDoc = await transaction.get(eventRef);

      if (eventDoc.exists) {
        console.log(`Event ${event.id} already processed, skipping`);
        return true; // Already processed
      }

      // Mark event as being processed
      transaction.set(eventRef, {
        eventId: event.id,
        eventType: event.type,
        processedAt: admin.firestore.FieldValue.serverTimestamp(),
        status: "processing",
      });

      return false; // Not yet processed
    });

    if (alreadyProcessed) {
      // Event was already processed - return success to prevent Stripe retries
      return res.json({ received: true, status: "already_processed" });
    }
  } catch (idempotencyError) {
    console.error(`Idempotency check failed: ${idempotencyError.message}`);
    // If idempotency check fails, still try to process but log the issue
    // This prevents webhook failures due to Firestore issues
  }

  try {
    switch (event.type) {
      case "checkout.session.completed":
        await handleCheckoutComplete(event.data.object);
        break;

      case "customer.subscription.created":
        await handleSubscriptionCreated(event.data.object);
        break;

      case "customer.subscription.updated":
        await handleSubscriptionUpdated(event.data.object);
        break;

      case "customer.subscription.deleted":
        await handleSubscriptionCancelled(event.data.object);
        break;

      case "invoice.payment_succeeded":
        await handlePaymentSuccess(event.data.object);
        break;

      case "invoice.payment_failed":
        await handlePaymentFailed(event.data.object);
        break;

      case "charge.refunded":
        await handleChargeRefunded(event.data.object);
        break;

      case "charge.refund.updated":
        await handleRefundUpdated(event.data.object);
        break;

      case "invoice.created":
        await handleInvoiceCreated(event.data.object);
        break;

      case "invoice.finalized":
        await handleInvoiceFinalized(event.data.object);
        break;

      default:
        console.log(`Unhandled event type: ${event.type}`);
    }

    // Mark event as successfully processed
    try {
      await eventRef.update({
        status: "completed",
        completedAt: admin.firestore.FieldValue.serverTimestamp(),
      });
    } catch (updateError) {
      console.warn(`Could not update event status: ${updateError.message}`);
    }

    res.json({ received: true });
  } catch (error) {
    console.error(`Error handling webhook: ${error.message}`);

    // Mark event as failed (allows manual retry investigation)
    try {
      await eventRef.update({
        status: "failed",
        error: error.message,
        failedAt: admin.firestore.FieldValue.serverTimestamp(),
      });
    } catch (updateError) {
      console.warn(`Could not update event status: ${updateError.message}`);
    }

    res.status(500).send(`Webhook Error: ${error.message}`);
  }
});

/**
 * Create Stripe checkout session
 */
exports.createCheckoutSession = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  // Apply rate limiting (stricter for payment operations)
  await applyRateLimit(context, "createCheckoutSession");

  const { tier, billingCycle } = data;

  // Validate tier
  const tierValidation = validateTier(tier);
  if (!tierValidation.valid) {
    throw new functions.https.HttpsError("invalid-argument", tierValidation.error);
  }

  // Validate billing cycle
  const cycleValidation = validateBillingCycle(billingCycle);
  if (!cycleValidation.valid) {
    throw new functions.https.HttpsError("invalid-argument", cycleValidation.error);
  }

  // Log checkout attempt for fraud detection
  await logSecurityEvent(userId, "CHECKOUT_INITIATED", { tier, billingCycle });

  // Get user
  const userDoc = await db.collection("users").doc(userId).get();
  const user = userDoc.data();

  // Get or create Stripe customer
  let customerId = user.stripeCustomerId;

  if (!customerId) {
    const customer = await stripeClient.customers.create({
      email: user.email,
      metadata: { firebaseUid: userId },
    });
    customerId = customer.id;

    await db.collection("users").doc(userId).update({
      stripeCustomerId: customerId,
    });
  }

  // Get price ID
  let priceId;
  let mode = "subscription";

  if (tier === "LIFETIME") {
    priceId = STRIPE_PRICES.LIFETIME.onetime;
    mode = "payment";
  } else {
    priceId = STRIPE_PRICES[tier]?.[billingCycle || "monthly"];
  }

  if (!priceId) {
    throw new functions.https.HttpsError("invalid-argument", "Invalid price configuration");
  }

  // Check if user has already used trial
  const subDoc = await db.collection("subscriptions").doc(userId).get();
  const hasUsedTrial = subDoc.exists && subDoc.data().tier !== "FREE_TRIAL";

  // Create checkout session
  const session = await stripeClient.checkout.sessions.create({
    customer: customerId,
    payment_method_types: ["card"],
    line_items: [{ price: priceId, quantity: 1 }],
    mode: mode,
    success_url: `${functions.config().app?.url || "https://app.termivoxed.com"}/subscription/success?session_id={CHECKOUT_SESSION_ID}`,
    cancel_url: `${functions.config().app?.url || "https://app.termivoxed.com"}/subscription/cancelled`,
    subscription_data:
      mode === "subscription"
        ? {
            trial_period_days: hasUsedTrial ? 0 : 7,
          }
        : undefined,
    metadata: {
      userId: userId,
      tier: tier,
    },
  });

  return { checkoutUrl: session.url, sessionId: session.id };
});

/**
 * Get customer portal session (for managing subscription)
 */
exports.createCustomerPortalSession = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  const userDoc = await db.collection("users").doc(userId).get();
  const customerId = userDoc.data()?.stripeCustomerId;

  if (!customerId) {
    throw new functions.https.HttpsError("failed-precondition", "No Stripe customer found");
  }

  const session = await stripeClient.billingPortal.sessions.create({
    customer: customerId,
    return_url: `${functions.config().app?.url || "https://app.termivoxed.com"}/account`,
  });

  return { portalUrl: session.url };
});

// ============================================================
// USAGE TRACKING
// ============================================================

/**
 * Track usage (exports, TTS minutes, AI generations)
 */
exports.trackUsage = functions.https.onCall(async (data, context) => {
  if (!context.auth) {
    throw new functions.https.HttpsError("unauthenticated", "User must be logged in");
  }

  const userId = context.auth.uid;

  // Apply rate limiting
  await applyRateLimit(context, "trackUsage");

  const { action, amount, metadata } = data;

  // Validate action
  const validActions = ["export", "tts_minute", "ai_generation"];
  if (!action || typeof action !== "string" || !validActions.includes(action)) {
    throw new functions.https.HttpsError(
      "invalid-argument",
      `Invalid action type. Must be one of: ${validActions.join(", ")}`
    );
  }

  // Validate amount
  if (amount !== undefined) {
    if (typeof amount !== "number" || amount < 0 || amount > 1000) {
      throw new functions.https.HttpsError("invalid-argument", "Amount must be a number between 0 and 1000");
    }
  }

  // Sanitize metadata
  const sanitizedMetadata = {};
  if (metadata && typeof metadata === "object") {
    for (const [key, value] of Object.entries(metadata)) {
      if (typeof key === "string" && key.length <= 50) {
        if (typeof value === "string") {
          sanitizedMetadata[key] = sanitizeString(value, 200);
        } else if (typeof value === "number" || typeof value === "boolean") {
          sanitizedMetadata[key] = value;
        }
      }
    }
  }

  // Get subscription
  const subDoc = await db.collection("subscriptions").doc(userId).get();

  if (!subDoc.exists) {
    throw new functions.https.HttpsError("failed-precondition", "No subscription found");
  }

  const subscription = subDoc.data();
  const usage = subscription.usageThisMonth || {};
  const limits = subscription.usageLimits || {};

  // Check limits
  let currentUsage = 0;
  let limit = -1;
  let usageField = "";

  switch (action) {
    case "export":
      currentUsage = usage.exportsCount || 0;
      limit = limits.maxExportsPerMonth;
      usageField = "usageThisMonth.exportsCount";
      break;
    case "tts_minute":
      currentUsage = usage.ttsMinutes || 0;
      limit = limits.maxTtsMinutesPerMonth;
      usageField = "usageThisMonth.ttsMinutes";
      break;
    case "ai_generation":
      currentUsage = usage.aiGenerations || 0;
      limit = limits.maxAiGenerationsPerMonth;
      usageField = "usageThisMonth.aiGenerations";
      break;
  }

  // Check if limit exceeded
  if (limit !== -1 && currentUsage + (amount || 1) > limit) {
    return {
      allowed: false,
      message: `Monthly limit exceeded. Used: ${currentUsage}/${limit}`,
      currentUsage: currentUsage,
      limit: limit,
      upgradeUrl: `${functions.config().app?.url || "https://app.termivoxed.com"}/upgrade`,
    };
  }

  // Update usage
  await db
    .collection("subscriptions")
    .doc(userId)
    .update({
      [usageField]: admin.firestore.FieldValue.increment(amount || 1),
    });

  // Log usage
  await db.collection("usage_logs").doc(userId).collection("logs").add({
    action: action,
    amount: amount || 1,
    timestamp: admin.firestore.FieldValue.serverTimestamp(),
    metadata: sanitizedMetadata,
  });

  return {
    allowed: true,
    currentUsage: currentUsage + (amount || 1),
    limit: limit,
  };
});

/**
 * Reset monthly usage (scheduled function - runs on 1st of each month)
 */
exports.resetMonthlyUsage = functions.pubsub.schedule("0 0 1 * *").onRun(async (context) => {
  console.log("Resetting monthly usage for all users...");

  const subscriptions = await db.collection("subscriptions").get();

  const batch = db.batch();

  subscriptions.forEach((doc) => {
    batch.update(doc.ref, {
      usageThisMonth: {
        exportsCount: 0,
        ttsMinutes: 0,
        aiGenerations: 0,
      },
    });
  });

  await batch.commit();

  console.log(`Reset usage for ${subscriptions.size} subscriptions`);
});

// ============================================================
// FRAUD DETECTION
// ============================================================

/**
 * Report suspicious activity
 */
exports.reportSuspiciousActivity = functions.https.onCall(async (data, context) => {
  // Can be called with or without auth (for tamper detection)
  const userId = context.auth?.uid || "anonymous";
  const { type, details, deviceFingerprint } = data;

  await db.collection("fraud_alerts").add({
    userId: userId,
    type: type,
    severity: getSeverity(type),
    details: details || {},
    deviceFingerprint: deviceFingerprint,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    resolved: false,
  });

  console.warn(`Fraud alert: ${type} for user ${userId}`);

  // TODO: Send alert to admin (PagerDuty, Slack, email)

  return { reported: true };
});

// ============================================================
// HELPER FUNCTIONS
// ============================================================

/**
 * Generate SHA-256 hash of device fingerprint
 *
 * SECURITY: Uses full SHA256 hash (64 hex chars / 256 bits) to prevent collisions.
 * Previously truncated to 32 chars (128 bits) which increased collision risk.
 */
function hashFingerprint(fingerprint) {
  const crypto = require("crypto");
  // SECURITY: Use full SHA256 hash, not truncated
  return crypto.createHash("sha256").update(`TERMIVOXED_DEVICE_${fingerprint}`).digest("hex");
}

/**
 * Generate referral code
 */
function generateReferralCode() {
  return uuidv4().slice(0, 8).toUpperCase();
}

/**
 * Register a new device
 */
async function registerDevice(userId, deviceId, fingerprint, deviceData) {
  await db.collection("devices").doc(deviceId).set({
    userId: userId,
    fingerprint: fingerprint, // Store for verification
    deviceName: deviceData.deviceName || "Unknown Device",
    deviceType: deviceData.deviceType || "UNKNOWN",
    osVersion: deviceData.osVersion || "",
    appVersion: deviceData.appVersion || "",
    firstSeen: admin.firestore.FieldValue.serverTimestamp(),
    lastSeen: admin.firestore.FieldValue.serverTimestamp(),
    isActive: true,
  });

  // Increment active device count
  await db
    .collection("subscriptions")
    .doc(userId)
    .update({
      activeDeviceCount: admin.firestore.FieldValue.increment(1),
    });

  console.log(`Registered new device ${deviceId} for user ${userId}`);
}

/**
 * Generate JWT license token
 */
function generateLicenseToken(userId, deviceId, subscription) {
  const payload = {
    uid: userId,
    did: deviceId,
    tier: subscription.tier,
    features: subscription.features,
    iat: Math.floor(Date.now() / 1000),
    exp: Math.floor(Date.now() / 1000) + 24 * 60 * 60, // 24 hours
  };

  return jwt.sign(payload, JWT_SECRET);
}

/**
 * Get tier from Stripe price ID
 */
function getTierFromPrice(priceId) {
  for (const [tier, prices] of Object.entries(STRIPE_PRICES)) {
    if (Object.values(prices).includes(priceId)) {
      return tier;
    }
  }
  return "BASIC"; // Default
}

/**
 * Get severity level for fraud type
 */
function getSeverity(type) {
  const severityMap = {
    DEVICE_LIMIT_EXCEEDED: "LOW",
    SUSPICIOUS_LOCATION: "MEDIUM",
    RAPID_DEVICE_CHANGES: "MEDIUM",
    TAMPER_DETECTED: "HIGH",
    DEBUGGER_DETECTED: "HIGH",
    LICENSE_SHARING: "CRITICAL",
  };
  return severityMap[type] || "MEDIUM";
}

// ============================================================
// STRIPE WEBHOOK HANDLERS
// ============================================================

async function handleCheckoutComplete(session) {
  const userId = session.metadata.userId;
  const tier = session.metadata.tier;

  console.log(`Checkout completed for user ${userId}, tier: ${tier}`);

  if (session.mode === "payment") {
    // One-time payment (LIFETIME)
    await db.collection("subscriptions").doc(userId).update({
      tier: tier,
      status: "ACTIVE",
      stripeSubscriptionId: null,
      currentPeriodStart: admin.firestore.FieldValue.serverTimestamp(),
      currentPeriodEnd: null, // Never expires
      maxDevices: TIER_CONFIG[tier].maxDevices,
      features: TIER_CONFIG[tier].features,
      usageLimits: {
        maxExportsPerMonth: TIER_CONFIG[tier].maxExportsPerMonth,
        maxTtsMinutesPerMonth: TIER_CONFIG[tier].maxTtsMinutesPerMonth,
        maxAiGenerationsPerMonth: TIER_CONFIG[tier].maxAiGenerationsPerMonth,
        maxVideoDurationMinutes: TIER_CONFIG[tier].maxVideoDurationMinutes,
      },
      history: admin.firestore.FieldValue.arrayUnion({
        action: "LIFETIME_PURCHASED",
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
        details: { tier: tier },
      }),
    });
  }
  // Subscription handled by customer.subscription.created
}

async function handleSubscriptionCreated(subscription) {
  const customerId = subscription.customer;

  // Find user by Stripe customer ID
  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (users.empty) {
    console.error(`No user found for Stripe customer: ${customerId}`);
    return;
  }

  const userId = users.docs[0].id;
  const tier = getTierFromPrice(subscription.items.data[0].price.id);

  await db.collection("subscriptions").doc(userId).update({
    tier: tier,
    status: "ACTIVE",
    stripeSubscriptionId: subscription.id,
    currentPeriodStart: admin.firestore.Timestamp.fromMillis(subscription.current_period_start * 1000),
    currentPeriodEnd: admin.firestore.Timestamp.fromMillis(subscription.current_period_end * 1000),
    maxDevices: TIER_CONFIG[tier].maxDevices,
    features: TIER_CONFIG[tier].features,
    usageLimits: {
      maxExportsPerMonth: TIER_CONFIG[tier].maxExportsPerMonth,
      maxTtsMinutesPerMonth: TIER_CONFIG[tier].maxTtsMinutesPerMonth,
      maxAiGenerationsPerMonth: TIER_CONFIG[tier].maxAiGenerationsPerMonth,
      maxVideoDurationMinutes: TIER_CONFIG[tier].maxVideoDurationMinutes,
    },
    history: admin.firestore.FieldValue.arrayUnion({
      action: "SUBSCRIPTION_CREATED",
      timestamp: admin.firestore.FieldValue.serverTimestamp(),
      details: { tier: tier, stripeSubscriptionId: subscription.id },
    }),
  });

  console.log(`Subscription created for user ${userId}: ${tier}`);
}

async function handleSubscriptionUpdated(subscription) {
  const customerId = subscription.customer;

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (users.empty) return;

  const userId = users.docs[0].id;
  const tier = getTierFromPrice(subscription.items.data[0].price.id);
  const status = subscription.status === "active" ? "ACTIVE" : subscription.status === "past_due" ? "PAST_DUE" : subscription.status;

  await db.collection("subscriptions").doc(userId).update({
    tier: tier,
    status: status.toUpperCase(),
    currentPeriodEnd: admin.firestore.Timestamp.fromMillis(subscription.current_period_end * 1000),
    maxDevices: TIER_CONFIG[tier]?.maxDevices || 1,
    features: TIER_CONFIG[tier]?.features || TIER_CONFIG.BASIC.features,
  });

  console.log(`Subscription updated for user ${userId}: ${tier}, status: ${status}`);
}

async function handleSubscriptionCancelled(subscription) {
  const customerId = subscription.customer;

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (users.empty) return;

  const userId = users.docs[0].id;

  await db.collection("subscriptions").doc(userId).update({
    status: "CANCELLED",
    cancelledAt: admin.firestore.FieldValue.serverTimestamp(),
    history: admin.firestore.FieldValue.arrayUnion({
      action: "SUBSCRIPTION_CANCELLED",
      timestamp: admin.firestore.FieldValue.serverTimestamp(),
    }),
  });

  console.log(`Subscription cancelled for user ${userId}`);
}

async function handlePaymentSuccess(invoice) {
  console.log(`Payment succeeded for invoice: ${invoice.id}`);
  // Update subscription status to ACTIVE if it was PAST_DUE
  const customerId = invoice.customer;

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (!users.empty) {
    const userId = users.docs[0].id;
    await db.collection("subscriptions").doc(userId).update({
      status: "ACTIVE",
    });
  }
}

async function handlePaymentFailed(invoice) {
  console.warn(`Payment failed for invoice: ${invoice.id}`);

  const customerId = invoice.customer;

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (!users.empty) {
    const userId = users.docs[0].id;
    await db.collection("subscriptions").doc(userId).update({
      status: "PAST_DUE",
      lastPaymentFailure: admin.firestore.FieldValue.serverTimestamp(),
    });

    // TODO: Send payment failure email
  }
}

/**
 * Handle refund events - revoke subscription access on refund
 */
async function handleChargeRefunded(charge) {
  console.log(`Charge refunded: ${charge.id}, amount: ${charge.amount_refunded}`);

  const customerId = charge.customer;
  if (!customerId) {
    console.warn("Refund without customer ID, cannot process");
    return;
  }

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();

  if (users.empty) {
    console.warn(`No user found for refunded charge customer: ${customerId}`);
    return;
  }

  const userId = users.docs[0].id;

  // Check if fully refunded
  const isFullRefund = charge.amount_refunded >= charge.amount;

  if (isFullRefund) {
    // Full refund - revoke subscription access
    await db.collection("subscriptions").doc(userId).update({
      status: "REFUNDED",
      tier: "FREE_TRIAL",
      refundedAt: admin.firestore.FieldValue.serverTimestamp(),
      refundAmount: charge.amount_refunded,
      history: admin.firestore.FieldValue.arrayUnion({
        action: "SUBSCRIPTION_REFUNDED",
        amount: charge.amount_refunded,
        chargeId: charge.id,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      }),
    });

    console.log(`Full refund processed for user ${userId}, subscription revoked`);
  } else {
    // Partial refund - log but maintain access
    await db.collection("subscriptions").doc(userId).update({
      partialRefund: true,
      partialRefundAmount: charge.amount_refunded,
      history: admin.firestore.FieldValue.arrayUnion({
        action: "PARTIAL_REFUND",
        amount: charge.amount_refunded,
        chargeId: charge.id,
        timestamp: admin.firestore.FieldValue.serverTimestamp(),
      }),
    });

    console.log(`Partial refund processed for user ${userId}`);
  }
}

/**
 * Handle refund status updates
 */
async function handleRefundUpdated(refund) {
  console.log(`Refund updated: ${refund.id}, status: ${refund.status}`);

  // Log refund status updates for audit trail
  if (refund.charge) {
    const charge = await stripeClient.charges.retrieve(refund.charge);
    if (charge.customer) {
      const users = await db.collection("users").where("stripeCustomerId", "==", charge.customer).get();
      if (!users.empty) {
        const userId = users.docs[0].id;
        await db.collection("subscriptions").doc(userId).update({
          history: admin.firestore.FieldValue.arrayUnion({
            action: "REFUND_STATUS_UPDATE",
            refundId: refund.id,
            status: refund.status,
            timestamp: admin.firestore.FieldValue.serverTimestamp(),
          }),
        });
      }
    }
  }
}

/**
 * Handle invoice creation - for audit and future invoice features
 */
async function handleInvoiceCreated(invoice) {
  console.log(`Invoice created: ${invoice.id}, amount: ${invoice.amount_due}`);

  const customerId = invoice.customer;
  if (!customerId) return;

  const users = await db.collection("users").where("stripeCustomerId", "==", customerId).get();
  if (users.empty) return;

  const userId = users.docs[0].id;

  // Store invoice reference for user access
  await db.collection("invoices").doc(invoice.id).set({
    userId: userId,
    customerId: customerId,
    amount: invoice.amount_due,
    currency: invoice.currency,
    status: invoice.status,
    createdAt: admin.firestore.FieldValue.serverTimestamp(),
    invoiceUrl: invoice.hosted_invoice_url,
    invoicePdf: invoice.invoice_pdf,
  });
}

/**
 * Handle invoice finalization - update invoice with final URLs
 */
async function handleInvoiceFinalized(invoice) {
  console.log(`Invoice finalized: ${invoice.id}`);

  await db.collection("invoices").doc(invoice.id).update({
    status: invoice.status,
    finalizedAt: admin.firestore.FieldValue.serverTimestamp(),
    invoiceUrl: invoice.hosted_invoice_url,
    invoicePdf: invoice.invoice_pdf,
    invoiceNumber: invoice.number,
  });
}
