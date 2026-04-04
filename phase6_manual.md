# SafaraOne — Phase 6 Manual
## The Booking & Payment Engine: Architecture Reference

> This document is the authoritative technical reference for Phase 6, Step 1.
> Read this BEFORE touching any code. It explains what exists, what is changing, and why.

---

## 1. What Phase 6 Builds

Phase 6 introduces the core booking flow for tourists. A tourist can:
1. Browse guides at `/guides`
2. Click "Book" on a guide card → land on `/book/guide/<id>`
3. Select a date and number of guests
4. See a live price calculation
5. Click "Confirm Booking" → booking saved to database → redirected to `/my-trips`

---

## 2. Files Being Touched

| File | Action | Reason |
|---|---|---|
| `app.py` | MODIFY 2 routes, ADD 1 route | Fix `book_item`, fix `api_create_booking`, add `/my-trips` |
| `templates/booking.html` | CREATE NEW | The checkout UI |
| `templates/my_trips.html` | CREATE NEW | Tourist booking history (placeholder) |
| `templates/guides.html` | MODIFY | Update Book button href |

**DO NOT touch any other file.**

---

## 3. Database Model Reference

These are the EXACT field names from `models.py`. Do not guess or rename them.

### Guide
```
id                → String (primary key, e.g. "guide-3")
name              → String
avatar_url        → String  ← image field for guides (NOT profile_photo_url, NOT image_url)
price_per_day_usd → Float   ← price field for guides
```

### Accommodation
```
id                  → String
name                → String
image_url           → String  ← image field
price_per_night_usd → Float   ← price field
```

### Experience
```
id        → String
title     → String  ← name field for experiences (NOT name)
image_url → String  ← image field
price_usd → Float   ← price field
```

### Booking
```
id             → Integer (auto)
user_id        → Integer (FK to User)
item_type      → String  ("guide", "accommodation", "experience")
item_id        → String
amount_usd     → Float   ← this is what total_price from the frontend saves into
num_guests     → Integer
status         → String  (default: "pending")
scheduled_date → DateTime
booking_date   → DateTime (auto)
```

---

## 4. Critical Normalization Logic

Because each model uses different field names for price and image, the `book_item`
route in `app.py` MUST normalize them before passing to the template.

The template receives ONLY these clean variables — it never accesses raw model fields:

| Template Variable | Guide source | Accommodation source | Experience source |
|---|---|---|---|
| `item_name` | `name` | `name` | `title` |
| `item_price` | `price_per_day_usd` | `price_per_night_usd` | `price_usd` |
| `item_image` | `avatar_url` | `image_url` | `image_url` |
| `item_label` | `"per day"` | `"per night"` | `"per person"` |
| `item_type` | passed from URL | passed from URL | passed from URL |
| `item_id` | passed from URL | passed from URL | passed from URL |

---

## 5. API Endpoint Contract

### POST `/api/bookings`

**Request JSON (sent from booking.html frontend):**
```json
{
  "item_type":      "guide",
  "item_id":        "guide-3",
  "scheduled_date": "2026-05-20",
  "num_guests":     2,
  "total_price":    300.00
}
```

**What the backend saves to the Booking model:**
```
item_type      = data["item_type"]
item_id        = str(data["item_id"])
amount_usd     = float(data["total_price"])   ← NOTE: frontend sends "total_price", saved as "amount_usd"
num_guests     = int(data["num_guests"])
scheduled_date = parsed from "scheduled_date"
user_id        = from JWT identity
status         = "pending"  (default)
```

**Success Response (201):**
```json
{ "message": "Booking created", "booking_id": 7 }
```

**Error Responses:**
- 400 — missing/invalid item_type
- 400 — missing item_id
- 400 — total_price is 0 or missing
- 400 — invalid date format
- 500 — database error

---

## 6. Authentication Rules

- `/book/<item_type>/<item_id>` — FULLY GATED. If `get_jwt_identity()` is None → immediately `redirect(url_for('auth'))`. Unauthenticated users never see the booking page.
- `POST /api/bookings` — uses `@jwt_required()` (hard, not optional). Returns 401 JSON if not authenticated.
- `/my-trips` — FULLY GATED. Same rule as `book_item`. Redirect to `/auth` if not logged in.

---

## 7. Price Calculation Logic (Frontend JavaScript)

```
subtotal = BASE_PRICE × num_guests
fee      = subtotal × 0.05          (5% SafaraOne service fee, displayed to user)
total    = subtotal + fee
```

`total` is what gets sent to the backend as `total_price`.

`BASE_PRICE` is injected from the Jinja template as a JavaScript constant:
```javascript
const BASE_PRICE = {{ item_price }};
```

---

## 8. Tourist Redirect After Booking

- On successful booking (API returns 201) → redirect to `/my-trips`
- `/my-trips` shows all bookings for the logged-in tourist, fetched live from the DB
- `/my-trips` enriches each booking with the item's display name and image
- If no bookings exist → show empty state with link to `/guides`

---

## 9. The `/dashboard/bookings` Route — DO NOT USE FOR TOURISTS

The existing `/dashboard/bookings` route in `app.py` is for **guides only**.
It filters by `user.role != 'guide'` and will redirect tourists away.
Tourists MUST be sent to `/my-trips` — a completely separate route.

---

## 10. guides.html Book Button

The existing Book button has `href="#"`. It must be updated to:
```html
href="{{ url_for('book_item', item_type='guide', item_id=guide.id) }}"
```

The variable inside the loop is `guide` (not `g`, not `item`).
Verify the loop variable name in your existing `guides.html` before editing.

---

## 11. What Is NOT in Phase 6 Step 1

- ❌ Stripe payment processing (Phase 6 Step 2)
- ❌ Email confirmation
- ❌ Booking cancellation by tourist
- ❌ Full tourist dashboard (My Trips is a functional placeholder)
- ❌ Accommodation or Experience book buttons (only Guide book button is wired up now)
