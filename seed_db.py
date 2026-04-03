import os
from app import app
# We added 'User' to the list of things to import here!
from models import db, Destination, Accommodation, Experience, Guide, Booking, Review, User
from data.mock_data import DESTINATIONS, ACCOMMODATIONS, EXPERIENCES, GUIDES

def seed():
    with app.app_context():
        # Create all tables safely (ignores if they exist)
        db.create_all()

        # THE FIX: Safety check - only seed if the database is empty!
        if User.query.first():
            print("Database already populated. Skipping seed.")
            return

        try:
            print("Seeding Destinations...")
            for d_data in DESTINATIONS:
                dest = Destination(
                    id=d_data['id'],
                    name=d_data['name'],
                    country=d_data['country'],
                    region=d_data['region'],
                    tagline=d_data['tagline'],
                    description=d_data['description'],
                    image_url=d_data['image_url'],
                    latitude=d_data['latitude'],
                    longitude=d_data['longitude'],
                    average_daily_budget_usd=d_data['average_daily_budget_usd'],
                    best_months=d_data['best_months'],
                    language=d_data['language'],
                    currency=d_data['currency'],
                    gallery=d_data['gallery'],
                    highlights=d_data['highlights'],
                    stats=d_data.get('stats', {})
                )
                db.session.add(dest)

            print("Seeding Accommodations...")
            for a_data in ACCOMMODATIONS:
                acc = Accommodation(
                    id=a_data['id'],
                    destination_id=a_data['destination_id'],
                    name=a_data['name'],
                    type=a_data['type'],
                    tier=a_data['tier'],
                    price_per_night_usd=a_data['price_per_night_usd'],
                    rating=a_data['rating'],
                    review_count=a_data['review_count'],
                    amenities=a_data['amenities'],
                    description=a_data['description'],
                    image_url=a_data['image_url'],
                    latitude=a_data['latitude'],
                    longitude=a_data['longitude'],
                    booking_url=a_data['booking_url'],
                )
                db.session.add(acc)

            print("Seeding Experiences...")
            for e_data in EXPERIENCES:
                exp = Experience(
                    id=e_data['id'],
                    destination_id=e_data['destination_id'],
                    title=e_data['title'],
                    category=e_data['category'],
                    tier=e_data['tier'],
                    price_usd=e_data['price_usd'],
                    duration_hours=e_data['duration_hours'],
                    rating=e_data['rating'],
                    review_count=e_data['review_count'],
                    max_participants=e_data['max_participants'],
                    description=e_data['description'],
                    image_url=e_data['image_url'],
                    tags=e_data['tags'],
                    is_indoor=e_data['is_indoor'],
                    booking_url=e_data['booking_url'],
                )
                db.session.add(exp)

            print("Seeding Guides...")
            for g_data in GUIDES:
                guide = Guide(
                    id=g_data['id'],
                    destination_id=g_data['destination_id'],
                    name=g_data['name'],
                    avatar_url=g_data['avatar_url'],
                    title=g_data['title'],
                    languages=g_data['languages'],
                    specializations=g_data['specializations'],
                    price_per_day_usd=g_data['price_per_day_usd'],
                    rating=g_data['rating'],
                    total_reviews=g_data['total_reviews'],
                    experience_years=g_data['experience_years'],
                    bio=g_data['bio'],
                    certifications=g_data['certifications'],
                    availability=g_data['availability'],
                    is_verified=g_data['is_verified'],
                )
                db.session.add(guide)

            db.session.commit()
            print("Database seeded successfully!")
        except Exception as e:
            db.session.rollback()
            print("Seeding skipped or failed: " + str(e))

if __name__ == "__main__":
    seed()