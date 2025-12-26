# TermiVoxed Deployment Guide

Complete step-by-step instructions for setting up Firebase, deploying the application, and performing customer-level testing.

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Stage 1: Firebase Project Setup](#stage-1-firebase-project-setup)
3. [Stage 2: Firebase Authentication Setup](#stage-2-firebase-authentication-setup)
4. [Stage 3: Firestore Database Setup](#stage-3-firestore-database-setup)
5. [Stage 4: Cloud Functions Deployment](#stage-4-cloud-functions-deployment)
6. [Stage 5: Stripe Payment Setup](#stage-5-stripe-payment-setup)
7. [Stage 6: Backend API Configuration](#stage-6-backend-api-configuration)
8. [Stage 7: Frontend Configuration](#stage-7-frontend-configuration)
9. [Stage 8: Local Testing](#stage-8-local-testing)
10. [Stage 9: Production Deployment](#stage-9-production-deployment)
11. [Stage 10: Customer-Level Testing](#stage-10-customer-level-testing)

---

## 1. Prerequisites

### Required Tools
```bash
# Node.js (v18 or higher)
node --version  # Should be >= 18.0.0

# Python (3.10 or higher)
python3 --version  # Should be >= 3.10

# Firebase CLI
npm install -g firebase-tools
firebase --version

# Git
git --version
```

### Required Accounts
- [ ] Google Cloud / Firebase account
- [ ] Stripe account (for payments)
- [ ] (Optional) Razorpay account (for India payments)

---

## Stage 1: Firebase Project Setup

### Step 1.1: Create Firebase Project

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Click **"Create a project"**
3. Enter project name: `termivoxed` (or your preferred name)
4. Enable Google Analytics (recommended)
5. Select or create a Google Analytics account
6. Click **"Create project"**

### Step 1.2: Upgrade to Blaze Plan

> **Important:** Cloud Functions require the Blaze (pay-as-you-go) plan.

1. In Firebase Console, click the gear icon → **"Usage and billing"**
2. Click **"Details & settings"**
3. Click **"Modify plan"** → Select **"Blaze"**
4. Add a billing account

### Step 1.3: Get Firebase Configuration

1. In Firebase Console, click the gear icon → **"Project settings"**
2. Scroll to **"Your apps"** section
3. Click the web icon (`</>`) to add a web app
4. Register app with nickname: `termivoxed-web`
5. Copy the Firebase configuration object:

```javascript
// Save these values - you'll need them later
const firebaseConfig = {
  apiKey: "AIza...",
  authDomain: "termivoxed.firebaseapp.com",
  projectId: "termivoxed",
  storageBucket: "termivoxed.appspot.com",
  messagingSenderId: "123456789",
  appId: "1:123456789:web:abc123",
  measurementId: "G-XXXXXX"
};
```

### Step 1.4: Download Service Account Key

1. Go to **Project settings** → **"Service accounts"** tab
2. Click **"Generate new private key"**
3. Save the JSON file as `firebase-service-account.json`
4. **NEVER commit this file to git!**

```bash
# Move to a secure location
mkdir -p ~/.termivoxed
mv ~/Downloads/termivoxed-firebase-adminsdk-*.json ~/.termivoxed/firebase-service-account.json
chmod 600 ~/.termivoxed/firebase-service-account.json
```

---

## Stage 2: Firebase Authentication Setup

### Step 2.1: Enable Authentication Providers

1. In Firebase Console, go to **"Authentication"** → **"Sign-in method"**
2. Enable the following providers:

#### Email/Password
- Click **"Email/Password"**
- Enable **"Email/Password"**
- (Optional) Enable **"Email link (passwordless sign-in)"**
- Click **"Save"**

#### Google
- Click **"Google"**
- Enable it
- Set **Project support email**
- Click **"Save"**

#### GitHub (Optional)
- Click **"GitHub"**
- Enable it
- You'll need to create a GitHub OAuth App:
  1. Go to GitHub → Settings → Developer settings → OAuth Apps
  2. Create new OAuth App
  3. Set Authorization callback URL to: `https://termivoxed.firebaseapp.com/__/auth/handler`
  4. Copy Client ID and Client Secret to Firebase
- Click **"Save"**

### Step 2.2: Configure Authorized Domains

1. Go to **"Authentication"** → **"Settings"** → **"Authorized domains"**
2. Add your domains:
   - `localhost` (for development)
   - `termivoxed.web.app` (Firebase hosting)
   - `app.termivoxed.com` (your custom domain)

### Step 2.3: Set Up Admin User (First Admin)

After your first user signs up, make them an admin:

```bash
# Install Firebase Admin SDK locally
cd /path/to/console_video_editor
pip install firebase-admin

# Create a script to set admin claims
cat > set_admin.py << 'EOF'
import firebase_admin
from firebase_admin import credentials, auth
import sys

# Initialize Firebase Admin
cred = credentials.Certificate("/path/to/.termivoxed/firebase-service-account.json")
firebase_admin.initialize_app(cred)

# Set admin claim for user
uid = sys.argv[1] if len(sys.argv) > 1 else input("Enter user UID: ")
auth.set_custom_user_claims(uid, {'admin': True})
print(f"Admin claim set for user: {uid}")
EOF

# Run it with the first user's UID
python set_admin.py "USER_UID_HERE"
```

---

## Stage 3: Firestore Database Setup

### Step 3.1: Create Firestore Database

1. In Firebase Console, go to **"Firestore Database"**
2. Click **"Create database"**
3. Choose **"Start in production mode"** (we'll deploy secure rules)
4. Select a location closest to your users:
   - For India: `asia-south1` (Mumbai)
   - For US: `us-central1`
   - For Europe: `europe-west1`
5. Click **"Enable"**

### Step 3.2: Deploy Security Rules

```bash
# Navigate to project directory
cd /path/to/console_video_editor

# Login to Firebase
firebase login

# Initialize Firebase in the project (if not done)
firebase init

# Select:
# - Firestore
# - Functions
# - Hosting (optional)

# Deploy only Firestore rules
firebase deploy --only firestore:rules
```

Verify deployment:
1. Go to Firebase Console → Firestore → **"Rules"** tab
2. Confirm the rules match `firestore.rules`

### Step 3.3: Create Required Indexes (if needed)

Firebase will auto-create indexes, but you can pre-create them:

```bash
# Deploy indexes
firebase deploy --only firestore:indexes
```

---

## Stage 4: Cloud Functions Deployment

### Step 4.1: Install Dependencies

```bash
cd cloud_functions/functions
npm install
```

### Step 4.2: Configure Firebase Functions

```bash
# Set Stripe secret key
firebase functions:config:set stripe.secret_key="sk_test_YOUR_STRIPE_SECRET_KEY"

# Set Stripe webhook secret (get this after creating webhook in Stripe)
firebase functions:config:set stripe.webhook_secret="whsec_YOUR_WEBHOOK_SECRET"

# Set JWT secret for license tokens (generate a secure random string)
firebase functions:config:set jwt.secret="$(openssl rand -hex 32)"

# Set Stripe price IDs (create these in Stripe Dashboard first)
firebase functions:config:set stripe.basic_monthly="price_xxxxx"
firebase functions:config:set stripe.basic_yearly="price_xxxxx"
firebase functions:config:set stripe.pro_monthly="price_xxxxx"
firebase functions:config:set stripe.pro_yearly="price_xxxxx"
firebase functions:config:set stripe.lifetime="price_xxxxx"

# Set app URL
firebase functions:config:set app.url="https://app.termivoxed.com"

# Verify configuration
firebase functions:config:get
```

### Step 4.3: Deploy Cloud Functions

```bash
# Deploy all functions
firebase deploy --only functions

# Or deploy specific functions
firebase deploy --only functions:verifyLicense,functions:stripeWebhook
```

### Step 4.4: Get Function URLs

After deployment, note the function URLs:
```
✔ functions[stripeWebhook]: https://us-central1-termivoxed.cloudfunctions.net/stripeWebhook
✔ functions[verifyLicense]: Deployed
✔ functions[createCheckoutSession]: Deployed
```

---

## Stage 5: Stripe Payment Setup

### Step 5.1: Create Stripe Account

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/)
2. Create an account or sign in
3. Complete business verification

### Step 5.2: Get API Keys

1. Go to **Developers** → **API keys**
2. Copy:
   - **Publishable key**: `pk_test_...` (for frontend)
   - **Secret key**: `sk_test_...` (for backend/functions)

### Step 5.3: Create Products and Prices

1. Go to **Products** → **Add product**

#### Individual/Basic Plan
- Name: `TermiVoxed Individual`
- Pricing:
  - Monthly: ₹149 / $4.99
  - Yearly: ₹1,499 / $49.99
- Copy the `price_xxx` IDs

#### Pro Plan
- Name: `TermiVoxed Pro`
- Pricing:
  - Monthly: ₹299 / $9.99
  - Yearly: ₹2,999 / $99.99
- Copy the `price_xxx` IDs

#### Lifetime
- Name: `TermiVoxed Lifetime`
- One-time: ₹4,999 / $149.99
- Copy the `price_xxx` ID

### Step 5.4: Create Webhook

1. Go to **Developers** → **Webhooks**
2. Click **"Add endpoint"**
3. Endpoint URL: `https://us-central1-termivoxed.cloudfunctions.net/stripeWebhook`
4. Select events:
   - `checkout.session.completed`
   - `customer.subscription.created`
   - `customer.subscription.updated`
   - `customer.subscription.deleted`
   - `invoice.payment_succeeded`
   - `invoice.payment_failed`
   - `invoice.created`
   - `invoice.finalized`
   - `charge.refunded`
5. Click **"Add endpoint"**
6. Copy the **Signing secret** (`whsec_...`)

### Step 5.5: Update Firebase Config with Webhook Secret

```bash
firebase functions:config:set stripe.webhook_secret="whsec_YOUR_SIGNING_SECRET"
firebase deploy --only functions:stripeWebhook
```

---

## Stage 6: Backend API Configuration

### Step 6.1: Create Environment File

```bash
cd /path/to/console_video_editor

# Copy example env
cp .env.example .env

# Edit the .env file
nano .env
```

### Step 6.2: Configure Environment Variables

```bash
# .env file contents

# Firebase Configuration
GOOGLE_APPLICATION_CREDENTIALS=/path/to/.termivoxed/firebase-service-account.json

# Server Configuration
TERMIVOXED_HOST=localhost
TERMIVOXED_PORT=8000
TERMIVOXED_ENV=development  # Change to 'production' for prod

# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_YOUR_SECRET_KEY
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_PUBLISHABLE_KEY
STRIPE_WEBHOOK_SECRET=whsec_YOUR_WEBHOOK_SECRET

# Razorpay Configuration (optional, for India)
RAZORPAY_KEY_ID=rzp_test_YOUR_KEY_ID
RAZORPAY_KEY_SECRET=YOUR_KEY_SECRET

# TTS Configuration
ELEVENLABS_API_KEY=your_elevenlabs_key  # Optional
OPENAI_API_KEY=your_openai_key  # Optional

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434  # Local Ollama
```

### Step 6.3: Install Python Dependencies

```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Step 6.4: Test Backend Startup

```bash
# Start the backend
python -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port 8000 --reload

# You should see:
# TermiVoxed - AI Voice-Over Studio
# → http://localhost:8000
# → API Docs: http://localhost:8000/docs
```

---

## Stage 7: Frontend Configuration

### Step 7.1: Install Dependencies

```bash
cd web_ui/frontend
npm install
```

### Step 7.2: Create Frontend Environment File

```bash
# Create .env file
cat > .env << 'EOF'
# Firebase Configuration (from Stage 1.3)
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=termivoxed.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=termivoxed
VITE_FIREBASE_STORAGE_BUCKET=termivoxed.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXX

# Stripe
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY

# API URL
VITE_API_URL=http://localhost:8000/api/v1
EOF
```

### Step 7.3: Test Frontend Startup

```bash
# Start development server
npm run dev

# You should see:
# VITE v5.x.x ready in xxx ms
# ➜ Local: http://localhost:5173/
```

---

## Stage 8: Local Testing

### Step 8.1: Start All Services

Open 3 terminal windows:

**Terminal 1 - Backend:**
```bash
cd /path/to/console_video_editor
source venv/bin/activate
python -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 - Frontend:**
```bash
cd /path/to/console_video_editor/web_ui/frontend
npm run dev
```

**Terminal 3 - Firebase Emulators (optional for local testing):**
```bash
cd /path/to/console_video_editor
firebase emulators:start --only functions,firestore,auth
```

### Step 8.2: Basic Functionality Test

1. Open http://localhost:5173
2. Click **"Sign Up"** → Create account with email/password
3. Verify email (check Firebase Console → Authentication)
4. Log in
5. Check that free trial is activated
6. Create a test project
7. Upload a test video
8. Test subtitle generation
9. Test TTS generation
10. Test export

### Step 8.3: Test Stripe Integration

```bash
# Use Stripe CLI for webhook testing
brew install stripe/stripe-cli/stripe  # macOS
# or download from https://stripe.com/docs/stripe-cli

# Login to Stripe CLI
stripe login

# Forward webhooks to local function
stripe listen --forward-to localhost:8000/api/v1/payments/webhook

# In another terminal, trigger a test event
stripe trigger checkout.session.completed
```

---

## Stage 9: Production Deployment

### Step 9.1: Build Frontend

```bash
cd web_ui/frontend

# Update .env for production
cat > .env.production << 'EOF'
VITE_FIREBASE_API_KEY=AIza...
VITE_FIREBASE_AUTH_DOMAIN=termivoxed.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=termivoxed
VITE_FIREBASE_STORAGE_BUCKET=termivoxed.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=123456789
VITE_FIREBASE_APP_ID=1:123456789:web:abc123
VITE_FIREBASE_MEASUREMENT_ID=G-XXXXXX
VITE_STRIPE_PUBLISHABLE_KEY=pk_live_YOUR_LIVE_KEY
VITE_API_URL=https://api.termivoxed.com/api/v1
EOF

# Build for production
npm run build
```

### Step 9.2: Deploy to Firebase Hosting (Optional)

```bash
# Initialize hosting if not done
firebase init hosting

# Deploy
firebase deploy --only hosting
```

### Step 9.3: Deploy Backend to Cloud

Options:
- **Google Cloud Run** (recommended)
- **AWS ECS**
- **DigitalOcean App Platform**
- **Railway/Render**

Example for Google Cloud Run:

```bash
# Build Docker image
docker build -t termivoxed-api .

# Tag for GCR
docker tag termivoxed-api gcr.io/termivoxed/api

# Push to GCR
docker push gcr.io/termivoxed/api

# Deploy to Cloud Run
gcloud run deploy termivoxed-api \
  --image gcr.io/termivoxed/api \
  --platform managed \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars "GOOGLE_APPLICATION_CREDENTIALS=/secrets/firebase-sa.json" \
  --set-secrets "STRIPE_SECRET_KEY=stripe-secret:latest"
```

### Step 9.4: Update Production Config

Update Firebase functions config for production:
```bash
# Switch to live Stripe keys
firebase functions:config:set stripe.secret_key="sk_live_YOUR_LIVE_KEY"
firebase functions:config:set stripe.webhook_secret="whsec_YOUR_LIVE_WEBHOOK_SECRET"
firebase functions:config:set app.url="https://app.termivoxed.com"

# Deploy
firebase deploy --only functions
```

---

## Stage 10: Customer-Level Testing

### Test Checklist

#### 10.1: New User Flow
- [ ] Visit landing page
- [ ] Click "Get Started" / "Sign Up"
- [ ] Register with email/password
- [ ] Receive verification email
- [ ] Verify email
- [ ] Log in successfully
- [ ] See free trial activated (7 days)
- [ ] See trial features available

#### 10.2: Core Features (Free Trial)
- [ ] Create new project
- [ ] Upload video (test different formats: MP4, MOV, AVI)
- [ ] Generate subtitles
- [ ] Edit subtitles
- [ ] Generate TTS audio
- [ ] Preview with TTS
- [ ] Export video (720p, 1080p)
- [ ] Download exported video

#### 10.3: Device Management
- [ ] Login from Device 1
- [ ] Attempt login from Device 2 (should work for trial)
- [ ] Check device list in account settings
- [ ] Remove a device
- [ ] Verify device limit enforcement

#### 10.4: Payment Flow (Use Stripe Test Mode)
- [ ] Click "Upgrade" on pricing page
- [ ] Select a plan (e.g., Pro Monthly)
- [ ] Complete checkout with test card: `4242 4242 4242 4242`
- [ ] Verify redirect to success page
- [ ] Verify subscription updated in account
- [ ] Verify features unlocked (4K export, etc.)

**Stripe Test Cards:**
| Scenario | Card Number |
|----------|-------------|
| Success | 4242 4242 4242 4242 |
| Declined | 4000 0000 0000 0002 |
| Requires Auth | 4000 0025 0000 3155 |
| Insufficient Funds | 4000 0000 0000 9995 |

#### 10.5: Subscription Management
- [ ] View subscription details
- [ ] Access billing portal
- [ ] Update payment method
- [ ] Cancel subscription
- [ ] Verify access until period end
- [ ] Verify downgrade after period end

#### 10.6: Usage Limits
- [ ] Check usage dashboard
- [ ] Export videos until limit reached (trial: 5)
- [ ] Verify limit enforcement message
- [ ] Upgrade and verify limit reset

#### 10.7: Security Testing
- [ ] Try accessing another user's project (should fail)
- [ ] Try modifying URL to access unauthorized resources
- [ ] Verify session expires after logout
- [ ] Test "Logout all devices" feature

#### 10.8: Edge Cases
- [ ] Slow network (throttle to 3G)
- [ ] Large file upload (1GB+)
- [ ] Long video (30+ minutes)
- [ ] Special characters in project names
- [ ] Multiple browser tabs
- [ ] Browser refresh during export

#### 10.9: Email Testing
- [ ] Password reset email
- [ ] Email verification
- [ ] Payment receipt email (from Stripe)
- [ ] Subscription cancelled email

#### 10.10: Error Handling
- [ ] Invalid file format upload
- [ ] Network disconnection during upload
- [ ] Payment failure
- [ ] Session expiry
- [ ] Rate limit exceeded

---

## Quick Reference

### Firebase Console Links
- Project Settings: https://console.firebase.google.com/project/termivoxed/settings/general
- Authentication: https://console.firebase.google.com/project/termivoxed/authentication
- Firestore: https://console.firebase.google.com/project/termivoxed/firestore
- Functions: https://console.firebase.google.com/project/termivoxed/functions

### Stripe Dashboard Links
- API Keys: https://dashboard.stripe.com/apikeys
- Products: https://dashboard.stripe.com/products
- Webhooks: https://dashboard.stripe.com/webhooks
- Test Payments: https://dashboard.stripe.com/test/payments

### Common Commands
```bash
# Deploy everything
firebase deploy

# Deploy specific services
firebase deploy --only functions
firebase deploy --only firestore:rules
firebase deploy --only hosting

# View function logs
firebase functions:log

# Run local emulators
firebase emulators:start

# Stripe webhook forwarding
stripe listen --forward-to localhost:8000/api/v1/payments/webhook
```

### Troubleshooting

**Firebase Auth not working:**
- Check authorized domains in Firebase Console
- Verify API key is correct in frontend .env

**Cloud Functions failing:**
- Check logs: `firebase functions:log`
- Verify config: `firebase functions:config:get`
- Check Blaze plan is active

**Stripe webhooks not received:**
- Verify webhook URL is correct
- Check webhook signing secret matches
- Test with Stripe CLI locally

**Backend can't connect to Firebase:**
- Verify `GOOGLE_APPLICATION_CREDENTIALS` path
- Check service account has correct permissions
- Ensure Firestore is enabled

---

## Support

For issues:
1. Check logs in Firebase Console
2. Check browser developer console
3. Review this guide's troubleshooting section
4. Report issues at: https://github.com/anthropics/claude-code/issues
