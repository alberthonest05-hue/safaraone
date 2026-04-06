from extensions import db  # Single source of truth — no circular import risk
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=False, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="tourist") # "tourist", "guide", "admin"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # ── Phase 8 additions ──────────────────────────────────────────────────
    # "instant" = confirm right after payment | "request" = guide reviews first
    booking_type       = db.Column(db.String(20), nullable=True, default="request")
    # Flutterwave sub-account ID for automated payouts
    flw_sub_account_id = db.Column(db.String(100), nullable=True)
    # Set to True by admin after KYC is approved
    is_verified        = db.Column(db.Boolean, default=False)
    # Admin flag
    is_admin           = db.Column(db.Boolean, default=False)

    def set_password(self, password):
        # We remove the hardcoded method and let the system use its most modern default scrambler
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        # If no password is provided, don't crash, just reject the login
        if not password:
            return False
        return check_password_hash(self.password_hash, password)


class Destination(db.Model):
    id = db.Column(db.String(50), primary_key=True) # e.g. "zanzibar"
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50))
    region = db.Column(db.String(100))
    tagline = db.Column(db.String(255))
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    average_daily_budget_usd = db.Column(db.Float)
    best_months = db.Column(db.String(100))
    language = db.Column(db.String(100))
    currency = db.Column(db.String(50))
    gallery = db.Column(db.JSON)
    highlights = db.Column(db.JSON)
    stats = db.Column(db.JSON)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "country": self.country,
            "region": self.region,
            "tagline": self.tagline,
            "description": self.description,
            "image_url": self.image_url,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "average_daily_budget_usd": self.average_daily_budget_usd,
            "best_months": self.best_months,
            "language": self.language,
            "currency": self.currency,
            "gallery": self.gallery,
            "highlights": self.highlights,
            "stats": self.stats
        }


class Accommodation(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    destination_id = db.Column(db.String(50), db.ForeignKey('destination.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50)) # e.g., "luxury resort"
    tier = db.Column(db.String(50)) # "luxury", "mid-range", "budget"
    price_per_night_usd = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer, default=0)
    amenities = db.Column(db.JSON)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    booking_url = db.Column(db.String(500))

    def to_dict(self):
        return {
            "id": self.id,
            "destination_id": self.destination_id,
            "name": self.name,
            "type": self.type,
            "tier": self.tier,
            "price_per_night_usd": self.price_per_night_usd,
            "rating": self.rating,
            "review_count": self.review_count,
            "amenities": self.amenities,
            "description": self.description,
            "image_url": self.image_url,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "booking_url": self.booking_url
        }


class Experience(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    destination_id = db.Column(db.String(50), db.ForeignKey('destination.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(50))
    tier = db.Column(db.String(50))
    price_usd = db.Column(db.Float, nullable=False)
    duration_hours = db.Column(db.Float)
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer, default=0)
    max_participants = db.Column(db.Integer)
    description = db.Column(db.Text)
    image_url = db.Column(db.String(500))
    tags = db.Column(db.JSON)
    is_indoor = db.Column(db.Boolean, default=False)
    booking_url = db.Column(db.String(500))

    def to_dict(self):
        return {
            "id": self.id,
            "destination_id": self.destination_id,
            "title": self.title,
            "category": self.category,
            "tier": self.tier,
            "price_usd": self.price_usd,
            "duration_hours": self.duration_hours,
            "rating": self.rating,
            "review_count": self.review_count,
            "max_participants": self.max_participants,
            "description": self.description,
            "image_url": self.image_url,
            "tags": self.tags,
            "is_indoor": self.is_indoor,
            "booking_url": self.booking_url
        }


class Guide(db.Model):
    id = db.Column(db.String(50), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True) # Optional link to User account
    destination_id = db.Column(db.String(50), db.ForeignKey('destination.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    avatar_url = db.Column(db.String(500))
    title = db.Column(db.String(200)) # e.g. "Stone Town Heritage Expert"
    languages = db.Column(db.JSON)
    specializations = db.Column(db.JSON)
    price_per_day_usd = db.Column(db.Float, nullable=False)
    rating = db.Column(db.Float, default=0.0)
    total_reviews = db.Column(db.Integer, default=0)
    experience_years = db.Column(db.Integer)
    bio = db.Column(db.Text)
    certifications = db.Column(db.JSON)
    availability = db.Column(db.String(100))
    is_verified = db.Column(db.Boolean, default=False)
    stripe_account_id = db.Column(db.String(255)) # For Phase 2C Split Payments

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "destination_id": self.destination_id,
            "name": self.name,
            "avatar_url": self.avatar_url,
            "title": self.title,
            "languages": self.languages,
            "specializations": self.specializations,
            "price_per_day_usd": self.price_per_day_usd,
            "rating": self.rating,
            "total_reviews": self.total_reviews,
            "experience_years": self.experience_years,
            "bio": self.bio,
            "certifications": self.certifications,
            "availability": self.availability,
            "is_verified": self.is_verified
        }


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_type = db.Column(db.String(50), nullable=False)  # 'accommodation', 'experience', 'guide'
    item_id = db.Column(db.String(50), nullable=False)
    item_name = db.Column(db.String(200), nullable=True)  # Human-readable name — stored at booking time
    amount_usd = db.Column(db.Float, nullable=False)
    num_guests = db.Column(db.Integer, default=1)
    escrow_released = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default="pending")  # pending / confirmed / completed / cancelled
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_date = db.Column(db.DateTime, nullable=True)
    stripe_session_id = db.Column(db.String(255), nullable=True)  # Legacy — kept for old records

    # ── Phase 7 additions ────────────────────────────────────────────────────
    # Flutterwave unique tx reference (format: saf-{id}-{random})
    tx_ref = db.Column(db.String(100), nullable=True)
    # Flutterwave transaction ID — required to call the refund API
    tx_id = db.Column(db.String(100), nullable=True)
    # Currency at time of payment: "USD" or "TZS"
    currency = db.Column(db.String(10), nullable=True, default='USD')
    # Amount in TZS at time of booking (NULL if paid in USD)
    tzs_amount = db.Column(db.Float, nullable=True)
    # Payment method: "card" or "mobile_money"
    payment_method = db.Column(db.String(30), nullable=True, default='card')
    # Refund lifecycle: None → "requested" → "processing" → "processed" | "rejected"
    refund_status = db.Column(db.String(20), nullable=True)
    # Flutterwave refund ID returned by POST /v3/transactions/<tx_id>/refund
    flw_refund_id = db.Column(db.String(100), nullable=True)
    # ─────────────────────────────────────────────────────────────────────────

    # Property aliases for Phase 7 route/template compatibility
    @property
    def amount(self):
        """Alias for amount_usd — used by Phase 7 routes and templates."""
        return self.amount_usd

    @property
    def tourist_id(self):
        """Alias for user_id — used by Phase 7 routes."""
        return self.user_id

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "item_name": self.item_name,
            "amount_usd": self.amount_usd,
            "currency": self.currency or 'USD',
            "tzs_amount": self.tzs_amount,
            "payment_method": self.payment_method or 'card',
            "tx_ref": self.tx_ref,
            "tx_id": self.tx_id,
            "refund_status": self.refund_status,
            "status": self.status,
            "num_guests": self.num_guests,
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
        }


class Review(db.Model):
    """
    Phase 8 verified review — linked to a specific confirmed booking.
    One review per booking (unique constraint on booking_id).

    FIX: Only ONE FK to User (tourist_id). The previous version had two FKs
    to user.id which caused SQLAlchemy AmbiguousForeignKeysError.
    user_id is now a plain property alias for tourist_id (backward compat).
    """
    __tablename__ = "review"

    id         = db.Column(db.Integer, primary_key=True)
    tourist_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    booking_id = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=True, unique=True)
    item_type  = db.Column(db.String(50), nullable=False)   # guide | accommodation | experience
    item_id    = db.Column(db.String(50), nullable=False)
    rating     = db.Column(db.Integer, nullable=False)      # 1–5
    comment    = db.Column(db.Text, nullable=True)
    is_visible = db.Column(db.Boolean, default=True)        # admin can hide abusive reviews
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tourist    = db.relationship("User", backref="reviews", lazy=True)
    booking    = db.relationship("Booking", backref="review", lazy=True, uselist=False)

    @property
    def user_id(self):
        """Backward-compat alias for tourist_id."""
        return self.tourist_id

    def to_dict(self):
        tourist_name = "Anonymous"
        try:
            tourist_name = self.tourist.username if self.tourist else "Anonymous"
        except Exception:
            pass
        return {
            "id":           self.id,
            "tourist_id":   self.tourist_id,
            "user_id":      self.tourist_id,
            "tourist_name": tourist_name,
            "booking_id":   self.booking_id,
            "item_type":    self.item_type,
            "item_id":      self.item_id,
            "rating":       self.rating,
            "comment":      self.comment,
            "created_at":   self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# PHASE 8 MODELS
# =============================================================================

# DAY 2 ───────────────────────────────────────────────────────────────────────

class Availability(db.Model):
    """Dates on which a guide is UNAVAILABLE. One record = one blocked date."""
    __tablename__ = "availability"
    __table_args__ = (
        db.UniqueConstraint("guide_id", "date", name="uq_guide_date"),
    )

    id         = db.Column(db.Integer, primary_key=True)
    guide_id   = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date       = db.Column(db.Date, nullable=False)
    reason     = db.Column(db.String(200), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    guide      = db.relationship("User", backref="blocked_dates", lazy=True)

    def to_dict(self):
        return {"id": self.id, "date": str(self.date), "reason": self.reason}


class Notification(db.Model):
    """In-app notification for any user. Also dispatched via FCM where configured."""
    __tablename__ = "notification"

    TYPES = {
        "booking_confirmed":  "Booking Confirmed",
        "booking_cancelled":  "Booking Cancelled",
        "review_received":    "New Review",
        "payment_released":   "Payment Released",
        "kyc_approved":       "Identity Verified",
        "kyc_rejected":       "Verification Failed",
        "escrow_settled":     "Tour Payment Settled",
        "general":            "Notification",
    }

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    notif_type = db.Column(db.String(50), nullable=False, default="general")
    title      = db.Column(db.String(200), nullable=False)
    message    = db.Column(db.Text, nullable=False)
    is_read    = db.Column(db.Boolean, default=False)
    link       = db.Column(db.String(400), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user       = db.relationship("User", backref="notifications", lazy=True)

    def to_dict(self):
        return {
            "id":         self.id,
            "type":       self.notif_type,
            "title":      self.title,
            "message":    self.message,
            "is_read":    self.is_read,
            "link":       self.link,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class UserFCMToken(db.Model):
    """Device push notification token (Firebase Cloud Messaging)."""
    __tablename__ = "user_fcm_token"

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    token      = db.Column(db.String(300), nullable=False)
    platform   = db.Column(db.String(20), nullable=True, default="web")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# DAY 3 ───────────────────────────────────────────────────────────────────────

class EscrowTransaction(db.Model):
    """
    Tracks the escrow lifecycle for a single booking.
    holding → settled | refunded
    """
    __tablename__ = "escrow_transaction"

    id              = db.Column(db.Integer, primary_key=True)
    booking_id      = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False, unique=True)
    total_amount    = db.Column(db.Float, nullable=False)
    deposit_pct     = db.Column(db.Float, default=20.0)
    deposit_amount  = db.Column(db.Float, nullable=False)
    escrow_amount   = db.Column(db.Float, nullable=False)
    deposit_flw_id  = db.Column(db.String(100), nullable=True)
    settle_flw_id   = db.Column(db.String(100), nullable=True)
    status          = db.Column(db.String(20), default="holding")
    settled_at      = db.Column(db.DateTime, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    booking         = db.relationship("Booking", backref="escrow", lazy=True, uselist=False)

    def to_dict(self):
        return {
            "id":             self.id,
            "booking_id":     self.booking_id,
            "total_amount":   self.total_amount,
            "deposit_pct":    self.deposit_pct,
            "deposit_amount": self.deposit_amount,
            "escrow_amount":  self.escrow_amount,
            "status":         self.status,
            "settled_at":     self.settled_at.isoformat() if self.settled_at else None,
        }


class PricingRule(db.Model):
    """Dynamic pricing configuration for a guide/stay/experience listing."""
    __tablename__ = "pricing_rule"

    id                     = db.Column(db.Integer, primary_key=True)
    operator_id            = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    item_type              = db.Column(db.String(20), nullable=False)
    item_id                = db.Column(db.Integer, nullable=False)
    low_load_threshold     = db.Column(db.Float, default=25.0)
    low_load_multiplier    = db.Column(db.Float, default=0.85)
    high_load_threshold    = db.Column(db.Float, default=75.0)
    high_load_multiplier   = db.Column(db.Float, default=1.20)
    last_minute_hours      = db.Column(db.Integer, default=48)
    last_minute_multiplier = db.Column(db.Float, default=0.90)
    max_capacity           = db.Column(db.Integer, default=10)
    is_active              = db.Column(db.Boolean, default=True)
    created_at             = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at             = db.Column(db.DateTime, onupdate=datetime.utcnow)

    operator               = db.relationship("User", backref="pricing_rules", lazy=True)

    def to_dict(self):
        return {
            "id":                     self.id,
            "item_type":              self.item_type,
            "item_id":                self.item_id,
            "low_load_threshold":     self.low_load_threshold,
            "low_load_multiplier":    self.low_load_multiplier,
            "high_load_threshold":    self.high_load_threshold,
            "high_load_multiplier":   self.high_load_multiplier,
            "last_minute_hours":      self.last_minute_hours,
            "last_minute_multiplier": self.last_minute_multiplier,
            "max_capacity":           self.max_capacity,
            "is_active":              self.is_active,
        }


class CommissionLedger(db.Model):
    """Immutable log of every commission extraction. Append-only audit trail."""
    __tablename__ = "commission_ledger"

    id               = db.Column(db.Integer, primary_key=True)
    booking_id       = db.Column(db.Integer, db.ForeignKey("booking.id"), nullable=False)
    escrow_id        = db.Column(db.Integer, db.ForeignKey("escrow_transaction.id"), nullable=True)
    gross_amount     = db.Column(db.Float, nullable=False)
    commission_rate  = db.Column(db.Float, nullable=False)
    commission_amount= db.Column(db.Float, nullable=False)
    net_to_operator  = db.Column(db.Float, nullable=False)
    extracted_at     = db.Column(db.DateTime, default=datetime.utcnow)

    booking          = db.relationship("Booking", backref="commission_records", lazy=True)

    def to_dict(self):
        return {
            "id":                self.id,
            "booking_id":        self.booking_id,
            "gross_amount":      self.gross_amount,
            "commission_rate":   self.commission_rate,
            "commission_amount": self.commission_amount,
            "net_to_operator":   self.net_to_operator,
            "extracted_at":      self.extracted_at.isoformat() if self.extracted_at else None,
        }


# DAY 4 ───────────────────────────────────────────────────────────────────────

class KYCRecord(db.Model):
    """Identity verification record for a guide. One per guide."""
    __tablename__ = "kyc_record"

    id               = db.Column(db.Integer, primary_key=True)
    guide_id         = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    smile_job_id     = db.Column(db.String(100), nullable=True)
    id_type          = db.Column(db.String(50),  nullable=True)
    id_number        = db.Column(db.String(100), nullable=True)
    country          = db.Column(db.String(10),  nullable=True, default="TZ")
    status           = db.Column(db.String(20), default="pending")
    confidence_value = db.Column(db.Float, nullable=True)
    risk_score       = db.Column(db.Float, nullable=True)
    admin_notes      = db.Column(db.Text, nullable=True)
    submitted_at     = db.Column(db.DateTime, default=datetime.utcnow)
    reviewed_at      = db.Column(db.DateTime, nullable=True)

    guide            = db.relationship("User", backref="kyc_record", lazy=True, uselist=False)

    def to_dict(self):
        return {
            "id":               self.id,
            "guide_id":         self.guide_id,
            "id_type":          self.id_type,
            "country":          self.country,
            "status":           self.status,
            "confidence_value": self.confidence_value,
            "risk_score":       self.risk_score,
            "admin_notes":      self.admin_notes,
            "submitted_at":     self.submitted_at.isoformat() if self.submitted_at else None,
            "reviewed_at":      self.reviewed_at.isoformat() if self.reviewed_at else None,
        }


class GuideVideo(db.Model):
    """Guide's 60-second video intro, stored on Cloudinary. One per guide."""
    __tablename__ = "guide_video"

    id                   = db.Column(db.Integer, primary_key=True)
    guide_id             = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False, unique=True)
    cloudinary_public_id = db.Column(db.String(300), nullable=False)
    cloudinary_url       = db.Column(db.String(500), nullable=False)
    cloudinary_thumbnail = db.Column(db.String(500), nullable=True)
    duration_seconds     = db.Column(db.Integer, nullable=True)
    status               = db.Column(db.String(20), default="pending")
    rejection_reason     = db.Column(db.String(300), nullable=True)
    uploaded_at          = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at          = db.Column(db.DateTime, nullable=True)

    guide                = db.relationship("User", backref="video_intro", lazy=True, uselist=False)

    def to_dict(self):
        return {
            "id":                    self.id,
            "guide_id":              self.guide_id,
            "cloudinary_url":        self.cloudinary_url,
            "cloudinary_thumbnail":  self.cloudinary_thumbnail,
            "duration_seconds":      self.duration_seconds,
            "status":                self.status,
            "uploaded_at":           self.uploaded_at.isoformat() if self.uploaded_at else None,
        }
