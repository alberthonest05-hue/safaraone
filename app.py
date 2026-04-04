"""
SafaraOne — All-in-One Travel Planning Platform
Python Flask Web Application
Author: SafaraOne Team
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, make_response
from dotenv import load_dotenv
import os
import uuid

# Phase 2: Load environment variables FIRST before importing models/services
load_dotenv()

from models import db, User, Destination, Accommodation, Experience, Guide, Booking, Review
from sqlalchemy import distinct
from flask_jwt_extended import (
    JWTManager, create_access_token, jwt_required, get_jwt_identity, 
    set_access_cookies, unset_jwt_cookies
)
from flask_cors import CORS

# Phase 2B: Use DB-constrained OpenAI Planner from services
from services.planner import generate_itinerary

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "safaraone-secret-key-2025")
CORS(app, supports_credentials=True)

# Database Configuration
db_url = os.environ.get('DATABASE_URL', 'sqlite:///safaraone.db')
if db_url.startswith('postgres://'):
    db_url = db_url.replace('postgres://', 'postgresql://', 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'connect_args': {
        'sslmode': 'require'
    },
    'pool_pre_ping': True,
    'pool_recycle': 300,
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


with app.app_context():
    db.create_all()


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

import stripe
from datetime import datetime
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "sk_test_placeholder")

@app.route("/api/bookings", methods=["POST"])
@jwt_required()
def api_create_booking():
    VALID_ITEM_TYPES = {"accommodation", "experience", "guide"}
    data = request.get_json()
    user_id = int(get_jwt_identity())
    
    item_type = data.get("item_type")
    amount_usd = float(data.get("amount_usd", 0))
    item_id = data.get("item_id")
    
    if not item_type or item_type not in VALID_ITEM_TYPES:
        return jsonify({"error": "Invalid or missing item_type"}), 400
    if amount_usd <= 0:
        return jsonify({"error": "Amount must be greater than 0"}), 400
    if not item_id:
        return jsonify({"error": "Missing item_id"}), 400
    
    scheduled_date_str = data.get("scheduled_date")
    scheduled_date = None
    if scheduled_date_str:
        try:
            scheduled_date = datetime.fromisoformat(scheduled_date_str)
        except ValueError:
            pass

    booking = Booking(
        user_id=user_id,
        item_type=data.get("item_type"),   # 'guide', 'accommodation', 'experience'
        item_id=data.get("item_id"),
        amount_usd=float(data.get("amount_usd", 0)),
        num_guests=int(data.get("num_guests", 1)),
        scheduled_date=scheduled_date
    )
    db.session.add(booking)
    db.session.commit()
    return jsonify({"booking_id": booking.id}), 201

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


@app.route("/api/reviews", methods=["POST"])
@jwt_required()
def api_post_review():
    data = request.get_json()
    user_id = int(get_jwt_identity())
    
    item_type = data.get("item_type")
    item_id = data.get("item_id")
    rating = int(data.get("rating", 5))
    comment = data.get("comment", "")
    
    if not item_type or not item_id:
        return jsonify({"error": "Missing item info"}), 400
        
    if not 1 <= rating <= 5:
        return jsonify({"error": "Rating must be between 1 and 5"}), 400
        
    try:
        review = Review(
            user_id=user_id,
            item_type=item_type,
            item_id=item_id,
            rating=rating,
            comment=comment
        )
        db.session.add(review)
        db.session.commit()
        
        # Optionally update the parent aggregate rating
        if item_type == "guide":
            guide = db.session.get(Guide, item_id)
            if guide:
                total_r = guide.total_reviews or 0
                current_rt = guide.rating or 0.0
                new_total = total_r + 1
                new_rating = ((current_rt * total_r) + rating) / new_total
                guide.rating = round(new_rating, 1)
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
    specializations = data.get("specializations", [])
    languages = data.get("languages", [])
    image_url = data.get("image_url", "https://images.unsplash.com/photo-1547471080-7cc2caa01a7e?w=800")
    
    # We allow specialization as a string for backward compat if needed, but the form sends a list
    spec_str = specialization if isinstance(data.get("specialization"), str) else ", ".join(specializations)

    if not all([name, bio, price, dest_id]):
        return jsonify({"error": "Missing required fields (name, bio, rate, destination)"}), 400

    try:
        # 1. Create the Guide profile
        new_guide = Guide(
            user_id=user_id,
            name=name,
            specialization=spec_str,
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
    user = User.query.get(user_id)
    if not user or user.role != "admin":
        return redirect(url_for("index"))
    
    users = User.query.all()
    return render_template("admin_dashboard.html", users=users)


@app.route("/api/admin/users/<int:user_id>", methods=["DELETE"])
@jwt_required()
def api_admin_delete_user(user_id):
    current_admin_id = int(get_jwt_identity())
    admin_user = User.query.get(current_admin_id)
    if not admin_user or admin_user.role != "admin":
        return jsonify({"error": "Unauthorized"}), 403
    
    user_to_delete = User.query.get(user_id)
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


@app.route('/api/setup/force-seed')
@app.route('/api/setup/force-seed')
def force_seed():
    try:
        from seed_db import seed
        seed()
        return 'Database seeded successfully!'
    except Exception as e:
        import traceback
        return f'Seeding failed: {traceback.format_exc()}'


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


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)
