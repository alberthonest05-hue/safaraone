"""
SafaraOne — Escrow Service (Phase 8, Day 3, Features #47 + #48 + #53)
======================================================================
Handles the complete escrow lifecycle:
  1. initiate_escrow()  — called when a booking is confirmed
  2. settle_escrow()    — called when tourist taps "Tour Completed"
  3. refund_escrow()    — called when a booking is cancelled with escrow holding

Commission is auto-extracted during settlement (Feature #53).

All Flutterwave API calls are wrapped in try/except. If the API is down,
the escrow record is still created/updated locally and flagged for manual
processing. This prevents payment failures from breaking the user experience.

Usage:
    from services.escrow_service import initiate_escrow, settle_escrow

    # On booking confirmed:
    initiate_escrow(booking, guide_sub_account_id)

    # On tourist tour completion tap:
    settle_escrow(escrow_transaction)
"""

import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)

FLW_SECRET = os.environ.get("FLW_SECRET_KEY", "")
FLW_BASE   = "https://api.flutterwave.com/v3"
HEADERS    = {"Authorization": f"Bearer {FLW_SECRET}", "Content-Type": "application/json"}


def _flw_post(endpoint: str, payload: dict) -> dict:
    """Make a POST to Flutterwave API. Returns response dict or raises."""
    resp = requests.post(f"{FLW_BASE}{endpoint}", json=payload, headers=HEADERS, timeout=15)
    return resp.json()


def _flw_get(endpoint: str, params: dict = None) -> dict:
    """Make a GET to Flutterwave API."""
    resp = requests.get(f"{FLW_BASE}{endpoint}", params=params or {}, headers=HEADERS, timeout=10)
    return resp.json()


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Initiation
# ─────────────────────────────────────────────────────────────────────────────

def initiate_escrow(booking, guide_sub_account_id: str = None) -> "EscrowTransaction":
    """
    Called immediately after a booking payment is confirmed.

    What it does:
      1. Calculates deposit amount (DEPOSIT_PCT of total)
      2. Creates EscrowTransaction record with status='holding'
      3. Sends deposit to guide sub-account via Flutterwave transfer
      4. Remaining balance stays in platform account as escrow

    Args:
        booking               : Confirmed Booking object (must have tx_id)
        guide_sub_account_id  : Flutterwave sub-account ID for the guide
                                (if None, deposit is flagged for manual payout)

    Returns:
        EscrowTransaction object
    """
    from app import app, db
    from models import EscrowTransaction

    DEPOSIT_PCT = float(os.environ.get("ESCROW_DEPOSIT_PCT", "20.0"))

    total_amount   = float(booking.amount)
    deposit_amount = round(total_amount * (DEPOSIT_PCT / 100), 2)
    escrow_amount  = round(total_amount - deposit_amount, 2)

    # Check for existing escrow (idempotency)
    existing = EscrowTransaction.query.filter_by(booking_id=booking.id).first()
    if existing:
        logger.info(f"[ESCROW] Escrow already exists for booking #{booking.id}")
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

    # ── Attempt Flutterwave deposit transfer ──────────────────────────────
    if guide_sub_account_id and booking.tx_id:
        try:
            currency = booking.currency or "USD"
            resp = _flw_post("/transfers", {
                "account_bank":    "flutterwave",           # internal FLW transfer
                "account_number":  guide_sub_account_id,
                "amount":          deposit_amount,
                "currency":        currency,
                "narration":       f"SafaraOne deposit – booking #{booking.id}",
                "reference":       f"dep-{booking.id}-{escrow.id}",
            })

            if resp.get("status") == "success":
                escrow.deposit_flw_id = str(resp["data"].get("id", ""))
                db.session.commit()
                logger.info(f"[ESCROW] Deposit {deposit_amount} {currency} sent to guide for booking #{booking.id}")
            else:
                logger.warning(f"[ESCROW] Deposit transfer failed: {resp}")

        except Exception as e:
            logger.error(f"[ESCROW] Deposit transfer exception for booking #{booking.id}: {e}")
            # Escrow record is still created — finance team reviews deposit_flw_id=None records
    else:
        logger.warning(f"[ESCROW] No sub_account_id or tx_id for booking #{booking.id} — deposit skipped, flagged for manual payout")

    return escrow


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Settlement
# ─────────────────────────────────────────────────────────────────────────────

def settle_escrow(escrow: "EscrowTransaction", guide_sub_account_id: str = None) -> dict:
    """
    Called when tourist taps "Tour Completed".

    What it does:
      1. Calculates commission (COMMISSION_RATE × escrow_amount)
      2. Calculates net payout to guide (escrow_amount − commission)
      3. Transfers net to guide sub-account via Flutterwave
      4. Creates CommissionLedger entry
      5. Updates escrow status to 'settled'
      6. Fires notification to guide

    Args:
        escrow               : EscrowTransaction object with status='holding'
        guide_sub_account_id : Flutterwave sub-account ID for the guide

    Returns:
        dict with settlement outcome
    """
    from app import app, db
    from models import CommissionLedger
    from services.notification_service import notify_escrow_settled

    if escrow.status != "holding":
        return {"status": "error", "message": f"Escrow is already {escrow.status}"}

    COMMISSION_RATE = float(os.environ.get("COMMISSION_RATE", "0.10"))
    booking = escrow.booking
    currency = booking.currency or "USD"

    gross_amount      = escrow.escrow_amount
    commission_amount = round(gross_amount * COMMISSION_RATE, 2)
    net_to_operator   = round(gross_amount - commission_amount, 2)

    # ── Create commission log (always, before the transfer attempt) ───────
    commission_log = CommissionLedger(
        booking_id        = booking.id,
        escrow_id         = escrow.id,
        gross_amount      = gross_amount,
        commission_rate   = COMMISSION_RATE,
        commission_amount = commission_amount,
        net_to_operator   = net_to_operator,
    )
    db.session.add(commission_log)

    # ── Attempt Flutterwave payout ────────────────────────────────────────
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
                logger.info(f"[ESCROW] Settled {net_to_operator} {currency} to guide for booking #{booking.id}")
            else:
                logger.warning(f"[ESCROW] Settlement transfer failed: {resp}")

        except Exception as e:
            logger.error(f"[ESCROW] Settlement exception for booking #{booking.id}: {e}")

    # ── Update escrow record ──────────────────────────────────────────────
    escrow.status         = "settled"
    escrow.settle_flw_id  = settle_flw_id
    escrow.settled_at     = datetime.utcnow()
    db.session.commit()

    # ── Notify guide ──────────────────────────────────────────────────────
    try:
        from models import User
        guide = User.query.get(booking.item_id) if booking.item_type == "guide" else None
        if guide:
            notify_escrow_settled(booking, guide, net_to_operator, currency)
    except Exception as e:
        logger.error(f"[ESCROW] Guide notification failed: {e}")

    return {
        "status":           "success",
        "gross_amount":     gross_amount,
        "commission":       commission_amount,
        "net_to_operator":  net_to_operator,
        "settle_flw_id":    settle_flw_id,
        "currency":         currency,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Escrow Refund
# ─────────────────────────────────────────────────────────────────────────────

def refund_escrow(escrow: "EscrowTransaction") -> dict:
    """
    Returns escrow balance to the tourist (e.g. on operator no-show).
    Uses the existing refund logic from Phase 7 (booking.tx_id).
    """
    from app import db

    if escrow.status != "holding":
        return {"status": "error", "message": f"Cannot refund — escrow is {escrow.status}"}

    booking = escrow.booking
    try:
        resp = requests.post(
            f"{FLW_BASE}/transactions/{booking.tx_id}/refund",
            json={"amount": escrow.escrow_amount},
            headers=HEADERS,
            timeout=10,
        )
        result = resp.json()
        if result.get("status") == "success":
            escrow.status = "refunded"
            db.session.commit()
            return {"status": "success", "refund_id": result["data"].get("id")}
        return {"status": "error", "message": str(result)}
    except Exception as e:
        logger.error(f"[ESCROW] Refund exception for booking #{booking.id}: {e}")
        return {"status": "error", "message": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Dynamic Pricing Engine
# ─────────────────────────────────────────────────────────────────────────────

def compute_dynamic_price(base_price: float, item_type: str, item_id: int, scheduled_date=None) -> dict:
    """
    Applies dynamic pricing rules to compute the final checkout price.

    Args:
        base_price     : The operator's standard listed price
        item_type      : "guide" | "stay" | "experience"
        item_id        : Database ID of the listing
        scheduled_date : datetime.date of the trip (for last-minute check)

    Returns:
        dict with final_price, multiplier, rule_applied
    """
    from models import PricingRule, Booking
    from datetime import date, datetime

    rule = PricingRule.query.filter_by(
        item_type=item_type,
        item_id=item_id,
        is_active=True,
    ).first()

    if not rule:
        return {"final_price": base_price, "multiplier": 1.0, "rule_applied": "none"}

    # ── Calculate current load ────────────────────────────────────────────
    confirmed_count = Booking.query.filter_by(
        item_type=item_type,
        item_id=item_id,
        status="confirmed",
    ).count()

    load_pct = (confirmed_count / rule.max_capacity * 100) if rule.max_capacity > 0 else 50.0

    # ── Check last-minute window ──────────────────────────────────────────
    if scheduled_date:
        if isinstance(scheduled_date, date):
            scheduled_dt = datetime.combine(scheduled_date, datetime.min.time())
        else:
            scheduled_dt = scheduled_date
        hours_to_departure = (scheduled_dt - datetime.utcnow()).total_seconds() / 3600
        if 0 < hours_to_departure < rule.last_minute_hours:
            multiplier   = rule.last_minute_multiplier
            rule_applied = f"last_minute ({hours_to_departure:.0f}h left)"
            final_price  = round(base_price * multiplier, 2)
            return {"final_price": final_price, "multiplier": multiplier, "rule_applied": rule_applied}

    # ── Apply load-based rule ─────────────────────────────────────────────
    if load_pct <= rule.low_load_threshold:
        multiplier   = rule.low_load_multiplier
        rule_applied = f"low_load ({load_pct:.0f}% capacity)"
    elif load_pct >= rule.high_load_threshold:
        multiplier   = rule.high_load_multiplier
        rule_applied = f"high_load ({load_pct:.0f}% capacity)"
    else:
        multiplier   = 1.0
        rule_applied = f"standard ({load_pct:.0f}% capacity)"

    final_price = round(base_price * multiplier, 2)
    return {"final_price": final_price, "multiplier": multiplier, "rule_applied": rule_applied}
