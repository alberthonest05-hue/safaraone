"""
SafaraOne — All-in-One Travel Planning Platform
Python Flask Web Application
Author: SafaraOne Team
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from dotenv import load_dotenv
import os
import uuid
import time
import random
import string
from datetime import datetime, timedelta, timezone

# Phase 2: Load environment variables FIRST before importing models/services
load_dotenv()

from models import db, User, Destination, Accommodation, Experience, Guide, Booking, Review, \
    Availability, Notification, EscrowTransaction, PricingRule, CommissionLedger, KYCRecord, GuideVideo
from sqlalchemy import distinct
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, 
    set_access_cookies, unset_jwt_cookies
)
from flask_cors import CORS
import requests

# Phase 2B: Use DB-constrained OpenAI Planner from services
from services.planner import generate_itinerary

# Phase 7: Email service (SendGrid → Brevo → console stub)
try:
    from services.email_service import send_booking_receipt, send_cancellation_email
except Exception as _email_import_err:
    import logging
    logging.warning(f'[EMAIL] Could not import email_service: {_email_import_err}')
    def send_booking_receipt(*a, **kw): return False
    def send_cancellation_email(*a, **kw): return False

# Phase 8: Notification service
try:
    from services.notification_service import notify, notify_booking_confirmed, notify_review_received
except Exception as _notif_import_err:
    import logging
    logging.warning(f'[NOTIFY] Could not import notification_service: {_notif_import_err}')
    def notify(*a, **kw): pass
    def notify_booking_confirmed(*a, **kw): pass
    def notify_review_received(*a, **kw): pass

# Phase 8: Escrow service
try:
    from services.escrow_service import initiate_escrow, settle_escrow, refund_escrow, compute_dynamic_price
except Exception as _escrow_import_err:
    import logging
    logging.warning(f'[ESCROW] Could not import escrow_service: {_escrow_import_err}')
    def initiate_escrow(*a, **kw): return {"status": "error"}
    def settle_escrow(*a, **kw): return {"status": "error"}
    def refund_escrow(*a, **kw): return {"status": "error"}
    def compute_dynamic_price(base_price, *a, **kw): return {"base_price": base_price, "final_price": base_price, "multiplier": 1.0, "reason": "unavailable"}

# Phase 8: KYC service
try:
    from services.kyc_service import submit_kyc, get_kyc_status, process_sumsub_webhook
except Exception as _kyc_import_err:
    import logging
    logging.warning(f'[KYC] Could not import kyc_service: {_kyc_import_err}')
    def submit_kyc(*a, **kw): return {"success": True, "stub": True}
    def get_kyc_status(guide_id): return {"status": "not_submitted"}
    def process_sumsub_webhook(*a, **kw): return False

# Phase 7: In-memory FX rate cache (1-hour TTL)
_tzs_rate_cache = {
    'rate': None,
    'fetched_at': 0,
    'ttl_seconds': 3600,
}

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "safaraone-secret-key-2025")
CORS(app, supports_credentials=True)

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///safaraone.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url

# Engine options — only apply SSL for PostgreSQL (not SQLite which doesn't support it)
if db_url.startswith('postgresql'):
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'connect_args': {'sslmode': 'require'},
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }
else:
    # SQLite (local dev) — no SSL, simpler pooling
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        'pool_pre_ping': True,
    }
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

# JWT Configuration
app.config["JWT_SECRET_KEY"] = os.environ.get("JWT_SECRET_KEY", "safaraone-jwt-secret-key-2025")
app.config["JWT_TOKEN_LOCATION"] = ["headers", "cookies"]
app.config["JWT_COOKIE_SECURE"] = False # Set to True in production (HTTPS)
app.config["JWT_COOKIE_CSRF_PROTECT"] = False # Simplify for dev

# Initialize Extensions
db.init_app(app)
jwt = JWTManager(app)

# Phase 8: COMMISSION_RATE config
app.config["COMMISSION_RATE"] = float(os.environ.get("COMMISSION_RATE", "0.10"))

# Phase 8: Cloudinary init (graceful if keys are missing)
try:
    import cloudinary
    import cloudinary.uploader
    cloudinary.config(
        cloud_name = os.environ.get("CLOUDINARY_CLOUD_NAME", ""),
        api_key    = os.environ.get("CLOUDINARY_API_KEY", ""),
        api_secret = os.environ.get("CLOUDINARY_API_SECRET", ""),
        secure     = True,
    )
except Exception as _cloud_err:
    import logging
    logging.warning(f'[CLOUDINARY] Init failed: {_cloud_err}')

@jwt.unauthorized_loader
def unauthorized_callback(reason):
    # If the user is hitting an API route, return JSON
    if request.path.startswith('/api/'):
        return jsonify({"error": "Authentication required", "reason": reason}), 401
    # For browser page requests, redirect to the login page
    return redirect(url_for('auth'))

@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Token expired, please log in again"}), 401
    return redirect(url_for('auth'))

@jwt.invalid_token_loader
def invalid_token_callback(reason):
    if request.path.startswith('/api/'):
        return jsonify({"error": "Invalid token", "reason": reason}), 401
    return redirect(url_for('auth'))

@app.context_processor
def inject_user():
    try:
        from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
        verify_jwt_in_request(optional=True)
        user_id = get_jwt_identity()
        if user_id:
            user = db.session.get(User, int(user_id))
            if user:
                return {
                    "current_user_role": user.role,
                    "current_user_name": user.username,
                    "current_user_id": user.id
                }
    except:
        pass
    return {"current_user_role": None, "current_user_name": None, "current_user_id": None}


def _safe_migrate():
    """
    Non-destructive DB migration that runs on every startup.
    Safe on Render free tier — no shell access needed.

    Strategy:
      1. db.create_all()  → creates any NEW tables, skips existing ones.
      2. ALTER TABLE ...  → adds missing columns to existing tables.
         Uses IF NOT EXISTS for PostgreSQL or a try/except for SQLite.
    """
    db.create_all()

    from sqlalchemy import inspect, text
    engine   = db.engine
    dialect  = engine.dialect.name   # 'postgresql' or 'sqlite'
    inspector = inspect(engine)

    # ── Columns to add to existing tables ────────────────────────────────────
    # Format: (table_name, column_name, sql_type, default_sql)
    migrations = [
        # Phase 8 — User model additions
        ("user", "booking_type",       "VARCHAR(20)",  "'request'"),
        ("user", "flw_sub_account_id", "VARCHAR(100)", "NULL"),
        ("user", "is_verified",        "BOOLEAN",      "FALSE"),
        ("user", "is_admin",           "BOOLEAN",      "FALSE"),
    ]

    with engine.connect() as conn:
        for table, column, col_type, default in migrations:
            # Check if column already exists in the actual DB
            try:
                existing_cols = [c["name"] for c in inspector.get_columns(table)]
            except Exception:
                continue  # Table might not exist yet — create_all() handles it

            if column in existing_cols:
                continue  # Already there — nothing to do

            try:
                if dialect == "postgresql":
                    # PostgreSQL supports ADD COLUMN IF NOT EXISTS directly
                    sql = text(
                        f"ALTER TABLE \"{table}\" "
                        f"ADD COLUMN IF NOT EXISTS {column} {col_type} DEFAULT {default}"
                    )
                else:
                    # SQLite doesn't support IF NOT EXISTS on ALTER TABLE,
                    # but we already checked above so this is safe
                    sql = text(
                        f"ALTER TABLE \"{table}\" "
                        f"ADD COLUMN {column} {col_type} DEFAULT {default}"
                    )
                conn.execute(sql)
                conn.commit()
                print(f"[MIGRATE] ✅ Added column {table}.{column}")
            except Exception as col_err:
                # Column might already exist (race condition), safe to ignore
                print(f"[MIGRATE] ℹ️  Skipped {table}.{column}: {col_err}")
                try:
                    conn.rollback()
                except Exception:
                    pass

    print("[MIGRATE] ✅ Schema migration complete")


with app.app_context():
    try:
        _safe_migrate()
    except Exception as _migrate_err:
        # Never crash the app on migration failure — log and continue
        print(f"[MIGRATE] ⚠️  Migration error (non-fatal): {_migrate_err}")
        try:
            db.create_all()  # Fallback: at least create new tables
        except Exception:
            pass

    # Auto-seed if database is empty
    try:
        from models import Destination
        if Destination.query.count() == 0:
            from seed_db import seed
            seed()
            print('Auto-seeded database on startup')
    except Exception as e:
        print(f'Auto-seed skipped: {e}')


# ─────────────────────────────────────────────
#  AUTH API ENDPOINTS (Phase 2A)
# ─────────────────────────────────────────────

@app.route("/api/auth/register", methods=["POST"])
def api_register():
    try:
        data = request.get_json()
        
        # We use .strip() to accidentally remove any invisible spaces the user might have typed
        username = data.get("username", "").strip()
        email = data.get("email", "").strip()
        password = data.get("password", "")
        role = data.get("role", "tourist")

        # THE FIX: Check if the user forgot to fill out the form!
        if not username or not email or not password:
            return jsonify({"error": "Please provide a username, email, and password."}), 400

        if User.query.filter_by(username=username).first():
            return jsonify({"error": "Username already taken"}), 400

        new_user = User(username=username, email=email, role=role)
        new_user.set_password(password)
        
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=str(new_user.id))
        resp = jsonify({"message": "User registered successfully", "user_id": new_user.id, "username": new_user.username, "role": new_user.role})
        set_access_cookies(resp, access_token)
        return resp, 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500


@app.route("/api/auth/login", methods=["POST"])
def api_login():
    data = request.get_json()
    
    username = data.get("username", "").strip()
    password = data.get("password", "")

    # THE FIX: Ensure they actually typed something before checking the database
    if not username or not password:
        return jsonify({"error": "Please enter both username and password."}), 400

    user = User.query.filter_by(username=username).first()
    
    if not user or not user.check_password(password):
        return jsonify({"error": "Invalid username or password"}), 401

    access_token = create_access_token(identity=str(user.id))
    resp = jsonify({"message": "Login successful", "role": user.role, "username": user.username})
    set_access_cookies(resp, access_token)
    return resp, 200


@app.route("/api/auth/logout", methods=["POST"])
def api_logout():
    resp = jsonify({"message": "Logout successful"})
    unset_jwt_cookies(resp)
    return resp, 200


# ─────────────────────────────────────────────
#  MAIN PAGES
# ─────────────────────────────────────────────

@app.route("/")
@jwt_required(optional=True)
def index():
    featured = [d.to_dict() for d in Destination.query.limit(3).all()]
    top_experiences = [e.to_dict() for e in Experience.query.limit(6).all()]
    top_guides = [g.to_dict() for g in Guide.query.limit(4).all()]
    
    pending_count = 0
    user_id = get_jwt_identity()
    if user_id:
        user = db.session.get(User, int(user_id))
        if user and user.role == 'guide':
            guide = Guide.query.filter_by(user_id=user.id).first()
            if guide:
                pending_count = Booking.query.filter_by(item_type='guide', item_id=guide.id, status='confirmed').count()

    return render_template(
        "index.html",
        destinations=featured,
        experiences=top_experiences,
        guides=top_guides,
        pending_count=pending_count
    )


@app.route("/destinations")
def destinations():
    """All destinations page."""
    all_dests = [d.to_dict() for d in Destination.query.all()]
    return render_template("destinations.html", destinations=all_dests)


@app.route("/destinations/<dest_id>")
def destination_detail(dest_id):
    """Single destination detail page."""
    # Apply Issue 1: db.session.get
    dest = db.session.get(Destination, dest_id)
    if not dest:
        return redirect(url_for("destinations"))
    
    stays = [a.to_dict() for a in Accommodation.query.filter_by(destination_id=dest_id).all()]
    experiences = [e.to_dict() for e in Experience.query.filter_by(destination_id=dest_id).all()]
    guides = [g.to_dict() for g in Guide.query.filter_by(destination_id=dest_id).all()]
    
    return render_template(
        "destination_detail.html",
        destination=dest.to_dict(),
        stays=stays,
        experiences=experiences,
        guides=guides,
    )


@app.route("/stays")
def stays():
    """Accommodation search page."""
    dest_filter = request.args.get("destination", "")
    budget_filter = request.args.get("budget", "")
    
    query = Accommodation.query
    if dest_filter:
        query = query.filter_by(destination_id=dest_filter)
    if budget_filter:
        query = query.filter_by(tier=budget_filter)
        
    results = [a.to_dict() for a in query.all()]
    all_dests = [d.to_dict() for d in Destination.query.all()]
    
    return render_template(
        "stays.html",
        accommodations=results,
        destinations=all_dests,
        current_dest=dest_filter,
        current_budget=budget_filter,
    )


@app.route("/experiences")
def experiences():
    """Experiences & activities page."""
    dest_filter = request.args.get("destination", "")
    category_filter = request.args.get("category", "")
    
    query = Experience.query
    if dest_filter:
        query = query.filter_by(destination_id=dest_filter)
    if category_filter:
        query = query.filter_by(category=category_filter)
        
    results = [e.to_dict() for e in query.all()]
    all_dests = [d.to_dict() for d in Destination.query.all()]
    
    # get distinct categories
    categories = sorted([
        r[0] for r in db.session.query(distinct(Experience.category))
        .filter(Experience.category.isnot(None)).all()
    ])

    return render_template(
        "experiences.html",
        experiences=results,
        destinations=all_dests,
        categories=categories,
        current_dest=dest_filter,
        current_category=category_filter,
    )


@app.route("/guides")
def guides():
    """Tour guide marketplace page."""
    dest_filter = request.args.get("destination", "")
    spec_filter = request.args.get("specialization", "")
    
    query = Guide.query
    if dest_filter:
        query = query.filter_by(destination_id=dest_filter)
        
    guides_list = query.all()
    # Filter by json contained specializations if spec_filter provided
    if spec_filter:
        guides_list = [g for g in guides_list if g.specializations and spec_filter in g.specializations]
        
    results = [g.to_dict() for g in guides_list]
    all_dests = [d.to_dict() for d in Destination.query.all()]
    
    all_all_guides = Guide.query.all()
    all_specs = sorted(list(set(s for g in all_all_guides if g.specializations for s in g.specializations)))
    
    return render_template(
        "guides.html",
        guides=results,
        destinations=all_dests,
        specializations=all_specs,
        current_dest=dest_filter,
        current_spec=spec_filter,
    )


@app.route('/book/<item_type>/<item_id>')
@jwt_required(optional=True)
def book_item(item_type, item_id):
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))

    user = db.session.get(User, int(user_id))
    if not user:
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
    if item_type == 'guide':
        display_price = raw.get('price_per_day_usd', 0)
    elif item_type == 'accommodation':
        display_price = raw.get('price_per_night_usd', 0)
    else:
        display_price = raw.get('price_usd', 0)

    display_name  = raw.get('name') or raw.get('title', 'Booking')

    # Reuse existing pending booking or create a fresh one (Phase 7 flow)
    booking = Booking.query.filter_by(
        user_id=int(user_id), item_type=item_type, item_id=str(item_id), status='pending'
    ).first()

    if not booking:
        booking = Booking(
            user_id=int(user_id),
            item_type=item_type,
            item_id=str(item_id),
            item_name=display_name,
            amount_usd=float(display_price),
            status='pending'
        )
        db.session.add(booking)
        db.session.commit()
    elif not booking.item_name:
        booking.item_name = display_name
        db.session.commit()

    from datetime import date as _date
    return render_template('booking.html', booking=booking, current_user=user,
                           today=_date.today().isoformat())


@app.route("/planner")
def planner():
    """AI Budget Planner page."""
    all_dests = [d.to_dict() for d in Destination.query.all()]
    return render_template("planner.html", destinations=all_dests)


@app.route("/api/generate-itinerary", methods=["POST"])
def api_generate_itinerary():
    """API endpoint: Generate AI budget itinerary."""
    data = request.get_json()
    destination_id = data.get("destination_id", "zanzibar")
    budget_usd = float(data.get("budget_usd", 500))
    days = int(data.get("days", 3))
    travelers = int(data.get("travelers", 1))
    
    itinerary = generate_itinerary(destination_id, budget_usd, days, travelers)
    return jsonify(itinerary)


@app.route("/auth")
def auth():
    """Login / Register page."""
    return render_template("auth.html")


@app.route("/about")
def about():
    """About SafaraOne page."""
    return render_template("about.html")


# ─────────────────────────────────────────────
#  API ENDPOINTS
# ─────────────────────────────────────────────

@app.route("/api/destinations")
def api_destinations():
    return jsonify([d.to_dict() for d in Destination.query.all()])

@app.route("/api/stays")
def api_stays():
    dest = request.args.get("destination", "")
    query = Accommodation.query
    if dest:
        query = query.filter_by(destination_id=dest)
    return jsonify([a.to_dict() for a in query.all()])

@app.route("/api/experiences")
def api_experiences():
    dest = request.args.get("destination", "")
    query = Experience.query
    if dest:
        query = query.filter_by(destination_id=dest)
    return jsonify([e.to_dict() for e in query.all()])

@app.route("/api/guides")
def api_guides():
    dest = request.args.get("destination", "")
    query = Guide.query
    if dest:
        query = query.filter_by(destination_id=dest)
    return jsonify([g.to_dict() for g in query.all()])

# ─────────────────────────────────────────────
#  GUIDE PROFILES & REGISTRATION (Phase 2B)
# ─────────────────────────────────────────────

@app.route("/api/guides/me", methods=["GET", "PUT"])
@jwt_required()
def api_guides_me():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    if user.role != "guide":
        return jsonify({"error": "Unauthorized"}), 403
        
    guide = Guide.query.filter_by(user_id=user_id).first()
    if not guide:
        return jsonify({"error": "Profile not found"}), 404

    if request.method == "GET":
        return jsonify(guide.to_dict())
        
    if request.method == "PUT":
        data = request.get_json()
        if "bio" in data: guide.bio = data["bio"]
        if "title" in data: guide.title = data["title"]
        if "price_per_day_usd" in data: guide.price_per_day_usd = float(data["price_per_day_usd"])
        if "availability" in data: guide.availability = data["availability"]
        if "destination_id" in data: guide.destination_id = data["destination_id"]
        if "specializations" in data: guide.specializations = data["specializations"]
        if "languages" in data: guide.languages = data["languages"]
        if "image_url" in data: guide.avatar_url = data["image_url"]  # avatar_url is the model field
        db.session.commit()
        return jsonify({"message": "Profile updated", "guide": guide.to_dict()})

@app.route("/api/guides/<id>", methods=["GET"])
def api_get_guide(id):
    guide = db.session.get(Guide, id)
    if not guide:
        return jsonify({"error": "Not found"}), 404
    return jsonify(guide.to_dict())

# ─────────────────────────────────────────────
#  PHASE 2C: PAYMENTS & REVIEWS
# ─────────────────────────────────────────────

# ── Phase 7: Internal FX rate helper (avoids HTTP self-call) ──────────────
def _get_tzs_rate_internal():
    """Get TZS/USD rate from cache or Flutterwave FX API."""
    now = time.time()
    if (
        _tzs_rate_cache['rate'] is not None
        and now - _tzs_rate_cache['fetched_at'] < _tzs_rate_cache['ttl_seconds']
    ):
        return {'rate': _tzs_rate_cache['rate'], 'source': 'flutterwave', 'cached': True}

    flw_secret = os.environ.get('FLW_SECRET_KEY', '')
    rate = None
    source = 'fallback'
    try:
        resp = requests.get(
            'https://api.flutterwave.com/v3/rates',
            params={'from': 'USD', 'to': 'TZS', 'amount': '1'},
            headers={'Authorization': f'Bearer {flw_secret}'},
            timeout=5,
        )
        if resp.status_code == 200:
            data = resp.json()
            rate = float(data['data']['destination']['amount'])
            source = 'flutterwave'
    except Exception as e:
        app.logger.warning(f'[FX] Flutterwave FX fetch failed: {e}')

    if rate is None:
        rate = 2650.0
        source = 'fallback'
        app.logger.warning('[FX] Using fallback TZS rate: 2650.0')

    _tzs_rate_cache['rate'] = rate
    _tzs_rate_cache['fetched_at'] = now
    return {'rate': rate, 'source': source, 'cached': False}


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

@app.route("/api/checkout", methods=["POST"])
@jwt_required()
def api_checkout():
    data = request.get_json()
    booking_id = data.get("booking_id")
    
    booking = db.session.get(Booking, booking_id)
    if not booking or str(booking.user_id) != str(get_jwt_identity()):
        return jsonify({"error": "Booking not found or unauthorized"}), 404
        
    if booking.amount_usd <= 0:
        return jsonify({"error": "Invalid booking amount"}), 400

    base_url = os.environ.get("BASE_URL", "http://127.0.0.1:5050")
        
    session_params = {
        "payment_method_types": ["card"],
        "line_items": [{
            "price_data": {
                "currency": "usd",
                "unit_amount": int(booking.amount_usd * 100),
                "product_data": {
                    "name": f"SafaraOne Booking: {booking.item_type.title()}"
                },
            },
            "quantity": 1,
        }],
        "mode": "payment",
        "success_url": f"{base_url}/success?session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base_url}/cancel",
        "metadata": {
            "booking_id": booking.id
        }
    }
    
    # Split Payments (Stripe Connect)
    if booking.item_type == "guide":
        guide = db.session.get(Guide, booking.item_id)
        if guide and guide.stripe_account_id:
            # 80% to guide, 20% platform fee
            guide_amount = int((booking.amount_usd * 0.8) * 100)
            session_params["payment_intent_data"] = {
                "transfer_data": {
                    "destination": guide.stripe_account_id,
                    "amount": guide_amount
                }
            }
            
    try:
        session = stripe.checkout.Session.create(**session_params)
        booking.stripe_session_id = session.id
        db.session.commit()
        return jsonify({"checkout_url": session.url})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/webhooks/stripe", methods=["POST"])
def api_webhook_stripe():
    payload = request.get_data(as_text=True)
    sig_header = request.headers.get("Stripe-Signature", "")
    endpoint_secret = os.environ.get("STRIPE_WEBHOOK_SECRET", "")
    
    if not endpoint_secret:
        return jsonify({"error": "Webhook secret not configured"}), 500
        
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, endpoint_secret)
    except stripe.error.SignatureVerificationError:
        return jsonify({"error": "Invalid signature"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 400
            
    if event.get("type") == "checkout.session.completed":
        session = event["data"]["object"]
        booking_id = session.get("metadata", {}).get("booking_id")
        if booking_id:
            booking = db.session.get(Booking, int(booking_id))
            if booking:
                booking.status = "confirmed"
                db.session.commit()
                
    return jsonify({"status": "success"}), 200


@app.route("/api/mobile-money/checkout", methods=["POST"])
@jwt_required()
def api_mobile_money_checkout():
    """Stub for Tanzanian Mobile Money (M-Pesa / AzamPay) push USSD flow"""
    data = request.get_json()
    booking_id = data.get("booking_id")
    phone = data.get("phone", "")
    
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
        
    tx_id = f"tz-{uuid.uuid4().hex[:8]}"
    
    # Simulate USSD Push Trigger
    return jsonify({
        "message": f"USSD push sent to {phone}. Awaiting user PIN.",
        "transaction_id": tx_id,
        "status": "pending_user_action"
    })


# DEPRECATED: Phase 8 replaces /api/reviews POST with submit_review() below.
# This function is renamed to avoid Flask duplicate endpoint error.
# The new endpoint at the bottom of this file handles /api/reviews POST fully.
def _legacy_api_post_review():
    """Legacy review submission — replaced by Phase 8 submit_review()."""
    data = request.get_json()
    user_id = int(get_jwt_identity())
    item_type = data.get("item_type")
    item_id   = data.get("item_id")
    rating    = int(data.get("rating", 5))
    comment   = data.get("comment", "")
    if not item_type or not item_id:
        return jsonify({"error": "Missing item info"}), 400
    if not 1 <= rating <= 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
    try:
        review = Review(
            tourist_id=user_id, user_id=user_id,
            item_type=item_type, item_id=str(item_id),
            rating=rating, comment=comment
        )
        db.session.add(review)
        db.session.commit()
        if item_type == "guide":
            guide = db.session.get(Guide, item_id)
            if guide:
                total_r = guide.total_reviews or 0
                current_rt = guide.rating or 0.0
                new_total = total_r + 1
                guide.rating = round(((current_rt * total_r) + rating) / new_total, 1)
                guide.total_reviews = new_total
                db.session.commit()
        return jsonify({"message": "Review submitted successfully"}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "You have already reviewed this item"}), 400

@app.route("/become-guide-info")
@jwt_required(optional=True)
def become_guide_info():
    """Guide onboarding landing page."""
    return render_template("become_guide_info.html")


# ─────────────────────────────────────────────
#  PHASE 2B: GUIDE REGISTRATION ROUTES
# ─────────────────────────────────────────────

@app.route("/register-guide")
@jwt_required(optional=True)
def register_guide_page():
    # Fix 1: Properly catch unauthorized users without a JSON crash
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))
        
    destinations = Destination.query.all()
    return render_template("register_guide.html", destinations=destinations)


@app.route("/api/guides/register", methods=["POST"])
@jwt_required()
def api_guide_register():
    user_id = int(get_jwt_identity())
    
    # Fix 4: Safely query the database, avoiding SQLAlchemy 2.0 specific syntax
    user = User.query.get(user_id)
    
    if not user:
        return jsonify({"error": "User not found"}), 404
        
    # Check if they are already a guide
    existing_guide = Guide.query.filter_by(user_id=user_id).first()
    if existing_guide:
        return jsonify({"error": "You are already registered as a guide"}), 400

    data = request.get_json()
    
    # Validation
    name = data.get("name")
    bio = data.get("bio")
    price = data.get("price_per_day_usd")
    dest_id = data.get("destination_id")
    specializations = data.get("specializations") or [data.get("specialization")] or []
    languages = data.get("languages", [])
    image_url = data.get("image_url", "https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800")
    
    # Use the first specialization as the title if title is missing
    title = data.get("title") or (specializations[0] if specializations else 'SafaraOne Guide')

    if not all([name, bio, price, dest_id]):
        return jsonify({"error": "Missing required fields (name, bio, rate, destination)"}), 400

    try:
        # 1. Create the Guide profile
        new_guide = Guide(
            id=f"guide-{user_id}", # Explicitly set an ID
            user_id=user_id,
            name=name,
            title=title,
            bio=bio,
            price_per_day_usd=float(price),
            destination_id=str(dest_id),
            languages=languages,
            specializations=specializations,
            avatar_url=image_url
        )
        
        # 2. Update the User role to 'guide'
        user.role = "guide"
        
        db.session.add(new_guide)
        db.session.commit()
        
        return jsonify({"message": "Guide profile created successfully!"}), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


# ─────────────────────────────────────────────
#  PHASE 2 MASTER UPDATE: DASHBOARDS & ADMIN
# ─────────────────────────────────────────────

@app.route("/admin")
@jwt_required()
def admin_dashboard():
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user or user.role != "admin":
        return redirect(url_for("index"))
    
    # Platform Analytics
    total_users = User.query.count()
    total_bookings = Booking.query.count()
    total_revenue = db.session.query(db.func.sum(Booking.amount_usd)).filter(Booking.status == 'confirmed').scalar() or 0.0
    active_guides = Guide.query.filter_by(is_verified=True).count()
    
    stats = {
        "total_users": total_users,
        "total_bookings": total_bookings,
        "total_revenue": round(total_revenue, 2),
        "active_guides": active_guides
    }
    
    users = User.query.all()
    unverified_guides = Guide.query.filter_by(is_verified=False).all()
    all_bookings = Booking.query.order_by(Booking.booking_date.desc()).all()
    
    return render_template("admin_dashboard.html", 
                           users=users, 
                           stats=stats, 
                           unverified_guides=unverified_guides,
                           bookings=all_bookings)


@app.route('/api/admin/guides/<guide_id>/verify', methods=['POST'])
@jwt_required()
def api_admin_verify_guide(guide_id):
    user_id = int(get_jwt_identity())
    admin = db.session.get(User, user_id)
    if not admin or admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
    
    guide = db.session.get(Guide, guide_id)
    if not guide:
        # Try finding by user_id if ID lookup fails
        guide = Guide.query.filter_by(user_id=int(guide_id)).first() if guide_id.isdigit() else None
        if not guide:
            return jsonify({'error': 'Guide not found'}), 404
            
    guide.is_verified = True
    db.session.commit()
    return jsonify({'message': f'Guide {guide.name} verified successfully'})


@app.route('/api/admin/users/<int:user_id>/suspend', methods=['POST'])
@jwt_required()
def api_admin_suspend_user(user_id):
    current_admin_id = int(get_jwt_identity())
    admin = db.session.get(User, current_admin_id)
    if not admin or admin.role != 'admin':
        return jsonify({'error': 'Unauthorized'}), 403
        
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({'error': 'User not found'}), 404
        
    if user.id == current_admin_id:
        return jsonify({'error': 'Cannot suspend yourself'}), 400
        
    user.role = 'suspended'
    db.session.commit()
    return jsonify({'message': f'User {user.username} suspended'})


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def api_admin_delete_user(user_id):
    current_admin_id = int(get_jwt_identity())
    admin_user = db.session.get(User, current_admin_id)
    if not admin_user or admin_user.role != "admin" :
        return jsonify({"error": "Unauthorized"}), 403
    
    user_to_delete = db.session.get(User, user_id)
    if not user_to_delete:
        return jsonify({"error": "User not found"}), 404
    
    if user_to_delete.id == current_admin_id:
        return jsonify({"error": "You cannot delete yourself"}), 400

    try:
        # Cascade-like manual cleanup
        # Delete Guide profile if exists
        Guide.query.filter_by(user_id=user_id).delete()
        # Delete Bookings
        Booking.query.filter_by(user_id=user_id).delete()
        # Delete Reviews
        Review.query.filter_by(user_id=user_id).delete()
        
        db.session.delete(user_to_delete)
        db.session.commit()
        return jsonify({"message": f"User {user_to_delete.username} and all related data deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500


@app.route("/api/setup/make-admin", methods=["POST"])
def api_make_admin():
    # Only allow if no admins exist
    admin_exists = User.query.filter_by(role="admin").first()
    if admin_exists:
        return jsonify({"error": "An admin already exists. Use the Admin panel."}), 403
    
    data = request.get_json()
    username = data.get("username")
    if not username:
        return jsonify({"error": "Username required"}), 400
        
    user = User.query.filter_by(username=username).first()
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    user.role = "admin"
    db.session.commit()
    return jsonify({"message": f"User {username} is now an admin!"})


# ── Phase 7: One-time production schema migration ─────────────────────────
# Visit: GET /api/setup/phase7-migrate  (no key needed — resets mock data only)
@app.route('/api/setup/phase7-migrate')
def phase7_migrate():
    try:
        db.drop_all()
        db.create_all()

        from data.mock_data import DESTINATIONS, ACCOMMODATIONS, EXPERIENCES, GUIDES

        for d in DESTINATIONS:
            dest_data = {k: v for k, v in d.items() if k != 'stats'}
            dest = Destination(**dest_data)
            if 'stats' in d:
                dest.stats = d['stats']
            db.session.add(dest)
        db.session.commit()

        for a in ACCOMMODATIONS:
            db.session.add(Accommodation(**a))
        db.session.commit()

        for e in EXPERIENCES:
            db.session.add(Experience(**e))
        db.session.commit()

        for g in GUIDES:
            db.session.add(Guide(**{k: v for k, v in g.items()}))
        db.session.commit()

        return jsonify({
            'status': 'success',
            'message': 'Phase 7 schema applied and database reseeded.',
            'destinations': Destination.query.count(),
            'accommodations': Accommodation.query.count(),
            'experiences': Experience.query.count(),
            'guides': Guide.query.count(),
        })

    except Exception as e:
        db.session.rollback()
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


@app.route('/api/setup/force-seed')
def force_seed():
    try:
        db.create_all()
        
        # Check if destinations already exist
        dest_count = Destination.query.count()
        if dest_count == 0:
            from data.mock_data import DESTINATIONS, ACCOMMODATIONS, EXPERIENCES, GUIDES
            
            for d in DESTINATIONS:
                # Filter out 'stats' field if it's not a model column
                dest_data = {k: v for k, v in d.items() if k != 'stats'}
                dest = Destination(**dest_data)
                if 'stats' in d:
                    dest.stats = d['stats']
                db.session.add(dest)
            db.session.commit()
            
            for a in ACCOMMODATIONS:
                db.session.add(Accommodation(**a))
            db.session.commit()
            
            for e in EXPERIENCES:
                db.session.add(Experience(**e))
            db.session.commit()
            
            for g in GUIDES:
                db.session.add(Guide(**{k: v for k, v in g.items()}))
            db.session.commit()
            
            return f'Seeded successfully! Destinations: {Destination.query.count()}'
        else:
            return f'Already seeded. Destinations: {dest_count}'
            
    except Exception as e:
        db.session.rollback()
        import traceback
        return f'Failed: {traceback.format_exc()}', 500


@app.route('/dashboard')
@jwt_required(optional=True)
def guide_dashboard():
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))
    
    user = db.session.get(User, int(user_id))
    if not user:
        return redirect(url_for('auth'))
    if user.role != 'guide':
        return redirect(url_for('index'))
    
    try:
        guide = Guide.query.filter_by(user_id=int(user_id)).first()
        
        if not guide or not guide.bio or not guide.price_per_day_usd:
            try:
                destinations = [d.to_dict() for d in Destination.query.all()]
            except:
                destinations = []
            hardcoded = [
                {'id': 'zanzibar', 'name': 'Zanzibar'},
                {'id': 'serengeti', 'name': 'Serengeti'},
                {'id': 'kilimanjaro', 'name': 'Mount Kilimanjaro'}
            ]
            existing_ids = [d['id'] for d in destinations]
            for h in hardcoded:
                if h['id'] not in existing_ids:
                    destinations.append(h)
            return render_template('guide_credentials.html', destinations=destinations)
        
        guide_dict = {
            'id': guide.id or '',
            'name': guide.name or user.username,
            'avatar_url': guide.avatar_url or 'https://images.unsplash.com/photo-1531746020798-e6953c6e8e04?w=400',
            'title': guide.title or 'SafaraOne Guide',
            'languages': guide.languages or [],
            'specializations': guide.specializations or [],
            'price_per_day_usd': guide.price_per_day_usd or 0,
            'rating': guide.rating or 0.0,
            'total_reviews': guide.total_reviews or 0,
            'bio': guide.bio or '',
            'destination_id': guide.destination_id or '',
            'is_verified': guide.is_verified or False,
        }
        
        try:
            bookings = Booking.query.filter_by(item_type='guide', item_id=guide.id).all()
        except:
            bookings = []
            
        total_earnings = sum((b.amount_usd or 0) * 0.8 for b in bookings if b.status == 'completed')
        pending = [b for b in bookings if b.status == 'confirmed']
        
        return render_template('guide_dashboard.html',
            guide=guide_dict,
            bookings=bookings,
            total_earnings=round(total_earnings, 2),
            pending_bookings=pending
        )
    except Exception as e:
        import traceback
        print('GUIDE DASHBOARD ERROR:', traceback.format_exc())
        return f'Dashboard error: {str(e)}', 500
@app.route('/dashboard/bookings')
@jwt_required(optional=True)
def guide_bookings():
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))
    user = db.session.get(User, int(user_id))
    if not user or user.role != 'guide':
        return redirect(url_for('index'))
    guide = Guide.query.filter_by(user_id=int(user_id)).first()
    if not guide:
        return redirect(url_for('guide_dashboard'))
    bookings = Booking.query.filter_by(item_type='guide', item_id=guide.id).all()
    return render_template('guide_bookings.html', bookings=bookings, guide=guide.to_dict())


@app.route('/dashboard/edit-profile')
@jwt_required(optional=True)
def guide_edit_profile():
    user_id = get_jwt_identity()
    if not user_id:
        return redirect(url_for('auth'))
    user = db.session.get(User, int(user_id))
    if not user or user.role != 'guide':
        return redirect(url_for('index'))
    guide = Guide.query.filter_by(user_id=int(user_id)).first()
    if not guide:
        return redirect(url_for('guide_dashboard'))
    destinations = [d.to_dict() for d in Destination.query.all()]
    return render_template('guide_edit_profile.html', guide=guide.to_dict(), destinations=destinations)


@app.route("/api/bookings/<int:booking_id>/status", methods=["POST"])
@jwt_required()
def api_update_booking_status(booking_id):
    user_id = int(get_jwt_identity())
    user = db.session.get(User, user_id)
    if not user or user.role != "guide":
        return jsonify({"error": "Unauthorized"}), 403
        
    data = request.get_json()
    new_status = data.get("status")
    if new_status not in ["confirmed", "cancelled", "completed"]:
        return jsonify({"error": "Invalid status"}), 400
        
    booking = db.session.get(Booking, booking_id)
    if not booking:
        return jsonify({"error": "Booking not found"}), 404
        
    # Ensure this booking belongs to the guide
    guide = Guide.query.filter_by(user_id=user_id).first()
    if not guide or booking.item_id != guide.id or booking.item_type != 'guide':
        return jsonify({"error": "Unauthorized"}), 403
        
    booking.status = new_status
    db.session.commit()
    return jsonify({"message": f"Booking {booking_id} updated to {new_status}"})


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
            'item_name':      b.item_name or item_name,
            'item_image':     item_image,
            'amount_usd':     b.amount_usd,
            'amount':         b.amount_usd,           # alias for Phase 7 template
            'currency':       b.currency or 'USD',
            'tzs_amount':     b.tzs_amount,
            'payment_method': b.payment_method or 'card',
            'refund_status':  b.refund_status,
            'tx_ref':         b.tx_ref or f'#{b.id}',
            'num_guests':     b.num_guests,
            'status':         b.status,
            'scheduled_date': b.scheduled_date.strftime('%Y-%m-%d') if b.scheduled_date else None,
            'booking_date':   b.booking_date.strftime('%b %d, %Y') if b.booking_date else ''
        })

    return render_template('my_trips.html', bookings=enriched, current_user=user, username=user.username)


# ── Phase 7, Feature #36 — Upgraded Cancellation Flow ────────────────────
@app.route('/api/bookings/<int:booking_id>/cancel', methods=['POST'])
@jwt_required()
def cancel_booking(booking_id):
    """
    Cancels a booking with automated refund logic.
    >48hrs before trip  → auto-refund via Flutterwave
    ≤48hrs before trip  → flagged for admin review
    Sends cancellation email in both cases.
    """
    current_user_id = int(get_jwt_identity())
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first()

    if not booking:
        return jsonify({'status': 'error', 'message': 'Booking not found'}), 404
    if booking.status == 'cancelled':
        return jsonify({'status': 'error', 'message': 'Booking is already cancelled'}), 400
    if booking.status == 'pending':
        booking.status = 'cancelled'
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Booking cancelled (no charge).', 'refund': None})

    # Determine refund eligibility
    now_utc = datetime.now(timezone.utc)
    refund_eligible = False
    hours_until_trip = None
    if booking.scheduled_date:
        trip_dt = booking.scheduled_date.replace(tzinfo=timezone.utc) if booking.scheduled_date.tzinfo is None else booking.scheduled_date
        hours_until_trip = (trip_dt - now_utc).total_seconds() / 3600
        refund_eligible = hours_until_trip > 48

    refund_info = {
        'refund_eligible':  refund_eligible,
        'hours_until_trip': hours_until_trip,
        'refund_status':    None,
        'refund_id':        None,
        'refund_amount':    None,
        'refund_currency':  booking.currency or 'USD',
    }

    if refund_eligible and booking.tx_id:
        flw_secret = os.environ.get('FLW_SECRET_KEY', '')
        try:
            refund_amount = booking.tzs_amount if booking.currency == 'TZS' else booking.amount_usd
            resp = requests.post(
                f'https://api.flutterwave.com/v3/transactions/{booking.tx_id}/refund',
                json={'amount': refund_amount},
                headers={'Authorization': f'Bearer {flw_secret}'},
                timeout=10,
            )
            result = resp.json()
            if result.get('status') == 'success':
                refund_data = result.get('data', {})
                booking.refund_status = 'processed'
                booking.flw_refund_id = str(refund_data.get('id', ''))
                refund_info.update({'refund_status': 'processed', 'refund_id': booking.flw_refund_id, 'refund_amount': str(refund_amount)})
                app.logger.info(f'[REFUND] Processed for booking #{booking_id}')
            else:
                booking.refund_status = 'requested'
                refund_info['refund_status'] = 'requested'
                app.logger.warning(f'[REFUND] FLW error for #{booking_id}: {result}')
        except Exception as e:
            booking.refund_status = 'requested'
            refund_info['refund_status'] = 'requested'
            app.logger.error(f'[REFUND] Exception for #{booking_id}: {e}')
    else:
        booking.refund_status = 'requested'
        refund_info['refund_status'] = 'requested'

    booking.status = 'cancelled'
    db.session.commit()

    # Phase 8: notify guide of cancellation
    try:
        if booking.item_type == 'guide':
            guide_user = User.query.filter_by(id=booking.item_id).first() or \
                         User.query.join(Guide, Guide.user_id == User.id)\
                               .filter(Guide.id == booking.item_id).first()
            if guide_user:
                notify(
                    user_id=guide_user.id,
                    notif_type="booking_cancelled",
                    title="Booking Cancelled",
                    message=f"A tourist cancelled their booking for {booking.scheduled_date.strftime('%b %d, %Y') if booking.scheduled_date else 'an upcoming date'}.",
                    link="/dashboard/bookings",
                )
    except Exception: pass

    # Send cancellation email (best-effort)
    tourist = db.session.get(User, current_user_id)
    if tourist:
        try:
            send_cancellation_email(
                user_email=tourist.email,
                username=tourist.username,
                booking_info={
                    'booking_id':    booking.id,
                    'item_name':     booking.item_name or 'Your booking',
                    'item_type':     booking.item_type.capitalize() if booking.item_type else 'Booking',
                    'scheduled_date': str(booking.scheduled_date) if booking.scheduled_date else '—',
                },
                refund_info=refund_info,
            )
        except Exception as e:
            app.logger.error(f'[EMAIL] Cancellation email failed for #{booking_id}: {e}')

    return jsonify({'status': 'success', 'message': 'Booking cancelled successfully.', 'refund': refund_info})



# ── Phase 7, Features #43 + #44 — Mobile Money + TZS Checkout ────────────
@app.route('/api/create-checkout-session', methods=['POST'])
@jwt_required()
def create_checkout_session():
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    booking_id      = data.get('booking_id')
    payment_method  = data.get('payment_method', 'card')
    currency        = data.get('currency', 'USD').upper()
    phone_number    = data.get('phone_number', '')
    check_in_date   = data.get('check_in_date', '') or data.get('scheduled_date', '')
    check_out_date  = data.get('check_out_date', '')   # For accommodation / guide
    num_units       = int(data.get('num_guests', 1))   # nights/days/guests

    if not booking_id:
        return jsonify({'status': 'error', 'message': 'booking_id is required'}), 400
    if not check_in_date:
        return jsonify({'status': 'error', 'message': 'Please select your trip start date.'}), 400

    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first()
    if not booking:
        return jsonify({'status': 'error', 'message': 'Booking not found or session expired. Please refresh.'}), 404
    if booking.status not in ('pending',):
        return jsonify({'status': 'error', 'message': 'This booking has already been processed.'}), 400
    if payment_method == 'mobile_money' and not phone_number:
        return jsonify({'status': 'error', 'message': 'Phone number is required for Mobile Money.'}), 400

    user = db.session.get(User, current_user_id)
    if not user:
        return jsonify({'status': 'error', 'message': 'User not found'}), 404

    # ── Parse dates ────────────────────────────────────────────────────────
    from datetime import datetime as _dt, timedelta as _td
    try:
        checkin_obj  = _dt.strptime(check_in_date, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return jsonify({'status': 'error', 'message': 'Invalid check-in date format.'}), 400

    # For accommodation/guide: compute nights/days from date range
    if check_out_date and booking.item_type in ('accommodation', 'guide'):
        try:
            checkout_obj = _dt.strptime(check_out_date, '%Y-%m-%d').date()
            nights = (checkout_obj - checkin_obj).days
            if nights < 1:
                return jsonify({'status': 'error', 'message': 'Check-out must be after check-in.'}), 400
            num_units = nights
        except (ValueError, TypeError):
            return jsonify({'status': 'error', 'message': 'Invalid check-out date format.'}), 400

    # ── Persist trip details on booking (without changing amount_usd unit price) ─
    booking.scheduled_date = checkin_obj
    booking.num_guests     = num_units
    # Do NOT mutate amount_usd — it is the unit price (per night/day/person)
    # Compute total only for Flutterwave charge
    unit_price    = float(booking.amount_usd)
    total_usd     = round(unit_price * num_units, 2)

    # ── Currency conversion ────────────────────────────────────────────────
    amount_for_charge = total_usd
    tzs_amount        = None
    if currency == 'TZS':
        rate_data         = _get_tzs_rate_internal()
        rate              = rate_data.get('rate', 2650.0)
        tzs_amount        = round(total_usd * rate, 2)
        amount_for_charge = tzs_amount

    tx_ref       = f"saf-{booking.id}-{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"
    redirect_url = url_for('payment_callback', _external=True)

    payload = {
        'tx_ref':       tx_ref,
        'amount':       amount_for_charge,
        'currency':     currency,
        'redirect_url': redirect_url,
        'customer':     {'email': user.email, 'name': user.username},
        'meta':         {'booking_id': booking.id, 'payment_method': payment_method, 'currency': currency},
        'customizations': {
            'title':       'SafaraOne',
            'description': f"Booking: {booking.item_name or 'Trip'} ({num_units} {'night(s)' if booking.item_type == 'accommodation' else 'day(s)' if booking.item_type == 'guide' else 'guest(s)'})",
            'logo':        'https://safaraone.onrender.com/static/img/logo.png',
        },
    }
    if payment_method == 'mobile_money':
        payload['payment_options'] = 'mobilemoneytanzania'
        payload['customer']['phonenumber'] = phone_number
    else:
        payload['payment_options'] = 'card'

    flw_secret = os.environ.get('FLW_SECRET_KEY', '')
    try:
        resp   = requests.post(
            'https://api.flutterwave.com/v3/payments',
            json=payload,
            headers={'Authorization': f'Bearer {flw_secret}'},
            timeout=12,
        )
        result = resp.json()

        if result.get('status') == 'success':
            # Only now save FLW ref and currency — do NOT change amount_usd
            booking.tx_ref         = tx_ref
            booking.currency       = currency
            booking.tzs_amount     = tzs_amount
            booking.payment_method = payment_method
            db.session.commit()
            return jsonify({'status': 'success', 'session_url': result['data']['link'], 'tx_ref': tx_ref})
        else:
            # ⚠️ Do NOT delete the booking — keep as pending so user can retry
            db.session.rollback()
            flw_msg = result.get('message', 'Payment gateway error. Please check your keys.')
            app.logger.error(f'[CHECKOUT] FLW error: {flw_msg} | payload: {payload}')
            return jsonify({'status': 'error', 'message': f'Payment gateway: {flw_msg}'}), 502

    except requests.exceptions.Timeout:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': 'Payment gateway timed out. Please try again.'}), 504
    except Exception as e:
        db.session.rollback()
        app.logger.error(f'[CHECKOUT] Unexpected error: {e}')
        return jsonify({'status': 'error', 'message': f'Unexpected error: {str(e)}'}), 500



# ── Phase 7 — FX Rate Endpoint ────────────────────────────────────────────
@app.route('/api/fx/tzs-rate', methods=['GET'])
def get_tzs_rate():
    """Returns live TZS/USD rate, cached 1 hour."""
    data = _get_tzs_rate_internal()
    return jsonify({'status': 'success', **data})


# ── Phase 7 — Updated Flutterwave Webhook (saves tx_id) ─────────────────
@app.route('/api/flw/webhook', methods=['POST'])
def flw_webhook():
    flw_hash      = request.headers.get('verif-hash')
    expected_hash = os.environ.get('FLW_VERIF_HASH', os.environ.get('FLW_WEBHOOK_SECRET', ''))
    if not flw_hash or flw_hash != expected_hash:
        return jsonify({'error': 'Unauthorized'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'error': 'No payload'}), 400

    if data.get('event') == 'charge.completed':
        payload = data.get('data', {})
        if payload.get('status') == 'successful':
            tx_ref   = payload.get('tx_ref', '')
            trans_id = payload.get('id')
            booking  = Booking.query.filter_by(tx_ref=tx_ref).first()
            if booking and booking.status == 'pending':
                booking.status = 'confirmed'
                booking.tx_id  = str(trans_id)  # Phase 7: store for refund calls
                db.session.commit()
                app.logger.info(f'[WEBHOOK] Booking #{booking.id} confirmed (tx_id={trans_id})')

    return jsonify({'status': 'ok'}), 200


# ── Phase 7, Feature #46 — Payment Callback (sends receipt email) ────────
@app.route('/payment/callback')
def payment_callback():
    status   = request.args.get('status', '')
    tx_ref   = request.args.get('tx_ref', '')
    trans_id = request.args.get('transaction_id', '')

    if status != 'successful' or not trans_id:
        # Mark pending booking as cancelled so the slot is freed
        booking = Booking.query.filter_by(tx_ref=tx_ref).first()
        if booking and booking.status == 'pending':
            booking.status = 'cancelled'
            db.session.commit()
        return redirect(url_for('payment_cancel_page'))

    booking = Booking.query.filter_by(tx_ref=tx_ref).first()
    if not booking:
        app.logger.error(f'[CALLBACK] No booking for tx_ref: {tx_ref}')
        return redirect(url_for('payment_cancel_page'))

    # Server-side verification
    flw_secret = os.environ.get('FLW_SECRET_KEY', '')
    try:
        resp = requests.get(
            f'https://api.flutterwave.com/v3/transactions/{trans_id}/verify',
            headers={'Authorization': f'Bearer {flw_secret}'},
            timeout=10,
        )
        result = resp.json()
        if result.get('status') != 'success':
            app.logger.warning(f'[CALLBACK] Verification failed for {tx_ref}')
            return redirect(url_for('payment_cancel_page'))

        verified = result['data']
        expected = booking.tzs_amount if booking.currency == 'TZS' else booking.amount_usd
        if abs(float(verified.get('amount', 0)) - expected) > 1:
            app.logger.warning(f'[CALLBACK] Amount mismatch for {tx_ref}')
            return redirect(url_for('payment_cancel_page'))
    except Exception as e:
        app.logger.error(f'[CALLBACK] Verify exception for {tx_ref}: {e}')
        return redirect(url_for('payment_cancel_page'))

    # Confirm booking
    booking.status = 'confirmed'
    booking.tx_id  = str(trans_id)
    db.session.commit()

    # Phase 8: initiate escrow + send booking confirmed notification
    try:
        if booking.item_type == 'guide':
            guide_obj  = db.session.get(Guide, booking.item_id)
            guide_user = User.query.get(guide_obj.user_id) if guide_obj else None
            guide_sub  = getattr(guide_user, 'flw_sub_account_id', None) if guide_user else None
            initiate_escrow(booking, guide_sub)
    except Exception as _esc_err:
        app.logger.error(f'[ESCROW] Initiation failed for booking #{booking.id}: {_esc_err}')

    try:
        tourist_obj  = db.session.get(User, booking.user_id)
        guide_notify = None
        if booking.item_type == 'guide':
            _g = db.session.get(Guide, booking.item_id)
            guide_notify = User.query.get(_g.user_id) if _g else None
        notify_booking_confirmed(booking, guide_notify)
    except Exception as _n_err:
        app.logger.error(f'[NOTIFY] Booking confirmed notification failed: {_n_err}')

    # Send receipt email (best-effort)
    tourist = db.session.get(User, booking.user_id)
    if tourist:
        guide_name = guide_phone = None
        if booking.item_type == 'guide':
            g = db.session.get(Guide, booking.item_id)
            if g:
                guide_name  = g.name
                guide_phone = getattr(g, 'phone', None)
        try:
            send_booking_receipt(
                user_email=tourist.email,
                username=tourist.username,
                booking_info={
                    'booking_id':     booking.id,
                    'item_name':      booking.item_name or 'Your Booking',
                    'item_type':      booking.item_type.capitalize() if booking.item_type else 'Booking',
                    'scheduled_date': booking.scheduled_date.strftime('%b %d, %Y') if booking.scheduled_date else '—',
                    'amount_usd':     f'{booking.amount_usd:.2f}',
                    'amount_tzs':     f'{booking.tzs_amount:,.0f}' if booking.tzs_amount else None,
                    'currency':       booking.currency or 'USD',
                    'payment_method': booking.payment_method or 'card',
                    'tx_ref':         booking.tx_ref,
                    'guide_name':     guide_name,
                    'guide_phone':    guide_phone,
                },
            )
        except Exception as e:
            app.logger.error(f'[EMAIL] Receipt failed for #{booking.id}: {e}')

    return redirect(url_for('payment_success_page', booking_id=booking.id))


# ── Phase 7 — Payment Success & Cancel Pages ───────────────────────────
@app.route('/payment/success')
@jwt_required(optional=True)
def payment_success_page():
    booking_id   = request.args.get('booking_id')
    user_id      = get_jwt_identity()
    current_user = db.session.get(User, int(user_id)) if user_id else None
    booking      = db.session.get(Booking, int(booking_id)) if booking_id else None
    return render_template('payment_success.html', booking=booking, current_user=current_user)


@app.route('/payment/cancel')
def payment_cancel_page():
    return render_template('payment_cancel.html')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)


# =============================================================================
# PHASE 8 ROUTES
# =============================================================================

# ──────────────────────────────────────────────────────────────────────
# DAY 2 — Host Dashboard, Availability, Reviews, Notifications
# ──────────────────────────────────────────────────────────────────────

@app.route("/host/dashboard")
@jwt_required()
def host_dashboard():
    """Main dashboard for accommodation hosts and experience providers. Feature #58."""
    current_user_id = get_jwt_identity()
    host = User.query.get_or_404(current_user_id)

    if host.role not in ("host", "operator", "admin"):
        return redirect(url_for("index"))

    # BUG FIX: Use Accommodation (not Stay), check for host_id attribute
    my_stay_ids = []
    if hasattr(Accommodation, "host_id"):
        my_stay_ids = [s.id for s in Accommodation.query.filter_by(host_id=int(current_user_id)).all()]

    my_experience_ids = []
    if hasattr(Experience, "host_id"):
        my_experience_ids = [e.id for e in Experience.query.filter_by(host_id=int(current_user_id)).all()]

    bookings = Booking.query
    if my_stay_ids or my_experience_ids:
        bookings = bookings.filter(
            db.or_(
                db.and_(Booking.item_type == "accommodation", Booking.item_id.in_([str(x) for x in my_stay_ids])),
                db.and_(Booking.item_type == "experience",    Booking.item_id.in_([str(x) for x in my_experience_ids])),
            )
        )
    bookings = bookings.order_by(Booking.created_at.desc()).all()

    total_bookings = len(bookings)
    confirmed      = sum(1 for b in bookings if b.status == "confirmed")
    total_revenue  = sum(b.amount for b in bookings if b.status == "confirmed")
    pending_count  = sum(1 for b in bookings if b.status == "pending")

    reviews = []
    if my_stay_ids or my_experience_ids:
        reviews = Review.query.filter(
            db.or_(
                db.and_(Review.item_type == "accommodation", Review.item_id.in_([str(x) for x in my_stay_ids])),
                db.and_(Review.item_type == "experience",    Review.item_id.in_([str(x) for x in my_experience_ids])),
            )
        ).order_by(Review.created_at.desc()).limit(10).all()

    unread_notifications = Notification.query.filter_by(
        user_id=current_user_id, is_read=False
    ).count()

    return render_template(
        "host_dashboard.html",
        host=host,
        bookings=bookings,
        stats={
            "total_bookings": total_bookings,
            "confirmed":      confirmed,
            "pending":        pending_count,
            "total_revenue":  total_revenue,
        },
        recent_reviews=reviews,
        unread_notifications=unread_notifications,
    )


@app.route("/host/edit-profile", methods=["GET", "POST"])
@jwt_required()
def host_edit_profile():
    """Allow hosts to update their bio, listing details, and contact info."""
    current_user_id = get_jwt_identity()
    host = User.query.get_or_404(current_user_id)

    if request.method == "POST":
        data = request.get_json() or request.form
        host.bio          = data.get("bio", getattr(host, 'bio', ''))
        host.booking_type = data.get("booking_type", host.booking_type)
        db.session.commit()
        return jsonify({"status": "success", "message": "Profile updated."})

    return render_template("host_edit_profile.html", host=host)


# ── Phase 8 — Guide Availability Calendar — Feature #59 ──────────────────────

@app.route("/api/availability/<int:guide_id>", methods=["GET"])
def get_availability(guide_id):
    """Returns list of blocked dates for a guide. Called by booking.html."""
    blocked = Availability.query.filter_by(guide_id=guide_id).all()
    return jsonify({
        "status":        "success",
        "blocked_dates": [str(a.date) for a in blocked],
    })


@app.route("/api/availability", methods=["POST"])
@jwt_required()
def block_date():
    """Guide blocks a date on their calendar. Body: { date, reason }"""
    current_user_id = int(get_jwt_identity())
    guide = User.query.get_or_404(current_user_id)

    if guide.role not in ("guide", "admin"):
        return jsonify({"status": "error", "message": "Not authorised"}), 403

    data     = request.get_json()
    date_str = data.get("date")
    reason   = data.get("reason", "")

    if not date_str:
        return jsonify({"status": "error", "message": "date is required"}), 400

    try:
        from datetime import date as date_type
        block_date_obj = date_type.fromisoformat(date_str)
    except ValueError:
        return jsonify({"status": "error", "message": "Invalid date format. Use YYYY-MM-DD"}), 400

    existing = Availability.query.filter_by(guide_id=current_user_id, date=block_date_obj).first()
    if existing:
        return jsonify({"status": "success", "message": "Date already blocked.", "id": existing.id})

    avail = Availability(guide_id=current_user_id, date=block_date_obj, reason=reason)
    db.session.add(avail)
    db.session.commit()
    return jsonify({"status": "success", "message": "Date blocked.", "id": avail.id})


@app.route("/api/availability/<int:availability_id>", methods=["DELETE"])
@jwt_required()
def unblock_date(availability_id):
    """Guide unblocks a previously blocked date."""
    current_user_id = int(get_jwt_identity())
    avail = Availability.query.filter_by(id=availability_id, guide_id=current_user_id).first()
    if not avail:
        return jsonify({"status": "error", "message": "Blocked date not found"}), 404
    db.session.delete(avail)
    db.session.commit()
    return jsonify({"status": "success", "message": "Date unblocked."})


@app.route("/dashboard/availability")
@jwt_required()
def guide_availability_page():
    """Renders the guide's availability calendar management page."""
    current_user_id = int(get_jwt_identity())
    guide = User.query.get_or_404(current_user_id)
    blocked = Availability.query.filter_by(guide_id=current_user_id)\
                                .order_by(Availability.date).all()
    return render_template("guide_availability.html", guide=guide, blocked_dates=blocked)


# ── Phase 8 — Rating & Review System — Feature #82 ───────────────────────

@app.route("/api/reviews", methods=["POST"])
@jwt_required()
def submit_review():
    """
    Tourist submits a review for a completed booking. (Phase 8 version)
    Replaces the original /api/reviews POST.
    """
    current_user_id = int(get_jwt_identity())
    data = request.get_json()

    booking_id = data.get("booking_id")
    rating     = data.get("rating")
    comment    = data.get("comment", "").strip()

    if not booking_id or rating is None:
        return jsonify({"status": "error", "message": "booking_id and rating are required"}), 400

    try:
        rating = int(rating)
        if not 1 <= rating <= 5:
            raise ValueError
    except (ValueError, TypeError):
        return jsonify({"status": "error", "message": "Rating must be an integer between 1 and 5"}), 400

    # BUG FIX: use user_id (actual column) not tourist_id (property alias)
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first()
    if not booking:
        return jsonify({"status": "error", "message": "Booking not found"}), 404

    if booking.status != "confirmed":
        return jsonify({"status": "error", "message": "You can only review confirmed bookings"}), 400

    existing = Review.query.filter_by(booking_id=booking_id).first()
    if existing:
        return jsonify({"status": "error", "message": "You have already reviewed this booking"}), 409

    review = Review(
        tourist_id = current_user_id,
        user_id    = current_user_id,
        booking_id = booking_id,
        item_type  = booking.item_type,
        item_id    = str(booking.item_id),
        rating     = rating,
        comment    = comment if comment else None,
    )
    db.session.add(review)
    db.session.commit()

    # Notify guide/host of new review
    try:
        if booking.item_type == "guide":
            guide_obj  = db.session.get(Guide, booking.item_id)
            guide_user = User.query.get(guide_obj.user_id) if guide_obj else None
            if guide_user:
                notify_review_received(review, guide_user)
    except Exception as e:
        app.logger.error(f"[REVIEW] Notification failed: {e}")

    return jsonify({"status": "success", "message": "Review submitted.", "review": review.to_dict()}), 201


@app.route("/api/reviews/<string:item_type>/<string:item_id>", methods=["GET"])
def get_reviews(item_type, item_id):
    """Get all visible reviews for a guide, stay, or experience."""
    if item_type not in ("guide", "accommodation", "experience"):
        return jsonify({"status": "error", "message": "Invalid item type"}), 400

    reviews = Review.query.filter_by(
        item_type=item_type,
        item_id=str(item_id),
        is_visible=True,
    ).order_by(Review.created_at.desc()).all()

    avg_rating = (
        sum(r.rating for r in reviews) / len(reviews) if reviews else 0
    )

    return jsonify({
        "status":     "success",
        "count":      len(reviews),
        "avg_rating": round(avg_rating, 1),
        "reviews":    [r.to_dict() for r in reviews],
    })


@app.route("/api/admin/reviews/<int:review_id>/hide", methods=["POST"])
@jwt_required()
def admin_hide_review(review_id):
    """Admin hides an abusive review."""
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    review = Review.query.get_or_404(review_id)
    review.is_visible = False
    db.session.commit()
    return jsonify({"status": "success", "message": "Review hidden."})


# ── Phase 8 — In-App Notification Center — Feature #80 ──────────────────

@app.route("/api/notifications", methods=["GET"])
@jwt_required()
def get_notifications():
    """Returns the current user's notifications, newest first."""
    current_user_id = int(get_jwt_identity())
    unread_only = request.args.get("unread_only", "false").lower() == "true"
    limit       = min(int(request.args.get("limit", 20)), 50)

    q = Notification.query.filter_by(user_id=current_user_id)
    if unread_only:
        q = q.filter_by(is_read=False)

    notifications = q.order_by(Notification.created_at.desc()).limit(limit).all()
    unread_count  = Notification.query.filter_by(user_id=current_user_id, is_read=False).count()

    return jsonify({
        "status":        "success",
        "unread_count":  unread_count,
        "notifications": [n.to_dict() for n in notifications],
    })


@app.route("/api/notifications/<int:notif_id>/read", methods=["POST"])
@jwt_required()
def mark_notification_read(notif_id):
    """Mark a single notification as read."""
    current_user_id = int(get_jwt_identity())
    notif = Notification.query.filter_by(id=notif_id, user_id=current_user_id).first()
    if not notif:
        return jsonify({"status": "error", "message": "Notification not found"}), 404
    notif.is_read = True
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/api/notifications/read-all", methods=["POST"])
@jwt_required()
def mark_all_notifications_read():
    """Mark all of the current user's notifications as read."""
    current_user_id = int(get_jwt_identity())
    Notification.query.filter_by(user_id=current_user_id, is_read=False)\
                      .update({"is_read": True})
    db.session.commit()
    return jsonify({"status": "success", "message": "All notifications marked as read."})


@app.route("/notifications")
@jwt_required()
def notification_center():
    """Renders the full notification inbox page."""
    current_user_id = int(get_jwt_identity())
    notifications   = Notification.query.filter_by(user_id=current_user_id)\
                                        .order_by(Notification.created_at.desc())\
                                        .limit(50).all()
    for n in notifications:
        n.is_read = True
    db.session.commit()
    return render_template("notification_center.html", notifications=notifications)


@app.route("/api/notifications/register-token", methods=["POST"])
@jwt_required()
def register_fcm_token():
    """Register a device FCM token for push notifications."""
    from models import UserFCMToken
    current_user_id = int(get_jwt_identity())
    data     = request.get_json()
    token    = data.get("token")
    platform = data.get("platform", "web")

    if not token:
        return jsonify({"status": "error", "message": "token is required"}), 400

    try:
        existing = UserFCMToken.query.filter_by(user_id=current_user_id, token=token).first()
        if not existing:
            fcm_token = UserFCMToken(user_id=current_user_id, token=token, platform=platform)
            db.session.add(fcm_token)
            db.session.commit()
        return jsonify({"status": "success"})
    except Exception as e:
        app.logger.error(f"[FCM] Token registration failed: {e}")
        return jsonify({"status": "success"})  # Silent fail


# =============================================================================
# DAY 3 — Escrow, Pricing, Commission
# =============================================================================

@app.route("/api/escrow/status/<int:booking_id>", methods=["GET"])
@jwt_required()
def get_escrow_status(booking_id):
    """Returns current escrow status for a booking."""
    current_user_id = int(get_jwt_identity())
    # BUG FIX: use user_id column directly
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first()
    if not booking:
        return jsonify({"status": "error", "message": "Booking not found"}), 404

    escrow = EscrowTransaction.query.filter_by(booking_id=booking_id).first()
    if not escrow:
        return jsonify({"status": "success", "escrow": None})
    return jsonify({"status": "success", "escrow": escrow.to_dict()})


@app.route("/api/escrow/settle/<int:booking_id>", methods=["POST"])
@jwt_required()
def settle_escrow_route(booking_id):
    """Tourist taps 'Tour Completed' — triggers escrow settlement."""
    current_user_id = int(get_jwt_identity())
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first()

    if not booking:
        return jsonify({"status": "error", "message": "Booking not found"}), 404
    if booking.status != "confirmed":
        return jsonify({"status": "error", "message": "Booking is not in a confirmed state"}), 400

    escrow = EscrowTransaction.query.filter_by(booking_id=booking_id).first()
    if not escrow:
        return jsonify({"status": "error", "message": "No escrow found for this booking"}), 404
    if escrow.status != "holding":
        return jsonify({"status": "error", "message": f"Escrow is already {escrow.status}."}), 400

    guide_sub_account = None
    if booking.item_type == "guide":
        guide_obj  = db.session.get(Guide, booking.item_id)
        guide_user = User.query.get(guide_obj.user_id) if guide_obj else None
        guide_sub_account = getattr(guide_user, "flw_sub_account_id", None) if guide_user else None

    result = settle_escrow(escrow, guide_sub_account)

    if result["status"] == "success":
        return jsonify({
            "status":  "success",
            "message": "Tour confirmed. Payment has been released to your guide.",
            "settlement": {
                "gross":       result["gross_amount"],
                "commission":  result["commission"],
                "net_to_guide":result["net_to_operator"],
                "currency":    result["currency"],
            },
        })
    else:
        app.logger.error(f"[ESCROW] Settlement failed for booking #{booking_id}: {result}")
        return jsonify({"status": "error", "message": "Settlement processing error. Our team has been notified."}), 500


@app.route("/escrow/confirm/<int:booking_id>")
@jwt_required()
def escrow_confirm_page(booking_id):
    """Tour completion confirmation page."""
    current_user_id = int(get_jwt_identity())
    booking = Booking.query.filter_by(id=booking_id, user_id=current_user_id).first_or_404()
    escrow  = EscrowTransaction.query.filter_by(booking_id=booking_id).first()

    commission_rate = app.config.get("COMMISSION_RATE", 0.10)
    net_to_guide = round(escrow.escrow_amount * (1 - commission_rate), 2) if escrow else None

    return render_template(
        "escrow_confirm.html",
        booking=booking,
        escrow=escrow,
        net_to_guide=net_to_guide,
        commission_pct=int(commission_rate * 100),
    )


# ── Phase 8 — Dynamic Pricing Engine — Feature #52 ─────────────────────────

@app.route("/dashboard/pricing")
@jwt_required()
def pricing_dashboard():
    """Guide/Host views and manages their dynamic pricing rules."""
    current_user_id = int(get_jwt_identity())
    operator = User.query.get_or_404(current_user_id)
    rules = PricingRule.query.filter_by(operator_id=current_user_id).all()
    return render_template("guide_pricing.html", operator=operator, rules=rules)


@app.route("/api/pricing/rules", methods=["GET"])
@jwt_required()
def get_pricing_rules():
    """Returns all pricing rules for the current operator."""
    current_user_id = int(get_jwt_identity())
    rules = PricingRule.query.filter_by(operator_id=current_user_id).all()
    return jsonify({"status": "success", "rules": [r.to_dict() for r in rules]})


@app.route("/api/pricing/rules", methods=["POST"])
@jwt_required()
def create_pricing_rule():
    """Create or update a pricing rule for a listing."""
    current_user_id = int(get_jwt_identity())
    data = request.get_json()
    item_type = data.get("item_type")
    item_id   = data.get("item_id")

    if not item_type or not item_id:
        return jsonify({"status": "error", "message": "item_type and item_id are required"}), 400

    for field in ("low_load_multiplier", "high_load_multiplier", "last_minute_multiplier"):
        val = data.get(field)
        if val is not None and not (0.5 <= float(val) <= 3.0):
            return jsonify({"status": "error", "message": f"{field} must be between 0.5 and 3.0"}), 400

    rule = PricingRule.query.filter_by(
        operator_id=current_user_id, item_type=item_type, item_id=item_id
    ).first()

    if not rule:
        rule = PricingRule(operator_id=current_user_id, item_type=item_type, item_id=item_id)
        db.session.add(rule)

    rule.low_load_threshold     = float(data.get("low_load_threshold",     rule.low_load_threshold or 25.0))
    rule.low_load_multiplier    = float(data.get("low_load_multiplier",     rule.low_load_multiplier or 0.85))
    rule.high_load_threshold    = float(data.get("high_load_threshold",    rule.high_load_threshold or 75.0))
    rule.high_load_multiplier   = float(data.get("high_load_multiplier",   rule.high_load_multiplier or 1.20))
    rule.last_minute_hours      = int(data.get("last_minute_hours",        rule.last_minute_hours or 48))
    rule.last_minute_multiplier = float(data.get("last_minute_multiplier", rule.last_minute_multiplier or 0.90))
    rule.max_capacity           = int(data.get("max_capacity",             rule.max_capacity or 10))
    rule.is_active              = bool(data.get("is_active", True))
    db.session.commit()
    return jsonify({"status": "success", "message": "Pricing rule saved.", "rule": rule.to_dict()})


@app.route("/api/pricing/rules/<int:rule_id>", methods=["DELETE"])
@jwt_required()
def delete_pricing_rule(rule_id):
    """Delete a pricing rule (operator only)."""
    current_user_id = int(get_jwt_identity())
    rule = PricingRule.query.filter_by(id=rule_id, operator_id=current_user_id).first()
    if not rule:
        return jsonify({"status": "error", "message": "Rule not found"}), 404
    db.session.delete(rule)
    db.session.commit()
    return jsonify({"status": "success", "message": "Pricing rule deleted."})


@app.route("/api/pricing/compute", methods=["POST"])
def compute_price():
    """Public endpoint — returns the dynamic price for a listing."""
    data           = request.get_json()
    item_type      = data.get("item_type")
    item_id        = data.get("item_id")
    base_price     = float(data.get("base_price", 0))
    scheduled_date = data.get("scheduled_date")

    if not all([item_type, item_id, base_price]):
        return jsonify({"status": "error", "message": "item_type, item_id, and base_price are required"}), 400

    if scheduled_date:
        from datetime import date
        try:
            scheduled_date = date.fromisoformat(scheduled_date)
        except ValueError:
            scheduled_date = None

    result = compute_dynamic_price(base_price, item_type, int(item_id), scheduled_date)
    return jsonify({"status": "success", **result})


# ── Phase 8 — Commission Ledger — Feature #53 ─────────────────────────────

@app.route("/api/admin/commission", methods=["GET"])
@jwt_required()
def get_commission_ledger():
    """Admin view of all commission extractions."""
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    limit  = min(int(request.args.get("limit", 50)), 200)
    offset = int(request.args.get("offset", 0))

    records          = CommissionLedger.query.order_by(CommissionLedger.extracted_at.desc())\
                                             .limit(limit).offset(offset).all()
    total            = CommissionLedger.query.count()
    total_commission = db.session.query(db.func.sum(CommissionLedger.commission_amount)).scalar() or 0

    return jsonify({
        "status":           "success",
        "total_records":    total,
        "total_commission": round(total_commission, 2),
        "records":          [r.to_dict() for r in records],
    })


# =============================================================================
# DAY 4 — KYC, Video Intros, Booking Type
# =============================================================================

@app.route("/dashboard/kyc")
@jwt_required()
def kyc_page():
    """Guide KYC submission page."""
    current_user_id = int(get_jwt_identity())
    guide  = User.query.get_or_404(current_user_id)
    status = get_kyc_status(current_user_id)
    return render_template("kyc_submit.html", guide=guide, kyc=status)


@app.route("/api/kyc/submit", methods=["POST"])
@jwt_required()
def submit_kyc_route():
    """Guide submits identity verification documents."""
    current_user_id = int(get_jwt_identity())
    guide = User.query.get_or_404(current_user_id)

    if guide.role not in ("guide", "operator"):
        return jsonify({"status": "error", "message": "KYC is for guides and operators only"}), 403

    id_type   = request.form.get("id_type", "NATIONAL_ID")
    id_number = request.form.get("id_number", "")
    country   = request.form.get("country", "TZ")

    if not id_number:
        return jsonify({"status": "error", "message": "id_number is required"}), 400

    import base64
    selfie_b64 = None
    id_b64     = None

    if "selfie_image" in request.files:
        selfie_file = request.files["selfie_image"]
        if selfie_file.filename:
            selfie_b64 = base64.b64encode(selfie_file.read()).decode("utf-8")

    if "id_image" in request.files:
        id_file = request.files["id_image"]
        if id_file.filename:
            id_b64 = base64.b64encode(id_file.read()).decode("utf-8")

    result = submit_kyc(
        guide_id            = current_user_id,
        id_type             = id_type,
        id_number           = id_number,
        country             = country,
        selfie_image_base64 = selfie_b64,
        id_image_base64     = id_b64,
    )

    try:
        admin_users = User.query.filter_by(is_admin=True).all()
        for admin in admin_users:
            notify(
                user_id    = admin.id,
                notif_type = "general",
                title      = "New KYC Submission",
                message    = f"Guide #{current_user_id} ({guide.username}) submitted KYC ({id_type}).",
                link       = f"/admin/kyc/{current_user_id}",
            )
    except Exception as e:
        app.logger.error(f"[KYC] Admin notification failed: {e}")

    if result.get("async_mode"):
        return jsonify({"status": "success",
                        "message": "Your documents have been submitted for review. We'll notify you of the result.",
                        "verify_url": result.get("verify_url")})

    if result.get("success"):
        kyc_status = get_kyc_status(current_user_id)
        return jsonify({"status": "success", "message": "Verification submitted.", "kyc_status": kyc_status.get("status")})

    return jsonify({"status": "error", "message": "Verification could not be completed. Please try again."}), 422


@app.route("/api/kyc/sumsub-webhook", methods=["POST"])
def sumsub_webhook():
    """Receives async verification results from Sumsub."""
    payload = request.get_json()
    success = process_sumsub_webhook(payload)
    return jsonify({"status": "success" if success else "error"}), 200


@app.route("/admin/kyc")
@jwt_required()
def admin_kyc_list():
    """Admin views all pending KYC submissions."""
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return redirect(url_for("index"))

    pending  = KYCRecord.query.filter_by(status="pending").order_by(KYCRecord.submitted_at.desc()).all()
    flagged  = KYCRecord.query.filter_by(status="flagged").order_by(KYCRecord.submitted_at.desc()).all()
    approved = KYCRecord.query.filter_by(status="approved").order_by(KYCRecord.reviewed_at.desc()).limit(20).all()
    rejected = KYCRecord.query.filter_by(status="rejected").order_by(KYCRecord.reviewed_at.desc()).limit(10).all()

    return render_template("admin_kyc.html", pending=pending, flagged=flagged,
                           approved=approved, rejected=rejected)


@app.route("/api/admin/kyc/<int:guide_id>/approve", methods=["POST"])
@jwt_required()
def admin_approve_kyc(guide_id):
    """Admin approves a guide's KYC submission."""
    from services.notification_service import notify_kyc_result
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    record = KYCRecord.query.filter_by(guide_id=guide_id).first()
    if not record:
        return jsonify({"status": "error", "message": "KYC record not found"}), 404

    record.status      = "approved"
    record.reviewed_at = datetime.utcnow()
    notes_data = request.get_json() or {}
    record.admin_notes = notes_data.get("notes", "")

    guide = User.query.get(guide_id)
    if guide:
        guide.is_verified = True
        video = GuideVideo.query.filter_by(guide_id=guide_id, status="pending").first()
        if video:
            video.status = "approved"
            video.approved_at = datetime.utcnow()

    db.session.commit()

    if guide:
        notify_kyc_result(guide, approved=True)

    return jsonify({"status": "success", "message": f"KYC approved for guide #{guide_id}."})


@app.route("/api/admin/kyc/<int:guide_id>/reject", methods=["POST"])
@jwt_required()
def admin_reject_kyc(guide_id):
    """Admin rejects a guide's KYC submission."""
    from services.notification_service import notify_kyc_result
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    data   = request.get_json() or {}
    reason = data.get("reason", "Documents could not be verified.")

    record = KYCRecord.query.filter_by(guide_id=guide_id).first()
    if not record:
        return jsonify({"status": "error", "message": "KYC record not found"}), 404

    record.status      = "rejected"
    record.reviewed_at = datetime.utcnow()
    record.admin_notes = reason
    db.session.commit()

    guide = User.query.get(guide_id)
    if guide:
        notify_kyc_result(guide, approved=False, reason=reason)

    return jsonify({"status": "success", "message": f"KYC rejected for guide #{guide_id}."})


# ── Phase 8 — Guide Video Introductions — Feature #60 ─────────────────────

@app.route("/api/guide/video", methods=["POST"])
@jwt_required()
def upload_guide_video():
    """Guide uploads a 60-second video introduction."""
    current_user_id = int(get_jwt_identity())
    guide = User.query.get_or_404(current_user_id)

    if "video" not in request.files:
        return jsonify({"status": "error", "message": "No video file provided"}), 400

    video_file = request.files["video"]
    if not video_file.filename:
        return jsonify({"status": "error", "message": "Empty file"}), 400

    allowed_mimes = {"video/mp4", "video/quicktime", "video/webm"}
    if video_file.mimetype not in allowed_mimes:
        return jsonify({"status": "error", "message": "Only MP4, MOV, and WebM videos are accepted"}), 400

    try:
        upload_result = cloudinary.uploader.upload(
            video_file,
            resource_type  = "video",
            folder         = f"safaraone/guide_intros/{current_user_id}",
            public_id      = f"guide_{current_user_id}_intro",
            overwrite      = True,
            transformation = [{"duration": 60}, {"quality": "auto"}, {"fetch_format": "auto"}],
            eager          = [{"format": "jpg", "transformation": [{"start_offset": "2"}]}],
            eager_async    = True,
        )
    except Exception as e:
        app.logger.error(f"[VIDEO] Cloudinary upload failed for guide #{current_user_id}: {e}")
        return jsonify({"status": "error", "message": "Video upload failed. Please try again."}), 500

    kyc_status   = get_kyc_status(current_user_id)
    auto_approve = kyc_status.get("status") == "approved"

    video = GuideVideo.query.filter_by(guide_id=current_user_id).first()
    if not video:
        video = GuideVideo(guide_id=current_user_id)
        db.session.add(video)

    video.cloudinary_public_id = upload_result.get("public_id", "")
    video.cloudinary_url       = upload_result.get("secure_url", "")
    video.duration_seconds     = int(upload_result.get("duration", 0) or 0)
    video.status               = "approved" if auto_approve else "pending"
    video.approved_at          = datetime.utcnow() if auto_approve else None
    video.rejection_reason     = None

    eager = upload_result.get("eager", [])
    if eager:
        video.cloudinary_thumbnail = eager[0].get("secure_url")

    db.session.commit()
    return jsonify({
        "status":       "success",
        "message":      "Video uploaded successfully." if auto_approve else "Video uploaded and pending admin review.",
        "video_url":    video.cloudinary_url,
        "thumbnail":    video.cloudinary_thumbnail,
        "video_status": video.status,
    })


@app.route("/api/guide/video", methods=["DELETE"])
@jwt_required()
def delete_guide_video():
    """Guide removes their video introduction."""
    current_user_id = int(get_jwt_identity())
    video = GuideVideo.query.filter_by(guide_id=current_user_id).first()
    if not video:
        return jsonify({"status": "error", "message": "No video found"}), 404

    try:
        cloudinary.uploader.destroy(video.cloudinary_public_id, resource_type="video")
    except Exception as e:
        app.logger.warning(f"[VIDEO] Cloudinary delete failed (continuing): {e}")

    db.session.delete(video)
    db.session.commit()
    return jsonify({"status": "success", "message": "Video removed."})


@app.route("/api/admin/videos/<int:guide_id>/approve", methods=["POST"])
@jwt_required()
def admin_approve_video(guide_id):
    """Admin approves a guide's video intro."""
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    video = GuideVideo.query.filter_by(guide_id=guide_id).first()
    if not video:
        return jsonify({"status": "error", "message": "Video not found"}), 404

    video.status      = "approved"
    video.approved_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"status": "success"})


@app.route("/api/admin/videos/<int:guide_id>/reject", methods=["POST"])
@jwt_required()
def admin_reject_video(guide_id):
    """Admin rejects a guide's video intro."""
    current_user_id = int(get_jwt_identity())
    admin = User.query.get_or_404(current_user_id)
    if not admin.is_admin:
        return jsonify({"status": "error", "message": "Forbidden"}), 403

    data   = request.get_json() or {}
    reason = data.get("reason", "Video does not meet our content guidelines.")

    video = GuideVideo.query.filter_by(guide_id=guide_id).first()
    if not video:
        return jsonify({"status": "error", "message": "Video not found"}), 404

    video.status           = "rejected"
    video.rejection_reason = reason
    db.session.commit()

    guide = User.query.get(guide_id)
    if guide:
        notify(
            user_id    = guide.id,
            notif_type = "general",
            title      = "Video Introduction Rejected",
            message    = f"Your intro video was not approved. Reason: {reason}",
            link       = "/dashboard",
        )
    return jsonify({"status": "success"})


# ── Phase 8 — Instant vs Request Booking Indicators — Feature #35 ─────────

@app.route("/api/guide/<int:guide_id>/booking-type", methods=["GET"])
def get_guide_booking_type(guide_id):
    """Returns whether a guide offers instant confirmation or requires approval."""
    guide_user = User.query.get(guide_id)
    if not guide_user:
        # Try looking up by Guide.id → User
        guide_obj  = db.session.get(Guide, str(guide_id))
        guide_user = User.query.get(guide_obj.user_id) if guide_obj else None
    if not guide_user:
        return jsonify({"status": "error", "message": "Guide not found"}), 404

    booking_type = getattr(guide_user, "booking_type", "request") or "request"
    return jsonify({
        "status":       "success",
        "booking_type": booking_type,
        "label":        "Instant Confirmation" if booking_type == "instant" else "Awaiting Approval (24hr)",
        "description":  (
            "Your booking will be confirmed immediately after payment."
            if booking_type == "instant"
            else "The guide will review your request and confirm within 24 hours of payment."
        ),
    })


@app.route("/api/guide/booking-type", methods=["POST"])
@jwt_required()
def set_guide_booking_type():
    """Guide sets their booking confirmation type."""
    current_user_id = int(get_jwt_identity())
    guide = User.query.get_or_404(current_user_id)
    data  = request.get_json() or {}
    btype = data.get("booking_type", "request")

    if btype not in ("instant", "request"):
        return jsonify({"status": "error", "message": "booking_type must be 'instant' or 'request'"}), 400

    guide.booking_type = btype
    db.session.commit()
    return jsonify({"status": "success", "booking_type": btype})
