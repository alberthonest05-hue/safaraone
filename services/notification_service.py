"""
SafaraOne — Notification Service (Phase 8)
==========================================
Handles in-app notifications + optional FCM push notifications.
Falls back gracefully when Firebase is not configured.
"""

import os
import json
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def _get_firebase_app():
    """Lazy-initialise Firebase Admin SDK. Returns None if not configured."""
    try:
        import firebase_admin
        from firebase_admin import credentials
        if not firebase_admin._apps:
            creds_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "")
            if not creds_json:
                return None
            cred = credentials.Certificate(json.loads(creds_json))
            firebase_admin.initialize_app(cred)
        return firebase_admin.get_app()
    except Exception as e:
        logger.warning(f"[FCM] Firebase init failed (stub mode): {e}")
        return None


def _send_fcm_push(user_id: int, title: str, body: str, link: str = None):
    """
    Send a Firebase Cloud Messaging push notification to all registered tokens
    for the given user. Silent failure if Firebase is not configured.
    """
    try:
        from firebase_admin import messaging
        app = _get_firebase_app()
        if not app:
            return  # FCM not configured — skip silently

        # Import here to avoid circular imports
        from app import app as flask_app, db
        from models import UserFCMToken
        with flask_app.app_context():
            tokens = UserFCMToken.query.filter_by(user_id=user_id).all()
            for t in tokens:
                try:
                    message = messaging.Message(
                        notification=messaging.Notification(title=title, body=body),
                        data={"link": link or ""},
                        token=t.token,
                    )
                    messaging.send(message)
                except Exception as e:
                    logger.warning(f"[FCM] Push failed for token {t.token[:20]}…: {e}")
    except Exception as e:
        logger.warning(f"[FCM] Push notification failed: {e}")


def notify(user_id: int, notif_type: str, title: str, message: str, link: str = None):
    """
    Create an in-app Notification record and optionally fire FCM push.

    Usage:
        notify(user_id=3, notif_type="booking_confirmed",
               title="Booking Confirmed", message="Your tour is booked!")
    """
    try:
        from app import db
        from models import Notification

        n = Notification(
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            message=message,
            link=link,
        )
        db.session.add(n)
        db.session.commit()

        # Best-effort FCM push
        _send_fcm_push(user_id, title, message, link)

    except Exception as e:
        logger.error(f"[NOTIFY] Failed to save notification for user {user_id}: {e}")


def notify_booking_confirmed(booking, guide=None):
    """
    Notify tourist that their booking is confirmed.
    Optionally notify the guide of an incoming booking.
    """
    # Notify tourist
    notify(
        user_id=booking.user_id,
        notif_type="booking_confirmed",
        title="Booking Confirmed 🎉",
        message=f"Your booking for {booking.item_name or 'your trip'} has been confirmed!",
        link=f"/my-trips",
    )

    # Notify guide (if guide booking)
    if guide:
        try:
            from datetime import date
            trip_date = booking.scheduled_date.strftime('%b %d, %Y') if booking.scheduled_date else 'a coming date'
            notify(
                user_id=guide.id if hasattr(guide, 'id') else guide.user_id,
                notif_type="booking_confirmed",
                title="New Booking Received 📅",
                message=f"You have a new confirmed booking for {trip_date}.",
                link="/dashboard/bookings",
            )
        except Exception as e:
            logger.error(f"[NOTIFY] Guide notification failed: {e}")


def notify_review_received(review, recipient):
    """
    Notify a guide/host that they have received a new review.
    `recipient` is the User object of the guide/host.
    """
    try:
        stars = "⭐" * review.rating
        notify(
            user_id=recipient.id,
            notif_type="review_received",
            title="New Review Received",
            message=f"You received a {review.rating}-star review. {stars}",
            link="/dashboard",
        )
    except Exception as e:
        logger.error(f"[NOTIFY] Review notification failed: {e}")


def notify_kyc_result(guide, approved: bool, reason: str = None):
    """Notify a guide of their KYC verification result."""
    if approved:
        notify(
            user_id=guide.id,
            notif_type="kyc_approved",
            title="Identity Verified ✅",
            message="Your identity has been verified. You are now fully discoverable on SafaraOne!",
            link="/dashboard",
        )
    else:
        notify(
            user_id=guide.id,
            notif_type="kyc_rejected",
            title="Verification Failed",
            message=f"Your identity verification was not approved. Reason: {reason or 'Please contact support.'}",
            link="/dashboard/kyc",
        )
