# TermiVoxed Setup Checklist

Print this checklist and check off each item as you complete it.

---

## Phase 1: Firebase Setup (30-45 minutes)

### Firebase Console
- [ ] Create Firebase project at https://console.firebase.google.com
- [ ] Upgrade to Blaze plan (required for Cloud Functions)
- [ ] Add web app and copy config values
- [ ] Download service account JSON key
- [ ] Save key to `~/.termivoxed/firebase-service-account.json`

### Authentication
- [ ] Enable Email/Password provider
- [ ] Enable Google provider
- [ ] (Optional) Enable GitHub provider
- [ ] Add authorized domains: `localhost`, your production domain

### Firestore
- [ ] Create Firestore database
- [ ] Select region (e.g., `asia-south1` for India)
- [ ] Deploy security rules: `firebase deploy --only firestore:rules`

---

## Phase 2: Stripe Setup (20-30 minutes)

### Stripe Dashboard
- [ ] Create/access Stripe account at https://dashboard.stripe.com
- [ ] Copy API keys (Publishable and Secret)
- [ ] Create products and prices:
  - [ ] Individual Monthly: ₹149 / $4.99
  - [ ] Individual Yearly: ₹1,499 / $49.99
  - [ ] Pro Monthly: ₹299 / $9.99
  - [ ] Pro Yearly: ₹2,999 / $99.99
  - [ ] Lifetime: ₹4,999 / $149.99
- [ ] Note all `price_xxx` IDs

### Stripe Webhook
- [ ] Create webhook endpoint pointing to your Cloud Function URL
- [ ] Select required events (checkout, subscription, invoice, charge)
- [ ] Copy webhook signing secret (`whsec_...`)

---

## Phase 3: Cloud Functions (15-20 minutes)

### Configuration
```bash
# Run these commands:
firebase functions:config:set stripe.secret_key="sk_test_xxx"
firebase functions:config:set stripe.webhook_secret="whsec_xxx"
firebase functions:config:set jwt.secret="$(openssl rand -hex 32)"
firebase functions:config:set stripe.basic_monthly="price_xxx"
firebase functions:config:set stripe.basic_yearly="price_xxx"
firebase functions:config:set stripe.pro_monthly="price_xxx"
firebase functions:config:set stripe.pro_yearly="price_xxx"
firebase functions:config:set stripe.lifetime="price_xxx"
firebase functions:config:set app.url="https://app.termivoxed.com"
```

- [ ] All config values set
- [ ] Deploy functions: `firebase deploy --only functions`
- [ ] Note function URLs for webhook

---

## Phase 4: Backend Setup (10-15 minutes)

### Environment
- [ ] Copy `.env.example` to `.env`
- [ ] Set `GOOGLE_APPLICATION_CREDENTIALS` path
- [ ] Set `STRIPE_SECRET_KEY`
- [ ] Set `STRIPE_PUBLISHABLE_KEY`
- [ ] Set `STRIPE_WEBHOOK_SECRET`
- [ ] (Optional) Set TTS API keys

### Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
- [ ] Virtual environment created
- [ ] Dependencies installed

### Test
```bash
python -m uvicorn web_ui.api.main:app --host 0.0.0.0 --port 8000
```
- [ ] Backend starts without errors
- [ ] API docs accessible at http://localhost:8000/docs

---

## Phase 5: Frontend Setup (10-15 minutes)

### Environment
Create `web_ui/frontend/.env`:
```
VITE_FIREBASE_API_KEY=xxx
VITE_FIREBASE_AUTH_DOMAIN=xxx.firebaseapp.com
VITE_FIREBASE_PROJECT_ID=xxx
VITE_FIREBASE_STORAGE_BUCKET=xxx.appspot.com
VITE_FIREBASE_MESSAGING_SENDER_ID=xxx
VITE_FIREBASE_APP_ID=xxx
VITE_STRIPE_PUBLISHABLE_KEY=pk_test_xxx
VITE_API_URL=http://localhost:8000/api/v1
```
- [ ] All Firebase config values set
- [ ] Stripe publishable key set

### Dependencies
```bash
cd web_ui/frontend
npm install
```
- [ ] Dependencies installed

### Test
```bash
npm run dev
```
- [ ] Frontend starts without errors
- [ ] Accessible at http://localhost:5173

---

## Phase 6: Integration Testing (30-45 minutes)

### Auth Flow
- [ ] Can create new account
- [ ] Can verify email
- [ ] Can log in
- [ ] Can log out
- [ ] Can reset password
- [ ] Google login works

### Free Trial
- [ ] New users get 7-day trial
- [ ] Trial features accessible
- [ ] Usage limits enforced

### Core Features
- [ ] Create project
- [ ] Upload video
- [ ] Generate subtitles
- [ ] Generate TTS
- [ ] Export video
- [ ] Download export

### Payment (Test Mode)
- [ ] Pricing page displays correctly
- [ ] Checkout redirects to Stripe
- [ ] Test payment succeeds (use `4242 4242 4242 4242`)
- [ ] Subscription activates after payment
- [ ] Pro features unlock

### Security
- [ ] Cannot access other users' projects
- [ ] Rate limiting works
- [ ] Session expires correctly

---

## Quick Commands Reference

```bash
# Start backend
source venv/bin/activate && python -m uvicorn web_ui.api.main:app --reload

# Start frontend
cd web_ui/frontend && npm run dev

# Deploy Firebase
firebase deploy

# View function logs
firebase functions:log

# Test webhooks locally
stripe listen --forward-to localhost:8000/api/v1/payments/webhook
```

---

## Environment Variables Summary

### Backend (.env)
| Variable | Description | Example |
|----------|-------------|---------|
| GOOGLE_APPLICATION_CREDENTIALS | Path to Firebase service account | ~/.termivoxed/firebase-sa.json |
| STRIPE_SECRET_KEY | Stripe secret key | sk_test_xxx |
| STRIPE_PUBLISHABLE_KEY | Stripe publishable key | pk_test_xxx |
| STRIPE_WEBHOOK_SECRET | Stripe webhook secret | whsec_xxx |
| TERMIVOXED_ENV | Environment (development/production) | development |

### Frontend (web_ui/frontend/.env)
| Variable | Description |
|----------|-------------|
| VITE_FIREBASE_API_KEY | Firebase API key |
| VITE_FIREBASE_AUTH_DOMAIN | Firebase auth domain |
| VITE_FIREBASE_PROJECT_ID | Firebase project ID |
| VITE_FIREBASE_STORAGE_BUCKET | Firebase storage bucket |
| VITE_FIREBASE_MESSAGING_SENDER_ID | Firebase messaging sender ID |
| VITE_FIREBASE_APP_ID | Firebase app ID |
| VITE_STRIPE_PUBLISHABLE_KEY | Stripe publishable key |
| VITE_API_URL | Backend API URL |

---

## Estimated Total Time: 2-3 hours

Good luck with your deployment!
