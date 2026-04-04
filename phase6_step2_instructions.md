# SafaraOne — Phase 6 Step 2
## Stripe Payment Integration: Instructions for Antigravity

> READ THIS ENTIRE DOCUMENT before writing a single line of code.
> Execute steps in EXACT ORDER.
> Do NOT combine steps. Do NOT modify files not listed here.

---

## Overview

Phase 6 Step 1 built the booking flow: tourist selects date/guests → booking saved with status `"pending"` → redirected to `/my-trips`.

Phase 6 Step 2 inserts Stripe Checkout between the "Confirm" button and the booking confirmation. The new flow is:

```
Tourist fills form → clicks "Proceed to Payment"
  → POST /api/create-checkout-session
    → Booking created (status: "pending")
    → Stripe Checkout Session created (booking_id in metadata)
    → Returns { session_url }
  → Browser redirects to Stripe hosted checkout
  → Tourist pays
  → Stripe redirects to /payment/success?session_id=...
  → Stripe fires webhook → /api/stripe/webhook
    → Booking status updated to "confirmed"
  → Tourist sees confirmation page

If tourist cancels on Stripe:
  → Stripe redirects to /payment/cancel/<booking_id>
  → Pending booking is cancelled
  → Tourist offered option to retry
```

---

## Files Being Touched

| File | Action | Reason |
|---|---|---|
| `app.py` | ADD import + 4 routes | Stripe setup, checkout session, webhook, success, cancel |
| `templates/booking.html` | MODIFY JS only | Replace old API call with checkout session call |
| `templates/payment_success.html` | CREATE NEW | Success landing page |
| `templates/payment_cancel.html` | CREATE NEW | Cancel landing page |
| `.env` | ADD 3 keys | Stripe credentials |

**DO NOT touch:** `models.py`, `my_trips.html`, `guides.html`, or any other file.

---

## Prerequisites — Manual Steps Before Coding

These must be done by a human (not Antigravity) before running the code.

### A — Install Stripe Python library

Run in the project root terminal:
```bash
pip install stripe
```

Add `stripe` to `requirements.txt`.

### B — Create a Stripe account & get test keys

1. Go to https://dashboard.stripe.com and sign up / log in
2. Make sure you are in **Test Mode** (toggle at top-left of dashboard)
3. Go to **Developers → API Keys**
4. Copy:
   - **Publishable key** → starts with `pk_test_`
   - **Secret key** → starts with `sk_test_`

### C — Add keys to `.env`

Open `.env` and add these three lines:
```
STRIPE_SECRET_KEY=sk_test_YOUR_KEY_HERE
STRIPE_PUBLISHABLE_KEY=pk_test_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_WILL_BE_FILLED_IN_STEP_11
APP_BASE_URL=https://safaraone.onrender.com
```

> `APP_BASE_URL` is used to build redirect URLs. On Render, set this to your exact deployment URL.
> For local dev, leave it unset — the code will fall back to `request.host_url`.

### D — Add env vars to Render dashboard

In your Render service → **Environment**, add the same 4 keys from step C.
`STRIPE_WEBHOOK_SECRET` can be added after Step 11 below.

---

## STEP 1 — Add Stripe import and config to `app.py`

Find this block near the top of `app.py` (after the existing imports):
```python
from flask_cors import CORS
```

Add these two lines DIRECTLY AFTER it:
```python
import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
```

✅ Verify: `stripe.api_key` is set from the env variable, not hardcoded.

---

## STEP 2 — Add `/api/create-checkout-session` route to `app.py`

Find this line near the bottom of `app.py`:
```python
if __name__ == "__main__":
```

Insert all four new routes (Steps 2–5) ABOVE that line, in order. Start with this one:

```python
@app.route('/api/create-checkout-session', methods=['POST'])
@jwt_required()
def create_checkout_session():
    VALID_ITEM_TYPES = {"accommodation", "experience", "guide"}
    data = request.get_json()
    user_id = int(get_jwt_identity())

    item_type          = data.get("item_type")
    item_id            = data.get("item_id")
    num_guests         = int(data.get("num_guests", 1))
    total_price        = data.get("total_price")
    scheduled_date_str = data.get("scheduled_date")
    item_name          = data.get("item_name", "SafaraOne Booking")

    # Validation
    if not item_type or item_type not in VALID_ITEM_TYPES:
        return jsonify({"error": "Invalid or missing item_type"}), 400
    if not item_id:
        return jsonify({"error": "Missing item_id"}), 400
    if total_price is None or float(total_price) <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400

    scheduled_date = None
    if scheduled_date_str:
        try:
            scheduled_date = datetime.fromisoformat(scheduled_date_str)
        except ValueError:
            return jsonify({"error": "Invalid date format. Use YYYY-MM-DD"}), 400

    # Step 1: Create the booking with status "pending"
    try:
        booking = Booking(
            user_id=user_id,
            item_type=item_type,
            item_id=str(item_id),
            amount_usd=float(total_price),
            num_guests=num_guests,
            scheduled_date=scheduled_date,
            status="pending"
        )
        db.session.add(booking)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Could not create booking: {str(e)}"}), 500

    # Step 2: Build redirect URLs
    base = os.environ.get('APP_BASE_URL', request.host_url.rstrip('/'))
    success_url = f"{base}/payment/success?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url  = f"{base}/payment/cancel/{booking.id}"

    # Step 3: Create Stripe Checkout Session
    try:
        session = stripe.checkout.Session.create(
            payment_method_types=["card"],
            line_items=[{
                "price_data": {
                    "currency": "usd",
                    "unit_amount": int(float(total_price) * 100),  # Stripe uses cents
                    "product_data": {
                        "name": item_name,
                        "description": f"SafaraOne booking · {num_guests} guest(s) · {scheduled_date_str or 'TBD'}",
                    },
                },
                "quantity": 1,
            }],
            mode="payment",
            success_url=success_url,
            cancel_url=cancel_url,
            metadata={
                "booking_id": str(booking.id),
                "user_id":    str(user_id),
            }
        )
        return jsonify({"session_url": session.url, "booking_id": booking.id}), 200

    except stripe.error.StripeError as e:
        # Roll back the booking if Stripe session creation fails
        db.session.delete(booking)
        db.session.commit()
        return jsonify({"error": str(e.user_message)}), 500
```

✅ Verify: Booking is created BEFORE the Stripe session.
✅ Verify: `booking_id` and `user_id` are stored in Stripe metadata.
✅ Verify: `unit_amount` is in cents (multiply USD by 100).
✅ Verify: `{{CHECKOUT_SESSION_ID}}` uses double braces (literal in f-string, Stripe substitutes at runtime).
✅ Verify: On Stripe failure, the pending booking is rolled back.

---

## STEP 3 — Add `/api/stripe/webhook` route to `app.py`

Add this route DIRECTLY AFTER the one from Step 2:

```python
@app.route('/api/stripe/webhook', methods=['POST'])
def stripe_webhook():
    payload    = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = os.environ.get('STRIPE_WEBHOOK_SECRET')

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        return jsonify({"error": "Invalid payload"}), 400
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400

    if event['type'] == 'checkout.session.completed':
        session    = event['data']['object']
        booking_id = session.get('metadata', {}).get('booking_id')

        if booking_id:
            booking = db.session.get(Booking, int(booking_id))
            if booking and booking.status == 'pending':
                booking.status = 'confirmed'
                db.session.commit()

    return jsonify({"status": "ok"}), 200
```

✅ Verify: Route has NO `@jwt_required()` decorator — Stripe calls this, not the browser.
✅ Verify: Uses `request.get_data()` (raw bytes), NOT `request.get_json()`.
✅ Verify: Signature is verified before processing the event.
✅ Verify: Only processes `checkout.session.completed` events.
✅ Verify: Sets `booking.status = 'confirmed'` and commits.

---

## STEP 4 — Add `/payment/success` route to `app.py`

Add this route DIRECTLY AFTER the webhook route:

```python
@app.route('/payment/success')
@jwt_required(optional=True)
def payment_success():
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))

    session_id = request.args.get('session_id')
    booking_info = None

    if session_id:
        try:
            session = stripe.checkout.Session.retrieve(session_id)
            booking_id = session.get('metadata', {}).get('booking_id')
            if booking_id:
                b = db.session.get(Booking, int(booking_id))
                if b and b.user_id == int(user_id):
                    # Lookup item name
                    item_name = b.item_id
                    if b.item_type == 'guide':
                        item = db.session.get(Guide, b.item_id)
                        if item:
                            item_name = item.name
                    elif b.item_type == 'accommodation':
                        item = db.session.get(Accommodation, b.item_id)
                        if item:
                            item_name = item.name
                    elif b.item_type == 'experience':
                        item = db.session.get(Experience, b.item_id)
                        if item:
                            item_name = item.title

                    booking_info = {
                        'id':             b.id,
                        'item_name':      item_name,
                        'item_type':      b.item_type,
                        'amount_usd':     b.amount_usd,
                        'num_guests':     b.num_guests,
                        'scheduled_date': b.scheduled_date.strftime('%b %d, %Y') if b.scheduled_date else 'TBD',
                        'status':         b.status,
                    }
        except Exception:
            pass  # If anything fails, still show the success page without details

    return render_template('payment_success.html', booking=booking_info)
```

✅ Verify: Route is fully gated — unauthenticated users go to `/auth`.
✅ Verify: Retrieves booking details via the Stripe session metadata.
✅ Verify: Only shows booking if `b.user_id == int(user_id)` (no data leakage).
✅ Verify: If Stripe retrieval fails, page still renders without crashing.

---

## STEP 5 — Add `/payment/cancel/<booking_id>` route to `app.py`

Add this route DIRECTLY AFTER the success route:

```python
@app.route('/payment/cancel/<int:booking_id>')
@jwt_required(optional=True)
def payment_cancel(booking_id):
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))

    # Cancel the pending booking that was created before Stripe redirect
    booking = db.session.get(Booking, booking_id)
    if booking and booking.user_id == int(user_id) and booking.status == 'pending':
        booking.status = 'cancelled'
        db.session.commit()

    return render_template('payment_cancel.html')
```

✅ Verify: Only cancels if `booking.user_id == int(user_id)` — no cross-user cancellation.
✅ Verify: Only cancels if status is `"pending"` — won't touch confirmed or completed bookings.
✅ Verify: Renders `payment_cancel.html` after cleanup.

---

## STEP 6 — Modify `templates/booking.html`: Update the JavaScript

Open `booking.html`. Find the entire `confirmBooking` async function. It currently sends a POST to `/api/bookings`. Replace the ENTIRE function with this:

```javascript
  async function confirmBooking() {
    const dateVal = document.getElementById('trip-date').value;
    if (!dateVal) {
      showAlert('Please select a trip date before confirming.', 'error');
      return;
    }

    const btn = document.getElementById('confirm-btn');
    btn.disabled    = true;
    btn.textContent = 'Redirecting to payment…';

    try {
      const res = await fetch('/api/create-checkout-session', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_type:      ITEM_TYPE,
          item_id:        ITEM_ID,
          item_name:      ITEM_NAME,
          scheduled_date: dateVal,
          num_guests:     getGuests(),
          total_price:    getTotal()
        })
      });

      const data = await res.json();

      if (res.ok && data.session_url) {
        window.location.href = data.session_url;
      } else {
        showAlert(data.error || 'Something went wrong. Please try again.', 'error');
        btn.disabled    = false;
        btn.textContent = 'Proceed to Payment';
      }
    } catch (err) {
      showAlert('Network error — please check your connection and try again.', 'error');
      btn.disabled    = false;
      btn.textContent = 'Proceed to Payment';
    }
  }
```

Also find the `<script>` block at the top of the JS where Jinja injects constants. It currently has:
```javascript
const BASE_PRICE = {{ item_price }};
const ITEM_TYPE  = "{{ item_type }}";
const ITEM_ID    = "{{ item_id }}";
```

Add ONE line after these — the item name constant:
```javascript
const ITEM_NAME  = "{{ item_name }}";
```

Also update the confirm button text. Find:
```html
Confirm Booking
```
Inside the button element, change the text to:
```
Proceed to Payment →
```

✅ Verify: JS now calls `/api/create-checkout-session`, not `/api/bookings`.
✅ Verify: `item_name` is sent in the request body (used in Stripe line item description).
✅ Verify: On success, browser redirects to `data.session_url` (Stripe hosted checkout).
✅ Verify: `ITEM_NAME` constant is injected from Jinja `{{ item_name }}`.
✅ Verify: Button text reads "Proceed to Payment →".

---

## STEP 7 — Create `templates/payment_success.html`

Create a NEW file. Do not overwrite anything. Paste this content exactly:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Payment Confirmed · SafaraOne</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      min-height: 100vh;
      background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0d3b2e 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 2rem 1rem;
    }

    .card {
      background: rgba(255,255,255,0.07);
      backdrop-filter: blur(24px);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 28px;
      padding: 3rem 2.5rem;
      max-width: 460px;
      width: 100%;
      text-align: center;
      box-shadow: 0 32px 64px rgba(0,0,0,0.5);
      color: #fff;
    }

    .check-ring {
      width: 80px;
      height: 80px;
      border-radius: 50%;
      background: rgba(74,222,128,0.15);
      border: 2px solid rgba(74,222,128,0.4);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 1.5rem;
      font-size: 2.2rem;
      animation: popIn 0.5s cubic-bezier(0.34,1.56,0.64,1) both;
    }

    @keyframes popIn {
      from { transform: scale(0); opacity: 0; }
      to   { transform: scale(1); opacity: 1; }
    }

    h1 {
      font-size: 1.75rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      letter-spacing: -0.02em;
    }

    .subtitle {
      color: rgba(255,255,255,0.5);
      font-size: 0.95rem;
      margin-bottom: 2rem;
      line-height: 1.5;
    }

    .booking-summary {
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.08);
      border-radius: 16px;
      padding: 1.25rem 1.5rem;
      margin-bottom: 2rem;
      text-align: left;
    }

    .summary-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      padding: 0.45rem 0;
      font-size: 0.9rem;
      color: rgba(255,255,255,0.7);
    }
    .summary-row:not(:last-child) {
      border-bottom: 1px solid rgba(255,255,255,0.06);
    }
    .summary-row .label { color: rgba(255,255,255,0.45); }
    .summary-row .value { font-weight: 600; color: #fff; }
    .summary-row .value.green { color: #4ade80; }

    .badge-confirmed {
      display: inline-block;
      background: rgba(74,222,128,0.15);
      color: #4ade80;
      border: 1px solid rgba(74,222,128,0.3);
      border-radius: 20px;
      font-size: 0.72rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.07em;
      padding: 3px 10px;
    }

    .actions {
      display: flex;
      gap: 0.75rem;
      flex-direction: column;
    }

    .btn-primary {
      display: block;
      background: linear-gradient(135deg, #4ade80, #16a34a);
      color: #fff;
      text-decoration: none;
      padding: 0.85rem 1.5rem;
      border-radius: 14px;
      font-weight: 700;
      font-size: 0.95rem;
      transition: opacity 0.2s;
    }
    .btn-primary:hover { opacity: 0.88; }

    .btn-secondary {
      display: block;
      color: rgba(255,255,255,0.45);
      text-decoration: none;
      padding: 0.65rem;
      font-size: 0.88rem;
      transition: color 0.2s;
    }
    .btn-secondary:hover { color: #fff; }
  </style>
</head>
<body>

<div class="card">
  <div class="check-ring">✓</div>
  <h1>You're all set!</h1>
  <p class="subtitle">
    Your payment was processed successfully.<br>
    Your guide will be in touch before the trip.
  </p>

  {% if booking %}
  <div class="booking-summary">
    <div class="summary-row">
      <span class="label">Booking</span>
      <span class="value">#{{ booking.id }}</span>
    </div>
    <div class="summary-row">
      <span class="label">Item</span>
      <span class="value">{{ booking.item_name }}</span>
    </div>
    <div class="summary-row">
      <span class="label">Date</span>
      <span class="value">{{ booking.scheduled_date }}</span>
    </div>
    <div class="summary-row">
      <span class="label">Guests</span>
      <span class="value">{{ booking.num_guests }}</span>
    </div>
    <div class="summary-row">
      <span class="label">Total paid</span>
      <span class="value green">${{ "%.2f"|format(booking.amount_usd) }}</span>
    </div>
    <div class="summary-row">
      <span class="label">Status</span>
      <span class="value"><span class="badge-confirmed">{{ booking.status }}</span></span>
    </div>
  </div>
  {% endif %}

  <div class="actions">
    <a href="/my-trips" class="btn-primary">View My Trips →</a>
    <a href="/" class="btn-secondary">← Back to Home</a>
  </div>
</div>

</body>
</html>
```

✅ Verify: Template handles `{% if booking %}` gracefully — renders even if `booking` is None.
✅ Verify: Uses `booking.amount_usd` with `"%.2f"|format(...)` filter.
✅ Verify: Primary CTA leads to `/my-trips`.

---

## STEP 8 — Create `templates/payment_cancel.html`

Create a NEW file. Paste this content exactly:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Payment Cancelled · SafaraOne</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      min-height: 100vh;
      background: linear-gradient(135deg, #0a1628 0%, #1a2a4a 50%, #0d3b2e 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      font-family: 'Segoe UI', system-ui, sans-serif;
      padding: 2rem 1rem;
    }

    .card {
      background: rgba(255,255,255,0.07);
      backdrop-filter: blur(24px);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 28px;
      padding: 3rem 2.5rem;
      max-width: 420px;
      width: 100%;
      text-align: center;
      box-shadow: 0 32px 64px rgba(0,0,0,0.5);
      color: #fff;
    }

    .icon-ring {
      width: 72px;
      height: 72px;
      border-radius: 50%;
      background: rgba(251,191,36,0.12);
      border: 2px solid rgba(251,191,36,0.35);
      display: flex;
      align-items: center;
      justify-content: center;
      margin: 0 auto 1.5rem;
      font-size: 2rem;
    }

    h1 {
      font-size: 1.65rem;
      font-weight: 700;
      margin-bottom: 0.5rem;
      letter-spacing: -0.02em;
    }

    p {
      color: rgba(255,255,255,0.5);
      font-size: 0.93rem;
      line-height: 1.6;
      margin-bottom: 2rem;
    }

    .actions {
      display: flex;
      gap: 0.75rem;
      flex-direction: column;
    }

    .btn-primary {
      display: block;
      background: linear-gradient(135deg, #4ade80, #16a34a);
      color: #fff;
      text-decoration: none;
      padding: 0.85rem 1.5rem;
      border-radius: 14px;
      font-weight: 700;
      font-size: 0.95rem;
      transition: opacity 0.2s;
    }
    .btn-primary:hover { opacity: 0.88; }

    .btn-secondary {
      display: block;
      color: rgba(255,255,255,0.4);
      text-decoration: none;
      padding: 0.65rem;
      font-size: 0.88rem;
      transition: color 0.2s;
    }
    .btn-secondary:hover { color: #fff; }
  </style>
</head>
<body>

<div class="card">
  <div class="icon-ring">✕</div>
  <h1>Payment cancelled</h1>
  <p>
    No charge was made. Your booking has been cancelled.<br>
    You can try again anytime.
  </p>
  <div class="actions">
    <a href="/guides" class="btn-primary">Browse Guides →</a>
    <a href="/" class="btn-secondary">← Back to Home</a>
  </div>
</div>

</body>
</html>
```

✅ Verify: Page is static — no Jinja variables required.
✅ Verify: CTA leads to `/guides`.

---

## STEP 9 — Register Stripe Webhook on Render

This is a manual step done in the Stripe Dashboard, not in code.

1. Deploy the updated app to Render first (push to GitHub → Render auto-deploys)
2. Go to **Stripe Dashboard → Developers → Webhooks**
3. Click **"Add an endpoint"**
4. Endpoint URL: `https://safaraone.onrender.com/api/stripe/webhook`
5. Events to listen for: select **`checkout.session.completed`** only
6. Click **"Add endpoint"**
7. Copy the **Signing secret** (starts with `whsec_`)
8. In Render dashboard → Environment → set `STRIPE_WEBHOOK_SECRET` to this value
9. Trigger a Render redeploy so the new env var takes effect

**For local testing only (optional):**
Install Stripe CLI, then run:
```bash
stripe listen --forward-to localhost:5050/api/stripe/webhook
```
Copy the webhook secret it prints and set it as `STRIPE_WEBHOOK_SECRET` in your local `.env`.

---

## STEP 10 — Verification Checklist

Run through ALL tests in a private/incognito window after deployment.

**Test 1 — Auth gating on checkout**
- [ ] Without logging in, go to `/book/guide/<any-id>`
- [ ] Should redirect to `/auth` immediately

**Test 2 — Booking page still renders correctly**
- [ ] Log in as tourist
- [ ] Go to `/guides`, click Book on any guide
- [ ] Booking page shows guide name, image, price
- [ ] Button text reads "Proceed to Payment →"

**Test 3 — Stripe redirect**
- [ ] Select a date, set guests, click "Proceed to Payment →"
- [ ] Browser should redirect to a Stripe hosted checkout page
- [ ] Stripe page shows the guide name, correct USD amount

**Test 4 — Successful payment (use Stripe test card)**
- [ ] On Stripe checkout, use test card: `4242 4242 4242 4242`
- [ ] Any future expiry, any CVC, any zip
- [ ] Stripe should redirect to `/payment/success?session_id=...`
- [ ] Success page shows booking details (id, name, date, total)

**Test 5 — Webhook fires and updates booking**
- [ ] After successful payment, go to `/my-trips`
- [ ] The booking created by that payment should show status `confirmed` (not `pending`)
- [ ] If status is still `pending`: webhook has not fired yet — check Stripe Dashboard → Webhooks → recent events

**Test 6 — Cancelled payment**
- [ ] Go through booking flow, reach Stripe checkout
- [ ] Click the back arrow / cancel link on Stripe
- [ ] Should land on `/payment/cancel/<booking_id>`
- [ ] Page shows "Payment cancelled" message
- [ ] In database (or `/my-trips`), that booking should have status `cancelled`

**Test 7 — Declined card**
- [ ] On Stripe checkout, use test declined card: `4000 0000 0000 0002`
- [ ] Stripe shows a decline message — tourist remains on Stripe page
- [ ] No booking status changes until a successful payment

---

## What Is NOT in Phase 6 Step 2

- ❌ Stripe Connect (splitting payments to guide accounts) — Phase 7
- ❌ Refunds (Stripe refund API) — Phase 7
- ❌ Email receipts — Phase 7
- ❌ Webhook handling for `payment_intent.payment_failed` — Phase 7
- ❌ Accommodation or Experience book buttons — Phase 6 Step 3
