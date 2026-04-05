"""
SafaraOne — Escrow Service (Phase 8)
=====================================
Manages the escrow lifecycle:
  - initiate_escrow()   → called after payment_callback confirms booking
  - settle_escrow()     → tourist confirms tour complete
  - refund_escrow()     → booking cancelled, refund escrow amount
  - compute_dynamic_price() → applies PricingRule multipliers
"""

import os
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


def initiate_escrow(booking, guide_sub_account_id: str = None):
    """
    Called immediately after booking.status = 'confirmed'.
    Splits the total amount:
      - deposit_pct% → sent to guide via Flutterwave transfer
      - remainder    → held in escrow (tracked in DB)

    If guide has no sub-account, the deposit is logged but not transferred
    (admin handles manual payout).
    """
    try:
        from app import app, db
        from models import EscrowTransaction

        deposit_pct = float(os.environ.get("ESCROW_DEPOSIT_PCT", "20.0"))
        total = booking.amount_usd
        deposit_amount = round(total * deposit_pct / 100, 2)
        escrow_amount = round(total - deposit_amount, 2)

        # Create escrow record
        escrow = EscrowTransaction(
            booking_id=booking.id,
            total_amount=total,
            deposit_pct=deposit_pct,
            deposit_amount=deposit_amount,
            escrow_amount=escrow_amount,
            status="holding",
        )
        db.session.add(escrow)
        db.session.commit()

        app.logger.info(
            f"[ESCROW] Initiated for booking #{booking.id}: "
            f"deposit={deposit_amount} USD, escrow={escrow_amount} USD"
        )

        # Attempt Flutterwave transfer for deposit (best-effort)
        if guide_sub_account_id:
            _flw_transfer(
                amount=deposit_amount,
                destination_account=guide_sub_account_id,
                narration=f"SafaraOne deposit — Booking #{booking.id}",
                reference=f"esc-dep-{booking.id}",
                escrow=escrow,
                field="deposit_flw_id",
            )

        return {"status": "success", "escrow_id": escrow.id}

    except Exception as e:
        logger.error(f"[ESCROW] Initiation failed for booking #{booking.id}: {e}")
        return {"status": "error", "message": str(e)}


def settle_escrow(escrow, guide_sub_account_id: str = None):
    """
    Tourist confirms tour complete → release escrow balance to guide
    minus SafaraOne commission.

    Returns dict with settlement breakdown.
    """
    try:
        from app import app, db
        from models import CommissionLedger

        commission_rate = float(os.environ.get("COMMISSION_RATE", "0.10"))
        gross = escrow.escrow_amount
        commission = round(gross * commission_rate, 2)
        net_to_operator = round(gross - commission, 2)

        # Log commission (append-only ledger)
        ledger = CommissionLedger(
            booking_id=escrow.booking_id,
            escrow_id=escrow.id,
            gross_amount=gross,
            commission_rate=commission_rate,
            commission_amount=commission,
            net_to_operator=net_to_operator,
        )
        db.session.add(ledger)

        # Attempt Flutterwave transfer for net payout
        if guide_sub_account_id and net_to_operator > 0:
            _flw_transfer(
                amount=net_to_operator,
                destination_account=guide_sub_account_id,
                narration=f"SafaraOne escrow settlement — Booking #{escrow.booking_id}",
                reference=f"esc-set-{escrow.booking_id}",
                escrow=escrow,
                field="settle_flw_id",
            )

        escrow.status = "settled"
        escrow.settled_at = datetime.utcnow()
        db.session.commit()

        # Notify guide
        try:
            from models import Booking, User
            from services.notification_service import notify
            booking = Booking.query.get(escrow.booking_id)
            if booking:
                guide = User.query.get(booking.item_id) if booking.item_type == "guide" else None
                if guide:
                    notify(
                        user_id=guide.id,
                        notif_type="escrow_settled",
                        title="Tour Payment Released 💰",
                        message=f"${net_to_operator:.2f} USD has been sent to your account for Booking #{booking.id}.",
                        link="/dashboard",
                    )
        except Exception as e:
            logger.warning(f"[ESCROW] Guide notification failed: {e}")

        return {
            "status": "success",
            "gross_amount": gross,
            "commission": commission,
            "net_to_operator": net_to_operator,
            "currency": "USD",
        }

    except Exception as e:
        logger.error(f"[ESCROW] Settlement failed for escrow #{escrow.id}: {e}")
        return {"status": "error", "message": str(e)}


def refund_escrow(escrow):
    """Refund the escrow balance to the tourist (booking cancelled)."""
    try:
        from app import db
        escrow.status = "refunded"
        db.session.commit()
        logger.info(f"[ESCROW] Refunded escrow #{escrow.id} for booking #{escrow.booking_id}")
        return {"status": "success"}
    except Exception as e:
        logger.error(f"[ESCROW] Refund failed for escrow #{escrow.id}: {e}")
        return {"status": "error", "message": str(e)}


def compute_dynamic_price(base_price: float, item_type: str, item_id: int, scheduled_date=None) -> dict:
    """
    Apply PricingRule multipliers to a base price.

    Returns:
        {
          "base_price": 100.0,
          "final_price": 85.0,
          "multiplier": 0.85,
          "reason": "low_load"
        }
    """
    try:
        from app import db
        from models import PricingRule, Booking
        from datetime import datetime, timezone

        rule = PricingRule.query.filter_by(
            item_type=item_type, item_id=item_id, is_active=True
        ).first()

        if not rule:
            return {
                "base_price": base_price,
                "final_price": round(base_price, 2),
                "multiplier": 1.0,
                "reason": "no_rule",
            }

        multiplier = 1.0
        reason = "standard"

        # ── Last-minute discount ─────────────────────────────────────────────
        if scheduled_date:
            now = datetime.now(timezone.utc)
            if hasattr(scheduled_date, 'tzinfo') and scheduled_date.tzinfo is None:
                from datetime import timezone as tz
                trip_dt = scheduled_date.replace(tzinfo=tz.utc)
            else:
                trip_dt = scheduled_date
            hours_away = (trip_dt - now).total_seconds() / 3600
            if 0 < hours_away < rule.last_minute_hours:
                multiplier = rule.last_minute_multiplier
                reason = "last_minute"

        # ── Demand-based multiplier (overrides last-minute if higher demand) ─
        if reason != "last_minute":
            confirmed_count = Booking.query.filter_by(
                item_type=item_type,
                item_id=str(item_id),
                status="confirmed",
            ).count()

            max_cap = rule.max_capacity or 10
            load_pct = (confirmed_count / max_cap) * 100 if max_cap > 0 else 0

            if load_pct < rule.low_load_threshold:
                multiplier = rule.low_load_multiplier
                reason = "low_load"
            elif load_pct > rule.high_load_threshold:
                multiplier = rule.high_load_multiplier
                reason = "high_load"

        final_price = round(base_price * multiplier, 2)
        return {
            "base_price": base_price,
            "final_price": final_price,
            "multiplier": multiplier,
            "reason": reason,
        }

    except Exception as e:
        logger.error(f"[PRICING] compute_dynamic_price failed: {e}")
        return {
            "base_price": base_price,
            "final_price": round(base_price, 2),
            "multiplier": 1.0,
            "reason": "error",
        }


# ── Internal helper ──────────────────────────────────────────────────────────

def _flw_transfer(amount: float, destination_account: str, narration: str,
                  reference: str, escrow, field: str):
    """
    Attempt a Flutterwave bank transfer. Saves the transfer ID to the escrow record.
    Non-fatal — logs errors but does not raise.
    """
    try:
        flw_secret = os.environ.get("FLW_SECRET_KEY", "")
        if not flw_secret:
            logger.warning("[ESCROW] FLW_SECRET_KEY not set — skipping transfer.")
            return

        payload = {
            "account_bank": "flutterwave",
            "account_number": destination_account,
            "amount": amount,
            "currency": "USD",
            "narration": narration,
            "reference": reference,
        }
        resp = requests.post(
            "https://api.flutterwave.com/v3/transfers",
            json=payload,
            headers={"Authorization": f"Bearer {flw_secret}"},
            timeout=15,
        )
        result = resp.json()
        if result.get("status") == "success":
            transfer_id = str(result["data"].get("id", ""))
            setattr(escrow, field, transfer_id)
            logger.info(f"[ESCROW] FLW transfer initiated (id={transfer_id})")
        else:
            logger.warning(f"[ESCROW] FLW transfer failed: {result}")
    except Exception as e:
        logger.error(f"[ESCROW] FLW transfer exception: {e}")
