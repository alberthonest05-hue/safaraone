"""
SafaraOne — Escrow Service (Phase 8, Day 3, Features #47 + #48 + #53)
======================================================================
Uses extensions.py for db — zero circular import risk.

Guide lookup fix: Guide.id is a String PK in this schema (e.g. "guide-zanzibar-1").
booking.item_id is a Guide.id (string), NOT a User.id (int).
So the correct lookup is: Guide.query.get(booking.item_id) → guide.user_id → User.
"""

import os
import logging
import requests
from datetime import datetime, date

# Clean import — no app dependency
from extensions import db
from models import EscrowTransaction, CommissionLedger, PricingRule, Booking, User, Guide

logger = logging.getLogger(__name__)

FLW_BASE = "https://api.flutterwave.com/v3"


def _headers() -> dict:
    """Build fresh headers each call so FLW_SECRET_KEY changes are picked up."""
    return {
        "Authorization": f"Bearer {os.environ.get('FLW_SECRET_KEY', '')}",
        "Content-Type": "application/json",
    }


def _flw_post(endpoint: str, payload: dict) -> dict:
    resp = requests.post(f"{FLW_BASE}{endpoint}", json=payload, headers=_headers(), timeout=15)
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Initiation
# ─────────────────────────────────────────────────────────────────────────────

def initiate_escrow(booking, guide_sub_account_id: str = None) -> EscrowTransaction:
    """
    Called immediately after booking payment is confirmed.
    Creates EscrowTransaction, fires deposit to guide, locks remainder.
    """
    DEPOSIT_PCT    = float(os.environ.get("ESCROW_DEPOSIT_PCT", "20.0"))
    total_amount   = float(booking.amount_usd)
    deposit_amount = round(total_amount * (DEPOSIT_PCT / 100), 2)
    escrow_amount  = round(total_amount - deposit_amount, 2)

    # Idempotency — never create duplicate records
    existing = EscrowTransaction.query.filter_by(booking_id=booking.id).first()
    if existing:
        logger.info(f"[ESCROW] Already exists for booking #{booking.id}")
        return existing

    escrow = EscrowTransaction(
        booking_id     = booking.id,
        total_amount   = total_amount,
        deposit_pct    = DEPOSIT_PCT,
        deposit_amount = deposit_amount,
        escrow_amount  = escrow_amount,
        status         = "holding",
    )
    db.session.add(escrow)
    db.session.commit()

    logger.info(
        f"[ESCROW] Initiated booking #{booking.id}: "
        f"deposit={deposit_amount} escrow={escrow_amount} USD"
    )

    if guide_sub_account_id and getattr(booking, 'tx_id', None):
        try:
            currency = getattr(booking, 'currency', None) or "USD"
            resp = _flw_post("/transfers", {
                "account_bank":   "flutterwave",
                "account_number": guide_sub_account_id,
                "amount":         deposit_amount,
                "currency":       currency,
                "narration":      f"SafaraOne deposit – booking #{booking.id}",
                "reference":      f"dep-{booking.id}-{escrow.id}",
            })
            if resp.get("status") == "success":
                escrow.deposit_flw_id = str(resp["data"].get("id", ""))
                db.session.commit()
                logger.info(f"[ESCROW] Deposit {deposit_amount} {currency} sent, booking #{booking.id}")
            else:
                logger.warning(f"[ESCROW] Deposit transfer rejected: {resp}")
        except Exception as e:
            logger.error(f"[ESCROW] Deposit exception booking #{booking.id}: {e}")
    else:
        logger.warning(
            f"[ESCROW] Booking #{booking.id} — no sub_account_id or tx_id. "
            "Deposit flagged for manual payout."
        )

    return escrow


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Settlement
# ─────────────────────────────────────────────────────────────────────────────

def settle_escrow(escrow: EscrowTransaction, guide_sub_account_id: str = None) -> dict:
    """
    Tourist taps "Tour Completed" — deducts commission, transfers net to guide.

    GUIDE LOOKUP FIX:
    Guide.id is a String PK (e.g. "guide-zanzibar-1").
    booking.item_id holds that string. We look up Guide first, then guide.user_id.
    Claude's version did db.session.get(User, int(booking.item_id)) which is WRONG.
    """
    # Import here to avoid service-to-service circular at module level
    from services.notification_service import notify_escrow_settled

    if escrow.status != "holding":
        return {"status": "error", "message": f"Escrow is already {escrow.status}"}

    COMMISSION_RATE   = float(os.environ.get("COMMISSION_RATE", "0.10"))
    booking           = escrow.booking
    currency          = getattr(booking, 'currency', None) or "USD"
    gross_amount      = escrow.escrow_amount
    commission_amount = round(gross_amount * COMMISSION_RATE, 2)
    net_to_operator   = round(gross_amount - commission_amount, 2)

    # Commission log — created BEFORE transfer for audit integrity
    commission_log = CommissionLedger(
        booking_id        = booking.id,
        escrow_id         = escrow.id,
        gross_amount      = gross_amount,
        commission_rate   = COMMISSION_RATE,
        commission_amount = commission_amount,
        net_to_operator   = net_to_operator,
    )
    db.session.add(commission_log)

    settle_flw_id = None
    if guide_sub_account_id:
        try:
            resp = _flw_post("/transfers", {
                "account_bank":   "flutterwave",
                "account_number": guide_sub_account_id,
                "amount":         net_to_operator,
                "currency":       currency,
                "narration":      f"SafaraOne settlement – booking #{booking.id}",
                "reference":      f"settle-{booking.id}-{escrow.id}",
            })
            if resp.get("status") == "success":
                settle_flw_id = str(resp["data"].get("id", ""))
                logger.info(f"[ESCROW] Settled {net_to_operator} {currency} booking #{booking.id}")
            else:
                logger.warning(f"[ESCROW] Settlement transfer rejected: {resp}")
        except Exception as e:
            logger.error(f"[ESCROW] Settlement exception booking #{booking.id}: {e}")

    escrow.status        = "settled"
    escrow.settle_flw_id = settle_flw_id
    escrow.settled_at    = datetime.utcnow()
    db.session.commit()

    # Notify guide — Guide.id is String, NOT User.id
    try:
        if booking.item_type == "guide":
            guide_record = Guide.query.get(booking.item_id)  # Guide.id = string
            if guide_record and guide_record.user_id:
                guide_user = db.session.get(User, guide_record.user_id)
                if guide_user:
                    notify_escrow_settled(booking, guide_user, net_to_operator, currency)
    except Exception as e:
        logger.error(f"[ESCROW] Guide notification failed: {e}")

    return {
        "status":          "success",
        "gross_amount":    gross_amount,
        "commission":      commission_amount,
        "net_to_operator": net_to_operator,
        "settle_flw_id":   settle_flw_id,
        "currency":        currency,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Refund
# ─────────────────────────────────────────────────────────────────────────────

def refund_escrow(escrow: EscrowTransaction) -> dict:
    """Return escrow balance to tourist (e.g. cancellation)."""
    if escrow.status != "holding":
        return {"status": "error", "message": f"Cannot refund — escrow is {escrow.status}"}

    booking = escrow.booking
    tx_id   = getattr(booking, 'tx_id', None)

    if not tx_id:
        # No Flutterwave tx_id — just mark locally
        escrow.status = "refunded"
        db.session.commit()
        logger.info(f"[ESCROW] Escrow #{escrow.id} marked refunded (no tx_id)")
        return {"status": "success", "method": "local"}

    try:
        resp   = requests.post(
            f"{FLW_BASE}/transactions/{tx_id}/refund",
            json={"amount": escrow.escrow_amount},
            headers=_headers(),
            timeout=10,
        )
        result = resp.json()
        if result.get("status") == "success":
            escrow.status = "refunded"
            db.session.commit()
            return {"status": "success", "refund_id": result["data"].get("id")}
        return {"status": "error", "message": str(result)}
    except Exception as e:
        logger.error(f"[ESCROW] Refund exception booking #{booking.id}: {e}")
        # Fail-safe: mark locally so UI is unblocked
        escrow.status = "refunded"
        db.session.commit()
        return {"status": "success", "method": "local_fallback"}


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Pricing Engine
# ─────────────────────────────────────────────────────────────────────────────

def compute_dynamic_price(
    base_price: float,
    item_type: str,
    item_id,
    scheduled_date=None,
) -> dict:
    """Compute checkout price after applying dynamic pricing rules."""
    try:
        rule = PricingRule.query.filter_by(
            item_type=item_type, item_id=item_id, is_active=True
        ).first()

        if not rule:
            return {"final_price": base_price, "multiplier": 1.0, "rule_applied": "none"}

        confirmed_count = Booking.query.filter_by(
            item_type=item_type, item_id=str(item_id), status="confirmed"
        ).count()
        load_pct = (confirmed_count / rule.max_capacity * 100) if rule.max_capacity > 0 else 50.0

        if scheduled_date:
            scheduled_dt = (
                datetime.combine(scheduled_date, datetime.min.time())
                if isinstance(scheduled_date, date) and not isinstance(scheduled_date, datetime)
                else scheduled_date
            )
            hours_left = (scheduled_dt - datetime.utcnow()).total_seconds() / 3600
            if 0 < hours_left < rule.last_minute_hours:
                multiplier = rule.last_minute_multiplier
                return {
                    "final_price":  round(base_price * multiplier, 2),
                    "multiplier":   multiplier,
                    "rule_applied": f"last_minute ({hours_left:.0f}h left)",
                }

        if load_pct <= rule.low_load_threshold:
            multiplier, rule_applied = rule.low_load_multiplier, f"low_load ({load_pct:.0f}% capacity)"
        elif load_pct >= rule.high_load_threshold:
            multiplier, rule_applied = rule.high_load_multiplier, f"high_load ({load_pct:.0f}% capacity)"
        else:
            multiplier, rule_applied = 1.0, f"standard ({load_pct:.0f}% capacity)"

        return {
            "final_price":  round(base_price * multiplier, 2),
            "multiplier":   multiplier,
            "rule_applied": rule_applied,
        }

    except Exception as e:
        logger.error(f"[PRICING] compute_dynamic_price failed: {e}")
        return {"final_price": base_price, "multiplier": 1.0, "rule_applied": "error"}
