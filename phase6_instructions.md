# SafaraOne — Phase 6 Instructions
## Step-by-Step Implementation Guide for Antigravity

> READ `phase6_manual.md` FIRST.
> Then execute the steps below in EXACT ORDER.
> Do NOT combine steps. Do NOT skip steps. Do NOT modify files not listed here.

---

## STEP 1 — Update `app.py`: Replace `book_item` route

Find the existing `@app.route('/book/<item_type>/<item_id>')` route and replace it
entirely with this:

```python
@app.route('/book/<item_type>/<item_id>')
@jwt_required(optional=True)
def book_item(item_type, item_id):
    # Fully gated — unauthenticated users go to login immediately
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))

    item = None
    if item_type == 'guide':
        item = db.session.get(Guide, item_id)
    elif item_type == 'accommodation':
        item = db.session.get(Accommodation, item_id)
    elif item_type == 'experience':
        item = db.session.get(Experience, item_id)

    if not item:
        return redirect(url_for('index'))

    raw = item.to_dict()

    # Normalize price — each model uses a different field name
    if item_type == 'guide':
        display_price = raw.get('price_per_day_usd', 0)
        display_label = 'per day'
    elif item_type == 'accommodation':
        display_price = raw.get('price_per_night_usd', 0)
        display_label = 'per night'
    else:  # experience
        display_price = raw.get('price_usd', 0)
        display_label = 'per person'

    # Normalize name — Experience uses 'title', others use 'name'
    display_name = raw.get('name') or raw.get('title', 'Item')

    # Normalize image — Guide uses avatar_url, others use image_url
    display_image = raw.get('avatar_url') or raw.get('image_url', '')

    return render_template('booking.html',
        item_type=item_type,
        item_id=item_id,
        item_name=display_name,
        item_price=display_price,
        item_label=display_label,
        item_image=display_image
    )
```

✅ Verify: Route uses `@jwt_required(optional=True)` and manually checks identity.
✅ Verify: All three item types are handled.
✅ Verify: Template receives `item_name`, `item_price`, `item_label`, `item_image`, `item_type`, `item_id`.

---

## STEP 2 — Update `app.py`: Replace `api_create_booking` route

Find the existing `@app.route("/api/bookings", methods=["POST"])` route and replace
it entirely with this:

```python
@app.route("/api/bookings", methods=["POST"])
@jwt_required()
def api_create_booking():
    VALID_ITEM_TYPES = {"accommodation", "experience", "guide"}
    data = request.get_json()
    user_id = int(get_jwt_identity())

    item_type   = data.get("item_type")
    item_id     = data.get("item_id")
    num_guests  = int(data.get("num_guests", 1))
    total_price = data.get("total_price")
    scheduled_date_str = data.get("scheduled_date")

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
        return jsonify({"message": "Booking created", "booking_id": booking.id}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
```

✅ Verify: Accepts `total_price` from request JSON.
✅ Verify: Saves it as `amount_usd` in the Booking model.
✅ Verify: Returns 201 with `booking_id` on success.

---

## STEP 3 — Update `app.py`: Add `/my-trips` route

Find the line `if __name__ == "__main__":` at the bottom of `app.py`.
Insert this new route ABOVE that line:

```python
@app.route('/my-trips')
@jwt_required(optional=True)
def my_trips():
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))

    user = db.session.get(User, int(user_id))
    if not user:
        return redirect(url_for('auth'))

    bookings = Booking.query.filter_by(user_id=int(user_id)).order_by(Booking.booking_date.desc()).all()

    enriched = []
    for b in bookings:
        item_name  = b.item_id   # safe fallback
        item_image = ''
        if b.item_type == 'guide':
            item = db.session.get(Guide, b.item_id)
            if item:
                item_name  = item.name
                item_image = item.avatar_url or ''
        elif b.item_type == 'accommodation':
            item = db.session.get(Accommodation, b.item_id)
            if item:
                item_name  = item.name
                item_image = item.image_url or ''
        elif b.item_type == 'experience':
            item = db.session.get(Experience, b.item_id)
            if item:
                item_name  = item.title
                item_image = item.image_url or ''

        enriched.append({
            'id':             b.id,
            'item_type':      b.item_type,
            'item_name':      item_name,
            'item_image':     item_image,
            'amount_usd':     b.amount_usd,
            'num_guests':     b.num_guests,
            'status':         b.status,
            'scheduled_date': b.scheduled_date.strftime('%b %d, %Y') if b.scheduled_date else 'TBD',
            'booking_date':   b.booking_date.strftime('%b %d, %Y') if b.booking_date else ''
        })

    return render_template('my_trips.html', bookings=enriched, username=user.username)
```

✅ Verify: Route is placed before `if __name__ == "__main__":`.
✅ Verify: Fully gated — redirects to auth if no JWT identity.
✅ Verify: Enriches each booking with name and image from the correct model.

---

## STEP 4 — Create `templates/booking.html`

Create a NEW file at `templates/booking.html`. Do not overwrite any existing file.
Paste this content exactly:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Book · SafaraOne</title>
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

    .checkout-wrapper {
      width: 100%;
      max-width: 500px;
    }

    .back-link {
      display: inline-flex;
      align-items: center;
      gap: 0.4rem;
      color: rgba(255,255,255,0.5);
      text-decoration: none;
      font-size: 0.85rem;
      margin-bottom: 1.2rem;
      transition: color 0.2s;
    }
    .back-link:hover { color: #fff; }

    .card {
      background: rgba(255,255,255,0.06);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 24px;
      padding: 2rem;
      box-shadow: 0 32px 64px rgba(0,0,0,0.5);
      color: #fff;
    }

    .item-summary {
      display: flex;
      gap: 1rem;
      align-items: center;
      padding-bottom: 1.5rem;
      border-bottom: 1px solid rgba(255,255,255,0.1);
      margin-bottom: 1.8rem;
    }

    .item-thumb {
      width: 72px;
      height: 72px;
      border-radius: 14px;
      object-fit: cover;
      flex-shrink: 0;
      background: rgba(255,255,255,0.05);
    }

    .item-info { flex: 1; min-width: 0; }

    .item-badge {
      display: inline-block;
      background: rgba(74,222,128,0.15);
      color: #4ade80;
      border: 1px solid rgba(74,222,128,0.25);
      border-radius: 20px;
      padding: 2px 10px;
      font-size: 0.72rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 0.4rem;
    }

    .item-name {
      font-size: 1.1rem;
      font-weight: 700;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .item-base-price {
      font-size: 0.85rem;
      color: rgba(255,255,255,0.5);
      margin-top: 0.2rem;
    }

    .item-base-price strong { color: rgba(255,255,255,0.85); }

    .field { margin-bottom: 1.4rem; }

    .field label {
      display: block;
      font-size: 0.75rem;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: rgba(255,255,255,0.5);
      margin-bottom: 0.5rem;
    }

    .field input[type="date"] {
      width: 100%;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px;
      padding: 0.8rem 1rem;
      color: #fff;
      font-size: 0.95rem;
      outline: none;
      transition: border-color 0.2s;
      color-scheme: dark;
    }
    .field input[type="date"]:focus { border-color: #4ade80; }

    .guest-row {
      display: flex;
      align-items: center;
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.12);
      border-radius: 12px;
      overflow: hidden;
      width: fit-content;
    }

    .guest-btn {
      background: none;
      border: none;
      color: #fff;
      width: 44px;
      height: 44px;
      font-size: 1.3rem;
      cursor: pointer;
      transition: background 0.15s;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    .guest-btn:hover { background: rgba(74,222,128,0.15); }
    .guest-btn:disabled { opacity: 0.3; cursor: not-allowed; }

    .guest-count {
      width: 48px;
      text-align: center;
      font-size: 1rem;
      font-weight: 700;
      border-left: 1px solid rgba(255,255,255,0.1);
      border-right: 1px solid rgba(255,255,255,0.1);
      height: 44px;
      line-height: 44px;
    }

    .breakdown {
      background: rgba(0,0,0,0.25);
      border-radius: 14px;
      padding: 1.2rem 1.3rem;
      margin: 1.8rem 0;
    }

    .breakdown-row {
      display: flex;
      justify-content: space-between;
      align-items: center;
      font-size: 0.9rem;
      color: rgba(255,255,255,0.55);
      margin-bottom: 0.6rem;
    }
    .breakdown-row:last-child { margin-bottom: 0; }

    .breakdown-row.total {
      border-top: 1px solid rgba(255,255,255,0.1);
      padding-top: 0.8rem;
      margin-top: 0.6rem;
      color: #fff;
      font-size: 1.05rem;
      font-weight: 700;
    }

    .breakdown-row.total .amount {
      color: #4ade80;
      font-size: 1.2rem;
    }

    .alert {
      border-radius: 10px;
      padding: 0.8rem 1rem;
      font-size: 0.88rem;
      margin-bottom: 1.2rem;
      display: none;
    }
    .alert.error {
      background: rgba(239,68,68,0.15);
      border: 1px solid rgba(239,68,68,0.3);
      color: #fca5a5;
    }
    .alert.success {
      background: rgba(74,222,128,0.15);
      border: 1px solid rgba(74,222,128,0.3);
      color: #86efac;
    }

    .confirm-btn {
      width: 100%;
      padding: 1rem;
      background: linear-gradient(135deg, #4ade80, #16a34a);
      border: none;
      border-radius: 14px;
      color: #fff;
      font-size: 1rem;
      font-weight: 700;
      cursor: pointer;
      letter-spacing: 0.02em;
      transition: opacity 0.2s, transform 0.15s;
    }
    .confirm-btn:hover:not(:disabled) {
      opacity: 0.92;
      transform: translateY(-1px);
    }
    .confirm-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    .secure-note {
      text-align: center;
      font-size: 0.78rem;
      color: rgba(255,255,255,0.3);
      margin-top: 1rem;
    }
  </style>
</head>
<body>

<div class="checkout-wrapper">
  <a href="javascript:history.back()" class="back-link">← Back</a>

  <div class="card">

    <div class="item-summary">
      <img class="item-thumb"
           src="{{ item_image }}"
           alt="{{ item_name }}"
           onerror="this.src='https://images.unsplash.com/photo-1506929562872-bb421503ef21?w=200'">
      <div class="item-info">
        <div class="item-badge">{{ item_type }}</div>
        <div class="item-name">{{ item_name }}</div>
        <div class="item-base-price">
          <strong>${{ "%.2f"|format(item_price) }}</strong> {{ item_label }}
        </div>
      </div>
    </div>

    <div id="alertBox" class="alert"></div>

    <div class="field">
      <label>Trip Date</label>
      <input type="date" id="scheduledDate">
    </div>

    <div class="field">
      <label>Number of Guests</label>
      <div class="guest-row">
        <button class="guest-btn" id="btnMinus" onclick="changeGuests(-1)" disabled>−</button>
        <div class="guest-count" id="guestDisplay">1</div>
        <button class="guest-btn" onclick="changeGuests(1)">+</button>
      </div>
    </div>

    <div class="breakdown">
      <div class="breakdown-row">
        <span>${{ "%.2f"|format(item_price) }} × <span id="guestLabel">1</span> guest(s)</span>
        <span id="subtotalDisplay">${{ "%.2f"|format(item_price) }}</span>
      </div>
      <div class="breakdown-row">
        <span>SafaraOne service fee (5%)</span>
        <span id="feeDisplay">$0.00</span>
      </div>
      <div class="breakdown-row total">
        <span>Total</span>
        <span class="amount" id="totalDisplay">${{ "%.2f"|format(item_price) }}</span>
      </div>
    </div>

    <button class="confirm-btn" id="confirmBtn" onclick="confirmBooking()">
      Confirm Booking
    </button>

    <p class="secure-note">🔒 Secured by Stripe · SafaraOne</p>

  </div>
</div>

<script>
  const BASE_PRICE = {{ item_price }};
  const ITEM_TYPE  = "{{ item_type }}";
  const ITEM_ID    = "{{ item_id }}";
  const FEE_RATE   = 0.05;

  let guests = 1;

  // Set minimum date to today
  document.getElementById('scheduledDate').min = new Date().toISOString().split('T')[0];

  function changeGuests(delta) {
    guests = Math.max(1, Math.min(20, guests + delta));
    document.getElementById('guestDisplay').textContent = guests;
    document.getElementById('guestLabel').textContent   = guests;
    document.getElementById('btnMinus').disabled        = guests === 1;
    updateCosts();
  }

  function updateCosts() {
    const subtotal = BASE_PRICE * guests;
    const fee      = subtotal * FEE_RATE;
    const total    = subtotal + fee;
    document.getElementById('subtotalDisplay').textContent = '$' + subtotal.toFixed(2);
    document.getElementById('feeDisplay').textContent      = '$' + fee.toFixed(2);
    document.getElementById('totalDisplay').textContent    = '$' + total.toFixed(2);
  }

  function getTotal() {
    return parseFloat(((BASE_PRICE * guests) * (1 + FEE_RATE)).toFixed(2));
  }

  function showAlert(msg, type) {
    const box = document.getElementById('alertBox');
    box.textContent  = msg;
    box.className    = 'alert ' + type;
    box.style.display = 'block';
  }

  async function confirmBooking() {
    const date = document.getElementById('scheduledDate').value;
    if (!date) {
      showAlert('Please select a trip date before confirming.', 'error');
      return;
    }

    const btn = document.getElementById('confirmBtn');
    btn.disabled    = true;
    btn.textContent = 'Processing…';

    try {
      const res = await fetch('/api/bookings', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          item_type:      ITEM_TYPE,
          item_id:        ITEM_ID,
          scheduled_date: date,
          num_guests:     guests,
          total_price:    getTotal()
        })
      });

      const data = await res.json();

      if (res.ok) {
        showAlert('Booking confirmed! Redirecting to your trips…', 'success');
        setTimeout(() => { window.location.href = '/my-trips'; }, 1800);
      } else {
        showAlert(data.error || 'Something went wrong. Please try again.', 'error');
        btn.disabled    = false;
        btn.textContent = 'Confirm Booking';
      }
    } catch (err) {
      showAlert('Network error — please check your connection and try again.', 'error');
      btn.disabled    = false;
      btn.textContent = 'Confirm Booking';
    }
  }
</script>

</body>
</html>
```

✅ Verify: `BASE_PRICE`, `ITEM_TYPE`, `ITEM_ID` are injected from Jinja.
✅ Verify: AJAX sends `total_price` (not `amount_usd`) to `/api/bookings`.
✅ Verify: On success, redirects to `/my-trips`.

---

## STEP 5 — Create `templates/my_trips.html`

Create a NEW file at `templates/my_trips.html`. Paste this content exactly:

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>My Trips · SafaraOne</title>
  <style>
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    body {
      min-height: 100vh;
      background: linear-gradient(135deg, #0a1628, #1a2a4a, #0d3b2e);
      font-family: 'Segoe UI', system-ui, sans-serif;
      color: #fff;
      padding: 2rem 1rem;
    }

    .container { max-width: 800px; margin: 0 auto; }

    .back-link {
      display: inline-block;
      color: rgba(255,255,255,0.4);
      text-decoration: none;
      font-size: 0.85rem;
      margin-bottom: 1.5rem;
    }
    .back-link:hover { color: #fff; }

    .page-header { margin-bottom: 2rem; }
    .page-header h1 { font-size: 1.8rem; font-weight: 700; margin-bottom: 0.3rem; }
    .page-header p  { color: rgba(255,255,255,0.5); font-size: 0.95rem; }

    .empty-state {
      background: rgba(255,255,255,0.05);
      border: 1px dashed rgba(255,255,255,0.15);
      border-radius: 20px;
      padding: 3rem 2rem;
      text-align: center;
    }
    .empty-state .icon { font-size: 3rem; margin-bottom: 1rem; }
    .empty-state h3   { font-size: 1.2rem; margin-bottom: 0.5rem; }
    .empty-state p    { color: rgba(255,255,255,0.45); font-size: 0.9rem; margin-bottom: 1.5rem; }

    .btn-explore {
      display: inline-block;
      background: linear-gradient(135deg, #4ade80, #16a34a);
      color: #fff;
      padding: 0.75rem 1.8rem;
      border-radius: 12px;
      text-decoration: none;
      font-weight: 600;
      font-size: 0.9rem;
    }
    .btn-explore:hover { opacity: 0.88; }

    .trips-list { display: flex; flex-direction: column; gap: 1rem; }

    .trip-card {
      background: rgba(255,255,255,0.06);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 18px;
      padding: 1.2rem 1.4rem;
      display: flex;
      gap: 1.2rem;
      align-items: center;
      backdrop-filter: blur(12px);
    }

    .trip-thumb {
      width: 64px;
      height: 64px;
      border-radius: 12px;
      object-fit: cover;
      flex-shrink: 0;
      background: rgba(255,255,255,0.05);
    }

    .trip-info    { flex: 1; min-width: 0; }
    .trip-meta    { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 0.3rem; }
    .trip-name    { font-weight: 600; font-size: 1rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .trip-details { font-size: 0.82rem; color: rgba(255,255,255,0.45); margin-top: 0.25rem; }
    .trip-price   { font-size: 1.05rem; font-weight: 700; color: #4ade80; white-space: nowrap; flex-shrink: 0; }

    .badge {
      font-size: 0.7rem; font-weight: 700; text-transform: uppercase;
      letter-spacing: 0.06em; border-radius: 20px; padding: 2px 8px;
    }
    .badge-type     { background: rgba(74,222,128,0.12); color: #4ade80; border: 1px solid rgba(74,222,128,0.2); }
    .badge-pending  { background: rgba(251,191,36,0.15); color: #fbbf24; border: 1px solid rgba(251,191,36,0.25); }
    .badge-confirmed{ background: rgba(74,222,128,0.15); color: #4ade80; border: 1px solid rgba(74,222,128,0.25); }
    .badge-completed{ background: rgba(99,102,241,0.15); color: #a5b4fc; border: 1px solid rgba(99,102,241,0.25); }
    .badge-cancelled{ background: rgba(239,68,68,0.12);  color: #fca5a5; border: 1px solid rgba(239,68,68,0.2); }
  </style>
</head>
<body>
<div class="container">

  <a href="/" class="back-link">← Back to Home</a>

  <div class="page-header">
    <h1>My Trips</h1>
    <p>Welcome back, {{ username }}. All your SafaraOne bookings in one place.</p>
  </div>

  {% if not bookings %}
  <div class="empty-state">
    <div class="icon">🧭</div>
    <h3>No trips yet</h3>
    <p>Your confirmed bookings will appear here once you book a guide, stay, or experience.</p>
    <a href="/guides" class="btn-explore">Explore Guides</a>
  </div>

  {% else %}
  <div class="trips-list">
    {% for b in bookings %}
    <div class="trip-card">
      <img class="trip-thumb"
           src="{{ b.item_image or 'https://images.unsplash.com/photo-1506929562872-bb421503ef21?w=200' }}"
           alt="{{ b.item_name }}"
           onerror="this.src='https://images.unsplash.com/photo-1506929562872-bb421503ef21?w=200'">
      <div class="trip-info">
        <div class="trip-meta">
          <span class="badge badge-type">{{ b.item_type }}</span>
          <span class="badge badge-{{ b.status }}">{{ b.status }}</span>
        </div>
        <div class="trip-name">{{ b.item_name }}</div>
        <div class="trip-details">
          📅 {{ b.scheduled_date }} &nbsp;·&nbsp;
          👥 {{ b.num_guests }} guest(s) &nbsp;·&nbsp;
          Booked {{ b.booking_date }}
        </div>
      </div>
      <div class="trip-price">${{ "%.2f"|format(b.amount_usd) }}</div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

</div>
</body>
</html>
```

✅ Verify: Template uses `b.item_name`, `b.item_image`, `b.amount_usd` (from enriched dict in route).
✅ Verify: Status badge CSS classes match: `badge-pending`, `badge-confirmed`, `badge-completed`, `badge-cancelled`.

---

## STEP 6 — Update `templates/guides.html`: Fix the Book button

Open `guides.html`. Find the Book button inside the guide card loop.
It currently has `href="#"`. Replace it with:

```html
href="{{ url_for('book_item', item_type='guide', item_id=guide.id) }}"
```

> ⚠️ IMPORTANT: The loop variable must match what is in your template.
> Open `guides.html` first and check what the `{% for ... %}` loop variable is called.
> If the loop says `{% for g in guides %}` then use `g.id`, not `guide.id`.
> If the loop says `{% for guide in guides %}` then use `guide.id`.

✅ Verify: Button href is dynamic, not `#`.
✅ Verify: `url_for('book_item', ...)` uses the correct loop variable name.

---

## STEP 7 — Manual Verification Checklist

Run through these checks after all steps are complete:

**Test 1 — Auth gating**
- [ ] Open a private/incognito window
- [ ] Navigate to `/book/guide/<any-guide-id>`
- [ ] You should be redirected to `/auth` immediately

**Test 2 — Booking page renders**
- [ ] Log in as a tourist
- [ ] Go to `/guides`
- [ ] Click the Book button on any guide
- [ ] Booking page should show the guide's name, image, and price

**Test 3 — Live price calculation**
- [ ] On the booking page, click the `+` guest button
- [ ] Subtotal, fee, and total should update instantly without page reload
- [ ] Minus button should be disabled at 1 guest

**Test 4 — Date validation**
- [ ] Click "Confirm Booking" without selecting a date
- [ ] Error message should appear: "Please select a trip date before confirming."

**Test 5 — Successful booking**
- [ ] Select a date, set guests, click Confirm
- [ ] Success message should appear
- [ ] After 1.8 seconds, page redirects to `/my-trips`
- [ ] New booking should appear in the list with status "pending"

**Test 6 — My Trips empty state**
- [ ] Log in as a brand new tourist with no bookings
- [ ] Navigate to `/my-trips`
- [ ] Should see the "No trips yet" empty state with Explore Guides button

---

## STOP HERE

Do not proceed to Phase 6 Step 2 (Stripe integration) until all 6 tests above pass.
