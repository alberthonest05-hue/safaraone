"""
SafaraOne — Notification Service — FINAL (circular-import-free)
================================================================
REPLACES: services/notification_service.py

WHAT CHANGED FROM PREVIOUS VERSION:
  No app module imports. Uses extensions.py for db.
  db imported from extensions.py — no circular dependency possible.
  Zero circular import risk.
"""

import os
import logging

# ── Clean import — no app dependency ──────────────────────────────────────
from extensions import db
from models import Notification

logger = logging.getLogger(__name__)

FIREBASE_ENABLED = bool(os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON"))
_fcm_app = None


def _get_fcm():
    global _fcm_app
    if _fcm_app is not None:
        return _fcm_app
    if not FIREBASE_ENABLED:
        return None
    try:
        import firebase_admin
        from firebase_admin import credentials
        import json
        if not firebase_admin._apps:
            sa_json = os.environ.get("FIREBASE_SERVICE_ACCOUNT_JSON", "{}")
            cred = credentials.Certificate(json.loads(sa_json))
            _fcm_app = firebase_admin.initialize_app(cred)
        else:
            _fcm_app = firebase_admin.get_app()
        return _fcm_app
    except Exception as e:
        logger.error(f"[FCM] Firebase init failed: {e}")
        return None


def _dispatch_fcm(user_id: int, title: str, message: str, link: str = None):
    """Fire-and-forget FCM push. Never raises."""
    app_obj = _get_fcm()
    if not app_obj:
        return
    try:
        from firebase_admin import messaging
        try:
            from models import UserFCMToken
            tokens = [t.token for t in UserFCMToken.query.filter_by(user_id=user_id).all()]
        except Exception:
            tokens = []
        if not tokens:
            return
        msg = messaging.MulticastMessage(
            tokens=tokens,
            notification=messaging.Notification(title=title, body=message),
            data={"link": link or "/"} if link else {},
            android=messaging.AndroidConfig(priority="high"),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(aps=messaging.Aps(sound="default"))
            ),
        )
        response = messaging.send_each_for_multicast(msg)
        logger.info(f"[FCM] user={user_id} ok={response.success_count} fail={response.failure_count}")
    except Exception as e:
        logger.error(f"[FCM] Dispatch error user={user_id}: {e}")


def notify(user_id: int, notif_type: str, title: str, message: str, link: str = None) -> bool:
    """
    Create an in-app Notification record and optionally fire an FCM push.
    Safe to call from any route or service — never raises.

    Returns:
        True if DB record was created, False on error.
    """
    try:
        notif = Notification(
            user_id=user_id,
            notif_type=notif_type,
            title=title,
            message=message,
            link=link,
        )
        db.session.add(notif)
        db.session.commit()
        logger.info(f"[NOTIFY] user={user_id} type={notif_type}: {title}")
        _dispatch_fcm(user_id, title, message, link)
        return True
    except Exception as e:
        logger.error(f"[NOTIFY] Failed for user={user_id}: {e}")
        return False


# ── Convenience helpers ───────────────────────────────────────────────────────

def notify_booking_confirmed(booking, guide_user=None):
    notify(
        user_id=booking.user_id,
        notif_type="booking_confirmed",
        title="Booking Confirmed! ✅",
        message=f"Your booking for {booking.item_name or 'your trip'} is confirmed.",
        link="/my-trips",
    )
    if guide_user:
        notify(
            user_id=guide_user.id,
            notif_type="booking_confirmed",
            title="New Booking Received 🎉",
            message=f"A tourist booked you for {booking.scheduled_date or 'an upcoming date'}.",
            link="/dashboard/bookings",
        )


def notify_review_received(review, guide_user):
    stars = "⭐" * review.rating
    notify(
        user_id=guide_user.id,
        notif_type="review_received",
        title=f"New Review {stars}",
        message=f"A tourist left you a {review.rating}-star review.",
        link="/dashboard",
    )


def notify_escrow_settled(booking, guide_user, net_amount: float, currency: str = "USD"):
    notify(
        user_id=guide_user.id,
        notif_type="escrow_settled",
        title="Payment Released 💰",
        message=f"{currency} {net_amount:.2f} sent to your account for booking #{booking.id}.",
        link="/dashboard",
    )


def notify_kyc_result(guide_user, approved: bool, reason: str = None):
    if approved:
        notify(
            user_id=guide_user.id,
            notif_type="kyc_approved",
            title="Identity Verified ✅",
            message="Your ID has been verified. Your profile is now visible to tourists.",
            link="/dashboard",
        )
    else:
        notify(
            user_id=guide_user.id,
            notif_type="kyc_rejected",
            title="Verification Failed ❌",
            message=f"Verification not approved. Reason: {reason or 'Please contact support.'}",
            link="/dashboard/kyc",
        )
