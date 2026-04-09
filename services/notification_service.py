"""
SafaraOne — Notification Service (Phase 8, Day 2, Feature #80)
==============================================================
Creates in-app notifications (stored in DB) and dispatches
Firebase Cloud Messaging (FCM) push notifications.

All functions are fire-and-forget — they never raise exceptions
that would break the calling route. Failures are logged only.

Usage:
    from services.notification_service import notify

    notify(
        user_id=booking.tourist_id,
        notif_type="booking_confirmed",
        title="Booking Confirmed! ✅",
        message=f"Your booking for {item_name} is confirmed.",
        link="/my-trips",
    )
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

FIREBASE_ENABLED = bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"))

# Lazy-load Firebase Admin SDK only if configured
_fcm_app = None

def _get_fcm():
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app
    if not FIREBASE_ENABLED:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials, messaging
        if not firebase_admin._apps:
            import json
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "{}")
            cred = credentials.Certificate(json.loads(sa_json))
            _fcm_app = firebase_admin.initialize_app(cred)
        else:
            _fcm_app = firebase_admin.get_app()
        return _fcm_app
    except Exception as e:
        logger.error(f"[FCM] Firebase init failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
# FCM Token store helper
# Expects a UserFCMToken model:
#   class UserFCMToken(db.Model):
#       user_id   = db.Column(db.Integer, db.ForeignKey('user.id'))
#       token     = db.Column(db.String(300))
#       platform  = db.Column(db.String(20))  # "web" | "android" | "ios"
# If you don't have this model yet, FCM dispatch is safely skipped.
# ─────────────────────────────────────────────────────────────────────────────

def _dispatch_fcm(user_id: int, title: str, message: str, link: str = None):
    """Send FCM push to all registered tokens for a user. Silent on failure."""
    app = _get_fcm()
    if not app:
        return

    try:
        from firebase_admin import messaging
        # Import here to avoid circular imports
        from extensions import db
        # Try to get tokens — gracefully skip if model doesn't exist yet
        try:
            from models import UserFCMToken
            tokens = [t.token for t in UserFCMToken.query.filter_by(user_id=user_id).all()]
        except Exception:
            tokens = []

        if not tokens:
            return

        data_payload = {"link": link or "/"} if link else {}

        message_obj = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=message),
            data=data_payload,
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(sound="default")
                )
            ),
        )
        response = messaging.send_each_for_multicast(message_obj)
        logger.info(f"[FCM] Sent to user {user_id}: {response.success_count} ok, {response.failure_count} failed")

    except Exception as e:
        logger.error(f"[FCM] Dispatch error for user {user_id}: {e}")


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def notify(
    user_id: int,
    notif_type: str,
    title: str,
    message: str,
    link: str = None,
    db_session=None,
) -> bool:
    """
    Create an in-app notification and optionally dispatch a push via FCM.

    Args:
        user_id    : ID of the user to notify
        notif_type : One of Notification.TYPES keys (e.g. "booking_confirmed")
        title      : Short notification title (shown in the bell dropdown)
        message    : Full notification message
        link       : Optional URL to link to (e.g. "/my-trips")
        db_session : Optionally pass the db session (defaults to importing from app)

    Returns:
        True if the DB record was created successfully.
    """
    try:
        if db_session is None:
            from extensions import db as db_session_default
            db_session = db_session_default
        from models import Notification

        notif = Notification(
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            message=message,
            link=link,
        )
        db_session.session.add(notif)
        db_session.session.commit()
        logger.info(f"[NOTIFY] Created notification for user {user_id}: {title}")

        # Best-effort FCM push
        _dispatch_fcm(user_id, title, message, link)
        return True

    except Exception as e:
        logger.error(f"[NOTIFY] Failed to create notification for user {user_id}: {e}")
        return False


def notify_booking_confirmed(booking, guide_user=None):
    """Helper — fires all notifications when a booking is confirmed."""
    from extensions import db
    # Notify tourist
    notify(
        user_id=booking.tourist_id,
        notif_type="booking_confirmed",
        title="Booking Confirmed! ✅",
        message=f"Your booking for {booking.item_name or 'your trip'} is confirmed.",
        link="/my-trips",
        db_session=db,
    )
    # Notify guide/host if applicable
    if guide_user:
        notify(
            user_id=guide_user.id,
            notif_type="booking_confirmed",
            title="New Booking Received 🎉",
            message=f"A tourist has booked you for {booking.scheduled_date or 'an upcoming date'}.",
            link="/dashboard/bookings",
            db_session=db,
        )


def notify_review_received(review, guide_user):
    """Helper — fires notification to guide when they receive a new review."""
    from extensions import db
    stars = "⭐" * review.rating
    notify(
        user_id=guide_user.id,
        notif_type="review_received",
        title=f"New Review {stars}",
        message=f"A tourist left you a {review.rating}-star review.",
        link="/dashboard",
        db_session=db,
    )


def notify_escrow_settled(booking, guide_user, net_amount: float, currency: str = "USD"):
    """Helper — fires notification to guide when escrow is released."""
    from extensions import db
    notify(
        user_id=guide_user.id,
        notif_type="escrow_settled",
        title="Payment Released 💰",
        message=f"{currency} {net_amount:.2f} has been sent to your account for booking #{booking.id}.",
        link="/dashboard",
        db_session=db,
    )


def notify_kyc_result(guide_user, approved: bool, reason: str = None):
    """Helper — fires notification to guide with KYC result."""
    from extensions import db
    if approved:
        notify(
            user_id=guide_user.id,
            notif_type="kyc_approved",
            title="Identity Verified ✅",
            message="Your ID has been verified. Your profile is now visible to tourists.",
            link="/dashboard",
            db_session=db,
        )
    else:
        msg = f"Your identity verification was not approved. Reason: {reason or 'Please contact support.'}"
        notify(
            user_id=guide_user.id,
            notif_type="kyc_rejected",
            title="Verification Failed ❌",
            message=msg,
            link="/dashboard/kyc",
            db_session=db,
        )
