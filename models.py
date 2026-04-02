from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), default="tourist") # "tourist", "guide", "admin"
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

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
    item_type = db.Column(db.String(50), nullable=False) # 'accommodation', 'experience', 'guide'
    item_id = db.Column(db.String(50), nullable=False)
    amount_usd = db.Column(db.Float, nullable=False)
    num_guests = db.Column(db.Integer, default=1)
    escrow_released = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default="pending") # "pending", "confirmed", "completed", "cancelled"
    booking_date = db.Column(db.DateTime, default=datetime.utcnow)
    scheduled_date = db.Column(db.DateTime)
    stripe_session_id = db.Column(db.String(255))

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "amount_usd": self.amount_usd,
            "status": self.status,
            "booking_date": self.booking_date.isoformat() if self.booking_date else None,
            "scheduled_date": self.scheduled_date.isoformat() if self.scheduled_date else None,
            "stripe_session_id": self.stripe_session_id
        }


class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    item_type = db.Column(db.String(50), nullable=False) # 'accommodation', 'experience', 'guide'
    item_id = db.Column(db.String(50), nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1-5
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'item_type', 'item_id', name='unique_user_review'),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item_type": self.item_type,
            "item_id": self.item_id,
            "rating": self.rating,
            "comment": self.comment,
            "created_at": self.created_at.isoformat() if self.created_at else None
        }
