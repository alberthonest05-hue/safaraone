import sys
from app import app, db
from extensions import jwt
from models import User, Guide, Notification, Availability, Booking, Review
from services.notification_service import notify_booking_confirmed
from flask_jwt_extended import create_access_token
from datetime import datetime, timedelta

def run_tests():
    with app.app_context():
        client = app.test_client()

        print("--- Setting up test data ---")
        # 1. Create a Tourist
        tourist = User.query.filter_by(email="tourist@test.com").first()
        if not tourist:
            tourist = User(username="tourist_tester", email="tourist@test.com", role="tourist")
            tourist.set_password("password123")
            db.session.add(tourist)
        
        # 2. Create a Guide
        guide_user = User.query.filter_by(email="guide@test.com").first()
        if not guide_user:
            guide_user = User(username="guide_tester", email="guide@test.com", role="guide")
            guide_user.set_password("password123")
            db.session.add(guide_user)
            db.session.flush()

            guide = getattr(Guide, "query", None)
            if guide: # if Guide exists as model
                g = Guide(id="test_guide", user_id=guide_user.id, name="Test Guide", destination_id="zanzibar", price_per_day_usd=100)
                db.session.add(g)

        # 3. Create a Booking
        db.session.flush()
        booking = Booking.query.filter_by(user_id=tourist.id, status="confirmed").first()
        if not booking:
            booking = Booking(
                user_id=tourist.id, 
                item_type="guide", 
                item_id=str(guide_user.id),
                status="confirmed",
                amount_usd=100.0,
                currency="USD",
                scheduled_date=datetime.utcnow() + timedelta(days=2)
            )
            db.session.add(booking)
        
        db.session.commit()
        print(f"[OK] Test Tourist ID: {tourist.id}, Test Guide ID: {guide_user.id}, Booking ID: {booking.id}")

        # --- Test 1: Notifications ---
        print("\n--- Test 1: Notification Center ---")
        notify_booking_confirmed(booking, guide_user)
        
        # Tourist login token
        tourist_token = create_access_token(identity=str(tourist.id))
        guide_token = create_access_token(identity=str(guide_user.id))

        res = client.get('/api/notifications', headers={'Authorization': f'Bearer {tourist_token}'})
        notifs = res.get_json()
        print(f"Tourist Notifications: {notifs['unread_count']} unread.")
        assert notifs['unread_count'] >= 1, "Failed to get unread notification for tourist."

        res = client.get('/api/notifications', headers={'Authorization': f'Bearer {guide_token}'})
        notifs = res.get_json()
        print(f"Guide Notifications: {notifs['unread_count']} unread.")
        assert notifs['unread_count'] >= 1, "Failed to get unread notification for guide."
        print("[PASS] Notification Center.")

        # --- Test 2: Availability Calendar ---
        print("\n--- Test 2: Availability Calendar ---")
        date_str = (datetime.utcnow() + timedelta(days=5)).strftime("%Y-%m-%d")
        payload = {"date": date_str, "reason": "Test block"}
        res = client.post('/api/availability', json=payload, headers={'Authorization': f'Bearer {guide_token}'})
        data = res.get_json()
        print(f"Block Date response: {data}")
        assert data['status'] == 'success', "Failed to block date."

        avail_id = data.get('id')
        if avail_id:
            res = client.delete(f'/api/availability/{avail_id}', headers={'Authorization': f'Bearer {guide_token}'})
            data = res.get_json()
            print(f"Unblock Date response: {data}")
            assert data['status'] == 'success', "Failed to unblock date."
        print("[PASS] Availability Calendar.")

        # --- Test 3: Rating & Review 
        print("\n--- Test 3: Submit a Review ---")
        res = client.post('/api/reviews', json={
            "booking_id": booking.id,
            "rating": 5,
            "comment": "Amazing experience!"
        }, headers={'Authorization': f'Bearer {tourist_token}'})
        data = res.get_json()
        print(f"Submit Review response: {data}")
        if data['status'] == 'error' and 'already reviewed' in data['message']:
            print("[WARN] Already reviewed, skipping duplicate test.")
        else:
            assert data['status'] == 'success', f"Failed to submit review: {data['message']}"
        print("[PASS] Rating & Review.")

        # --- Test 4: Escrow Settlement ---
        print("\n--- Test 4: Escrow Settlement ---")
        from models import EscrowTransaction
        from services.escrow_service import initiate_escrow
        
        # Initiate escrow
        guide_sub_account_id = None # Simulate a guide without Flutterwave sub-account
        escrow = initiate_escrow(booking, guide_sub_account_id)
        print(f"Escrow Initiated: ID {escrow.id}, Status: {escrow.status}, Deposit: {escrow.deposit_amount}")
        assert escrow.status == "holding", "Escrow did not initialize to 'holding' status."
        
        # Tourist triggers settlement
        res = client.post(f'/api/escrow/settle/{booking.id}', headers={'Authorization': f'Bearer {tourist_token}'})
        data = res.get_json()
        print(f"Settle Escrow response: {data}")
        
        if data['status'] == 'error' and 'already settled' in data['message']:
            print("[WARN] Escrow already settled, skipping.")
        else:
            assert data['status'] == 'success', f"Failed to settle escrow: {data['message']}"
            assert getattr(escrow, 'status', None) == "settled" or data.get('settlement'), "Escrow status didn't transition to settled."
            
        print("[PASS] Escrow Settlement.")

        # --- Test 5: KYC and Booking Control ---
        print("\n--- Test 5: KYC and Booking Control ---")
        
        # 1. Update Booking Type
        res = client.post('/api/guide/booking-type', json={"booking_type": "instant"}, headers={'Authorization': f'Bearer {guide_token}'})
        data = res.get_json()
        print(f"Set Booking Type (instant): {data}")
        assert data['booking_type'] == 'instant', "Failed to set booking type to instant."
        
        # 2. Submit KYC
        import io
        fake_image = (io.BytesIO(b"fake image data"), "test.jpg")
        res = client.post('/api/kyc/submit', data={
            "id_type": "NATIONAL_ID",
            "id_number": "123456789",
            "country": "TZ",
            "selfie_image": fake_image,
            "id_image": fake_image
        }, content_type='multipart/form-data', headers={'Authorization': f'Bearer {guide_token}'})
        data = res.get_json()
        print(f"Submit KYC: {data}")
        assert data['status'] == 'success', f"Failed to submit KYC: {data.get('message')}"
        
        # 3. Approve KYC (Admin)
        # Create an admin user
        admin = User.query.filter_by(role="admin").first()
        if not admin:
            admin = User(username="admin_tester", email="admin@test.com", role="admin", is_admin=True)
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
        
        admin_token = create_access_token(identity=str(admin.id))
        
        res = client.post(f'/api/admin/kyc/{guide_user.id}/approve', json={"notes": "Test approval"}, headers={'Authorization': f'Bearer {admin_token}'})
        data = res.get_json()
        print(f"Approve KYC Admin: {data}")
        assert data['status'] == 'success', f"Failed to approve KYC: {data.get('message')}"
        
        updated_guide = User.query.get(guide_user.id)
        assert updated_guide.is_verified == True, "Guide is_verified flag not set after approval."
        
        print("[PASS] KYC and Booking Control.")

if __name__ == "__main__":
    run_tests()
