# SafaraOne — Phase 6 Step 2 (Flutterwave Edition)
## Payment Integration: Instructions for Antigravity

> READ THIS ENTIRE DOCUMENT before writing a single line of code.
> Execute steps in EXACT ORDER.
> Do NOT combine steps. Do NOT modify files not listed here.

---

## What Is Changing vs What Is Staying

### STAYING exactly as-is (do not touch):
- `templates/payment_success.html` — already created, no changes
- `templates/payment_cancel.html` — already created, no changes
- `templates/booking.html` — already updated in Stripe step, no further changes needed
- All other templates, models, services

### BEING REPLACED/REMOVED (the Stripe code that was added):
- `import stripe` and `stripe.api_key = ...` in `app.py`
- The `/api/create-checkout-session` route (Stripe version)
- The `/api/stripe/webhook` route
- The `/payment/success` route
- The `/payment/cancel/<booking_id>` route

### BEING ADDED (the Flutterwave replacements):
- `import requests` in `app.py`
- New `/api/create-checkout-session` route (Flutterwave version, same URL, different code)
- New `/api/flw/webhook` route
- New `/payment/callback` route (handles BOTH success and cancel — one route instead of two)

---

## Why One Callback Route Instead of Two

Stripe lets you set separate success and cancel URLs.
Flutterwave uses a single `redirect_url` and adds `?status=successful` or `?status=cancelled`
to it when redirecting the tourist back. So one route reads that status and decides
which template to show. Cleaner, fewer routes.

---

## How the tx_ref Works (Read This — It Is Important)

Flutterwave requires a unique transaction reference called `tx_ref` for every payment.
We generate it like this:

```
saf-{booking_id}-{8_random_characters}
```

Example: `saf-7-a3f9b2c1`

This is important because when Flutterwave redirects the tourist back to our site,
it includes this `tx_ref` in the URL. We split it on `-` to extract the booking_id:

```
"saf-7-a3f9b2c1".split("-") → ["saf", "7", "a3f9b2c1"]
                                              ↑
                                       this is booking_id
```

We also store `booking_id` in the Flutterwave `meta` field as a backup.
When we verify the payment with Flutterwave's API, meta comes back in the response,
giving us a second reliable way to find the booking. Both methods are used.

---

## Files Being Touched

| File | Action | What Exactly |
|---|---|---|
| `app.py` | REMOVE 1 import, REMOVE 4 routes, ADD 1 import, ADD 3 routes | Stripe out, Flutterwave in |
| `requirements.txt` | REMOVE `stripe`, ADD `requests` | Dependency swap |
| `.env` | REMOVE Stripe keys, ADD Flutterwave keys | Credentials swap |

**DO NOT touch:** any template files, `models.py`, `services/`, or anything else.

---

## Prerequisites — Manual Steps Before Coding

These steps must be done by a human. Explain this to the user.

### A — Create a Flutterwave account and get test keys

**Tell the user to do this:**

1. Go to **dashboard.flutterwave.com** and sign up for a free account
2. Verify your email when they send a confirmation link
3. Once inside the dashboard, look at the top of the page — make sure it says **Test Mode**.
   There is usually a toggle switch. Turn it ON so you are in test mode (no real money moves)
4. In the left sidebar, click **Settings**
5. Then click **API Keys**
6. You will see two keys on that page:
   - **Public Key** — starts with `FLWPUBK_TEST-`  → copy it
   - **Secret Key** — starts with `FLWSECK_TEST-` → copy it
7. Keep this tab open, you will need these keys in the next step

### B — Choose your webhook secret

Flutterwave's webhook verification works differently from Stripe.
**You create the secret yourself** — it can be any string, like a strong password.
It just needs to be the same string in both your `.env` file and the Flutterwave dashboard.

Example of a good webhook secret: `safaraone-flw-hook-2026`

Pick one now and remember it. You will use it in Step C and again in Step 9 (dashboard setup).

### C — Update your `.env` file

Open the `.env` file in the project root. **Remove** these lines that were added for Stripe:
```
STRIPE_SECRET_KEY=...
STRIPE_PUBLISHABLE_KEY=...
STRIPE_WEBHOOK_SECRET=...
```

**Add** these lines instead:
```
FLW_SECRET_KEY=FLWSECK_TEST-paste_your_key_here
FLW_PUBLIC_KEY=FLWPUBK_TEST-paste_your_key_here
FLW_WEBHOOK_SECRET=safaraone-flw-hook-2026
APP_BASE_URL=https://safaraone.onrender.com
```

> Note: `APP_BASE_URL` may already be in your `.env` from the Stripe step. If so, leave it as-is.

### D — Update Render environment variables

In Render dashboard → your SafaraOne service → **Environment**:
- Remove the three Stripe keys
- Add the three Flutterwave keys with the same values as your `.env`
- Leave `APP_BASE_URL` as-is if it is already there

---

## STEP 1 — Update `requirements.txt`

Find this line:
```
stripe
```

Replace it with:
```
requests
```

> Note: `requests` is almost certainly already installed in your Python environment,
> but it must be listed in `requirements.txt` so Render installs it on deploy.
> If `stripe` is not in `requirements.txt`, simply add `requests` on its own line.

✅ Verify: `stripe` is removed. `requests` is present.

---

## STEP 2 — Remove Stripe import from `app.py`

Find these two lines that were added in the Stripe step:
```python
import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
```

Delete both lines entirely.

Then find this line near the top of `app.py`:
```python
from flask_cors import CORS
```

Add this line DIRECTLY AFTER it:
```python
import requests
```

✅ Verify: `import stripe` is gone.
✅ Verify: `stripe.api_key` line is gone.
✅ Verify: `import requests` is present after `from flask_cors import CORS`.

---

## STEP 3 — Remove all four Stripe routes from `app.py`

Find and DELETE the following four complete route functions.
Delete everything from the `@app.route(...)` decorator down to and including
the last line of each function body. Do not leave any blank `@app.route` decorators behind.

**Route 1 to delete** — find by its decorator:
```python
@app.route('/api/create-checkout-session', methods=['POST'])
```
Delete this entire function.

**Route 2 to delete** — find by its decorator:
```python
@app.route('/api/stripe/webhook', methods=['POST'])
```
Delete this entire function.

**Route 3 to delete** — find by its decorator:
```python
@app.route('/payment/success')
```
Delete this entire function.

**Route 4 to delete** — find by its decorator:
```python
@app.route('/payment/cancel/<int:booking_id>')
```
Delete this entire function.

✅ Verify: All four decorators are gone from `app.py`.
✅ Verify: No orphaned code is left behind from these functions.
✅ Verify: The rest of `app.py` is intact — `my_trips`, `guide_dashboard`, etc. are untouched.

---

## STEP 4 — Add the new `/api/create-checkout-session` route

Find this line near the bottom of `app.py`:
```python
if __name__ == "__main__":
```

Insert all three new routes (Steps 4, 5, 6) ABOVE that line. Start with this one:

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

    # Step 1: Look up the tourist's email for Flutterwave customer object
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404

    # Step 2: Create the booking with status "pending"
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

    # Step 3: Build the unique transaction reference
    # Format: saf-{booking_id}-{8 random hex chars}
    # We encode booking_id here so we can extract it from the redirect URL later
    tx_ref = f"saf-{booking.id}-{uuid.uuid4().hex[:8]}"

    # Step 4: Build redirect URL — single URL, Flutterwave adds ?status=... to it
    base        = os.environ.get('APP_BASE_URL', request.host_url.rstrip('/'))
    redirect_url = f"{base}/payment/callback"

    # Step 5: Call Flutterwave API to create a hosted checkout link
    flw_payload = {
        "tx_ref":       tx_ref,
        "amount":       float(total_price),
        "currency":     "USD",
        "redirect_url": redirect_url,
        "customer": {
            "email": user.email,
            "name":  user.username,
        },
        "customizations": {
            "title":       "SafaraOne",
            "description": f"{item_name} · {num_guests} guest(s) · {scheduled_date_str or 'TBD'}",
        },
        "meta": {
            "booking_id": str(booking.id),
            "user_id":    str(user_id),
        }
    }

    flw_headers = {
        "Authorization": f"Bearer {os.environ.get('FLW_SECRET_KEY')}",
        "Content-Type":  "application/json"
    }

    try:
        flw_response = requests.post(
            "https://api.flutterwave.com/v3/payments",
            json=flw_payload,
            headers=flw_headers,
            timeout=15
        )
        flw_data = flw_response.json()

        if flw_data.get("status") == "success":
            session_url = flw_data["data"]["link"]
            return jsonify({"session_url": session_url, "booking_id": booking.id}), 200
        else:
            # Flutterwave rejected the request — roll back the pending booking
            db.session.delete(booking)
            db.session.commit()
            error_msg = flw_data.get("message", "Flutterwave error. Check your API key.")
            return jsonify({"error": error_msg}), 500

    except requests.exceptions.Timeout:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({"error": "Payment gateway timed out. Please try again."}), 504

    except Exception as e:
        db.session.delete(booking)
        db.session.commit()
        return jsonify({"error": f"Payment error: {str(e)}"}), 500
```

✅ Verify: `tx_ref` follows format `saf-{booking.id}-{8hex}`.
✅ Verify: `meta` contains `booking_id` as a string.
✅ Verify: Single `redirect_url` pointing to `/payment/callback` (no success/cancel split).
✅ Verify: If Flutterwave call fails for any reason, the pending booking is deleted.
✅ Verify: Response returns `{"session_url": "...", "booking_id": ...}` on success — same shape as the old Stripe route.
✅ Verify: `user.email` is used (requires `user` lookup before booking creation).

---

## STEP 5 — Add the `/api/flw/webhook` route

Add this route DIRECTLY AFTER the one from Step 4:

```python
@app.route('/api/flw/webhook', methods=['POST'])
def flw_webhook():
    # Flutterwave verification: compare verif-hash header to our secret
    # The secret is a string WE chose and set in both .env and Flutterwave dashboard
    flw_hash      = request.headers.get('verif-hash')
    expected_hash = os.environ.get('FLW_WEBHOOK_SECRET')

    if not flw_hash or flw_hash != expected_hash:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()

    if not data:
        return jsonify({"error": "No payload"}), 400

    # Only process completed charge events
    if data.get('event') == 'charge.completed':
        payment_data = data.get('data', {})

        if payment_data.get('status') == 'successful':
            tx_ref = payment_data.get('tx_ref', '')
            meta   = payment_data.get('meta', {})

            # Try to get booking_id from meta first (most reliable)
            booking_id = meta.get('booking_id')

            # Fallback: parse booking_id from tx_ref (format: saf-{id}-{random})
            if not booking_id:
                parts = tx_ref.split('-')
                if len(parts) >= 2:
                    try:
                        booking_id = parts[1]
                    except (IndexError, ValueError):
                        pass

            if booking_id:
                booking = db.session.get(Booking, int(booking_id))
                # Guard: only confirm if still pending (webhook may fire after callback)
                if booking and booking.status == 'pending':
                    booking.status = 'confirmed'
                    db.session.commit()

    # Always return 200 — Flutterwave retries if it gets anything else
    return jsonify({"status": "ok"}), 200
```

✅ Verify: Route has NO `@jwt_required()` — Flutterwave calls this, not the tourist's browser.
✅ Verify: Uses `request.headers.get('verif-hash')` — lowercase, exact spelling.
✅ Verify: Compares header value directly to `FLW_WEBHOOK_SECRET` env variable.
✅ Verify: Only processes `charge.completed` events with `status == "successful"`.
✅ Verify: The `if booking.status == 'pending'` guard prevents double-confirmation if both webhook and callback fire.
✅ Verify: Always returns 200 at the end (important — Flutterwave will retry indefinitely if it gets a non-200).

---

## STEP 6 — Add the `/payment/callback` route

Add this route DIRECTLY AFTER the webhook route from Step 5:

```python
@app.route('/payment/callback')
def payment_callback():
    status         = request.args.get('status', '')
    tx_ref         = request.args.get('tx_ref', '')
    transaction_id = request.args.get('transaction_id', '')

    # Extract booking_id from tx_ref
    # tx_ref format: "saf-{booking_id}-{random}"
    # Example:       "saf-7-a3f9b2c1"
    booking_id = None
    parts = tx_ref.split('-')
    if len(parts) >= 2:
        try:
            booking_id = int(parts[1])
        except (ValueError, IndexError):
            pass

    # ── CANCELLED OR ABANDONED ──────────────────────────────────────────────
    # Flutterwave sets status="cancelled" when tourist clicks back/cancel
    # If transaction_id is missing, the payment never completed
    if status == 'cancelled' or not transaction_id:
        if booking_id:
            booking = db.session.get(Booking, booking_id)
            if booking and booking.status == 'pending':
                booking.status = 'cancelled'
                db.session.commit()
        return render_template('payment_cancel.html')

    # ── SUCCESSFUL PAYMENT ──────────────────────────────────────────────────
    # IMPORTANT: Never trust the ?status=successful query param alone.
    # Always verify the transaction_id with the Flutterwave API.
    # This prevents anyone from manually visiting the success URL to fake a payment.

    if status == 'successful' and transaction_id:
        try:
            verify_url = f"https://api.flutterwave.com/v3/transactions/{transaction_id}/verify"
            flw_headers = {
                "Authorization": f"Bearer {os.environ.get('FLW_SECRET_KEY')}",
                "Content-Type":  "application/json"
            }
            verify_resp = requests.get(verify_url, headers=flw_headers, timeout=10)
            verify_data = verify_resp.json()

            # Check both outer status and inner payment status
            if (verify_data.get('status') == 'success' and
                    verify_data.get('data', {}).get('status') == 'successful'):

                # Get booking_id from verified meta (more reliable than tx_ref parsing)
                meta_booking_id = verify_data['data'].get('meta', {}).get('booking_id')
                final_booking_id = meta_booking_id or booking_id

                booking_info = None

                if final_booking_id:
                    booking = db.session.get(Booking, int(final_booking_id))

                    # Confirm if still pending
                    # (webhook may have already confirmed it — that is fine)
                    if booking and booking.status == 'pending':
                        booking.status = 'confirmed'
                        db.session.commit()

                    # Build booking summary for the success template
                    if booking:
                        item_name = booking.item_id  # safe fallback
                        if booking.item_type == 'guide':
                            item = db.session.get(Guide, booking.item_id)
                            if item:
                                item_name = item.name
                        elif booking.item_type == 'accommodation':
                            item = db.session.get(Accommodation, booking.item_id)
                            if item:
                                item_name = item.name
                        elif booking.item_type == 'experience':
                            item = db.session.get(Experience, booking.item_id)
                            if item:
                                item_name = item.title

                        booking_info = {
                            'id':             booking.id,
                            'item_name':      item_name,
                            'item_type':      booking.item_type,
                            'amount_usd':     booking.amount_usd,
                            'num_guests':     booking.num_guests,
                            'scheduled_date': booking.scheduled_date.strftime('%b %d, %Y') if booking.scheduled_date else 'TBD',
                            'status':         booking.status,
                        }

                return render_template('payment_success.html', booking=booking_info)

        except requests.exceptions.Timeout:
            # Flutterwave API timed out — show cancel page to be safe
            pass
        except Exception:
            pass

    # ── FALLBACK ────────────────────────────────────────────────────────────
    # Anything unexpected (bad status, verification failed, exception) → cancel page
    return render_template('payment_cancel.html')
```

✅ Verify: No `@jwt_required()` decorator — tourist may have an expired session after paying, that must not block them seeing the success page.
✅ Verify: Cancelled path cancels the pending booking before rendering `payment_cancel.html`.
✅ Verify: Successful path VERIFIES with Flutterwave API — never trusts URL params alone.
✅ Verify: Verification checks BOTH `verify_data['status'] == 'success'` AND `verify_data['data']['status'] == 'successful'`.
✅ Verify: `if booking and booking.status == 'pending'` guard prevents double-confirmation.
✅ Verify: `booking_info` is built with the exact same field names that `payment_success.html` expects.
✅ Verify: Any exception or verification failure falls through to the cancel page.

---

## STEP 7 — Register the Webhook on Flutterwave Dashboard

**Tell the user to do this after deploying to Render:**

1. Go to your **Flutterwave dashboard** (dashboard.flutterwave.com)
2. In the left sidebar, click **Settings**
3. Click **Webhooks**
4. In the field labelled **"Webhook URL"**, paste:
   ```
   https://safaraone.onrender.com/api/flw/webhook
   ```
5. In the field labelled **"Secret Hash"**, paste the same webhook secret
   you added to your `.env` file in Prerequisite B — for example:
   ```
   safaraone-flw-hook-2026
   ```
6. Click **Save**

That's it. Flutterwave will now send a notification to that URL every time
a payment completes, and your server will use the secret to confirm it is genuine.

---

## STEP 8 — Deploy to Render

**Tell the user to do this:**

1. Commit all code changes to GitHub:
   ```bash
   git add .
   git commit -m "Phase 6 Step 2: Flutterwave payment integration"
   git push
   ```
2. Render will automatically detect the push and start a new deployment
3. Watch the Render logs — look for any errors about `requests`, imports, or missing env vars
4. Once the deployment shows **"Live"**, proceed to testing

---

## STEP 9 — Verification Checklist

Run every one of these tests after deployment. Do them in order.

---

**Test 1 — Auth gate still works**

- Open a private/incognito browser window (no login)
- Go to `https://safaraone.onrender.com/book/guide/<any-guide-id>`
- You should be immediately redirected to `/auth`
- ✅ Pass / ❌ Fail

---

**Test 2 — Booking page still renders correctly**

- Log in as a tourist
- Go to `/guides`
- Click the Book button on any guide
- The booking page should show: guide name, image, price, date picker, guest counter
- The button should read **"Proceed to Payment →"**
- ✅ Pass / ❌ Fail

---

**Test 3 — Flutterwave redirect works**

- On the booking page, select a date, leave guests at 1
- Click **"Proceed to Payment →"**
- Your browser should leave SafaraOne and land on a Flutterwave hosted payment page
  (URL will be `checkout.flutterwave.com/...`)
- The page should show the guide name, USD amount, and SafaraOne as the merchant name
- ✅ Pass / ❌ Fail

If the button spins but does not redirect — open browser DevTools (F12) → Console tab → look for the error message from the API response. Most likely cause: `FLW_SECRET_KEY` env var is missing or incorrect.

---

**Test 4 — Successful payment with Flutterwave test card**

On the Flutterwave checkout page, use these exact test card details:

```
Card number:  5531 8866 5214 2950
Expiry:        09/32
CVV:           564
PIN:           3310
OTP:           12345
```

After entering the OTP, Flutterwave redirects you back to SafaraOne.

- You should land on `/payment/callback?status=successful&...`
- The page should show `payment_success.html` with booking details
- The booking status shown should be **confirmed**
- ✅ Pass / ❌ Fail

---

**Test 5 — Booking appears as confirmed in My Trips**

- After the successful payment from Test 4, go to `/my-trips`
- The booking just created should appear in the list
- Its status badge should show **confirmed** (green), not pending
- ✅ Pass / ❌ Fail

If status is still **pending**: the webhook has not fired yet OR there is a mismatch in `FLW_WEBHOOK_SECRET`. Check Flutterwave dashboard → Settings → Webhooks → look at recent delivery attempts.

---

**Test 6 — Cancelled payment**

- Go through the booking flow again until you reach the Flutterwave checkout page
- Click the **back arrow** or **"Cancel"** link on the Flutterwave page
- You should be redirected back to `/payment/callback?status=cancelled&...`
- The page should show `payment_cancel.html`
- Go to `/my-trips` — the booking created for this attempt should show status **cancelled**
- ✅ Pass / ❌ Fail

---

**Test 7 — Security: no fake success**

This tests that the verification step is working.

- In your browser address bar, manually type:
  ```
  https://safaraone.onrender.com/payment/callback?status=successful&tx_ref=saf-1-fake&transaction_id=00000000
  ```
- You should land on `payment_cancel.html` (not the success page)
- This confirms we are verifying with Flutterwave and not trusting URL params alone
- ✅ Pass / ❌ Fail

---

## What Is NOT in Phase 6 Step 2

- ❌ Mobile money (M-Pesa, Tigo Pesa) — Flutterwave supports these but they require extra
  form fields and OTP flows. Phase 7 addition.
- ❌ TZS currency — currently charges in USD. Can be switched by changing `"currency": "USD"`
  to `"currency": "TZS"` and adjusting amounts. Phase 7 decision.
- ❌ Refunds via Flutterwave API — Phase 7
- ❌ Email receipts — Phase 7
- ❌ Accommodation and Experience book buttons — Phase 6 Step 3
