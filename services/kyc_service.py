"""
SafaraOne — KYC Identity Verification Service (Phase 8)
=========================================================
Supports:
  - Smile Identity (for Tanzania national IDs)
  - Sumsub (global async flow with webhook)
  - Stub mode (when neither API key is configured)

In stub mode: submission is accepted, record created with status=pending,
and admin must manually approve/reject from the admin KYC panel.
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


def submit_kyc(guide_id: int, id_type: str, id_number: str,
               country: str = "TZ",
               selfie_image_base64: str = None,
               id_image_base64: str = None) -> dict:
    """
    Submit KYC documents for a guide.

    Returns one of:
      {"success": True}                            — verified synchronously (Smile ID)
      {"async_mode": True, "verify_url": "..."}    — Sumsub async SDK URL
      {"success": True, "stub": True}              — no service configured
    """
    try:
        from app import db
        from models import KYCRecord

        # Upsert the KYC record
        record = KYCRecord.query.filter_by(guide_id=guide_id).first()
        if not record:
            record = KYCRecord(guide_id=guide_id)
            db.session.add(record)

        record.id_type = id_type
        record.id_number = _mask_id(id_number)
        record.country = country
        record.status = "pending"
        record.submitted_at = datetime.utcnow()
        db.session.commit()

        smile_partner_id = os.environ.get("SMILE_IDENTITY_PARTNER_ID", "")
        smile_api_key = os.environ.get("SMILE_IDENTITY_API_KEY", "")
        sumsub_app_token = os.environ.get("SUMSUB_APP_TOKEN", "")

        # ── Try Smile Identity ────────────────────────────────────────────────
        if smile_partner_id and smile_api_key:
            return _submit_smile_identity(
                record, guide_id, id_type, id_number, country,
                selfie_image_base64, id_image_base64,
                smile_partner_id, smile_api_key
            )

        # ── Try Sumsub ───────────────────────────────────────────────────────
        if sumsub_app_token:
            return _submit_sumsub(record, guide_id, sumsub_app_token)

        # ── Stub mode ────────────────────────────────────────────────────────
        logger.warning(
            f"[KYC] No API keys configured. Guide #{guide_id} queued for manual review."
        )
        return {"success": True, "stub": True}

    except Exception as e:
        logger.error(f"[KYC] submit_kyc failed for guide #{guide_id}: {e}")
        return {"success": False, "error": str(e)}


def get_kyc_status(guide_id: int) -> dict:
    """Return the current KYC status for a guide, or {'status': 'not_submitted'}."""
    try:
        from models import KYCRecord
        record = KYCRecord.query.filter_by(guide_id=guide_id).first()
        if not record:
            return {"status": "not_submitted"}
        return record.to_dict()
    except Exception as e:
        logger.error(f"[KYC] get_kyc_status failed for guide #{guide_id}: {e}")
        return {"status": "error"}


def process_sumsub_webhook(payload: dict) -> bool:
    """
    Handle Sumsub async verification webhook.
    Updates KYCRecord status based on Sumsub result.
    Returns True on success, False on failure.

    Sumsub webhook payload (simplified):
      {"applicantId": "...", "reviewStatus": "completed",
       "reviewResult": {"reviewAnswer": "GREEN"|"RED"}}
    """
    try:
        from app import db
        from models import KYCRecord

        applicant_id = payload.get("applicantId", "")
        review_status = payload.get("reviewStatus", "")
        review_result = payload.get("reviewResult", {})
        answer = review_result.get("reviewAnswer", "").upper()

        record = KYCRecord.query.filter_by(smile_job_id=applicant_id).first()
        if not record:
            logger.warning(f"[KYC] Sumsub webhook: no record for applicant {applicant_id}")
            return False

        if review_status == "completed":
            if answer == "GREEN":
                record.status = "approved"
            elif answer == "RED":
                record.status = "rejected"
            else:
                record.status = "flagged"
            record.reviewed_at = datetime.utcnow()
            db.session.commit()
            logger.info(f"[KYC] Sumsub webhook processed: guide {record.guide_id} → {record.status}")

        return True

    except Exception as e:
        logger.error(f"[KYC] process_sumsub_webhook failed: {e}")
        return False


# ── Internal helpers ─────────────────────────────────────────────────────────

def _mask_id(id_number: str) -> str:
    """Mask all but the last 4 chars of an ID number for storage."""
    if not id_number or len(id_number) <= 4:
        return "****"
    return "*" * (len(id_number) - 4) + id_number[-4:]


def _submit_smile_identity(record, guide_id, id_type, id_number, country,
                           selfie_b64, id_b64, partner_id, api_key) -> dict:
    """Attempt Smile Identity verification (Tanzania-focused)."""
    try:
        import json
        import requests

        payload = {
            "source_sdk": "rest_api",
            "source_sdk_version": "1.0",
            "partner_id": partner_id,
            "partner_params": {
                "user_id": str(guide_id),
                "job_id": f"safaraone-kyc-{guide_id}",
                "job_type": 5,  # Enhanced KYC
            },
            "id_info": {
                "first_name": "",
                "last_name": "",
                "country": country,
                "id_type": id_type,
                "id_number": id_number,
            },
            "api_key": api_key,
        }

        if selfie_b64:
            payload["images"] = [{"image_type_id": 0, "image": selfie_b64}]
        if id_b64:
            payload.setdefault("images", [])
            payload["images"].append({"image_type_id": 1, "image": id_b64})

        resp = requests.post(
            "https://testapi.smileidentity.com/v1/id_verification",
            json=payload,
            timeout=30,
        )
        result = resp.json()

        from app import db
        actions = result.get("Actions", {})
        smile_result = actions.get("Return_Personal_Info", "Unknown")

        record.smile_job_id = result.get("SmileJobID", "")
        if smile_result == "Returned":
            record.status = "approved"
            record.confidence_value = float(result.get("ConfidenceValue", 0) or 0)
        else:
            record.status = "pending"

        db.session.commit()

        if record.status == "approved":
            from services.notification_service import notify_kyc_result
            from models import User
            guide = User.query.get(guide_id)
            if guide:
                guide.is_verified = True
                db.session.commit()
                notify_kyc_result(guide, approved=True)
            return {"success": True}
        else:
            return {"success": False, "pending": True}

    except Exception as e:
        logger.error(f"[KYC] Smile Identity call failed: {e}")
        # Fall through — record is already saved as pending
        return {"success": True, "stub": True}


def _submit_sumsub(record, guide_id, app_token) -> dict:
    """Submit to Sumsub and return an async applicant URL."""
    try:
        import hmac
        import hashlib
        import time
        import requests

        secret_key = os.environ.get("SUMSUB_SECRET_KEY", "")
        base_url = "https://api.sumsub.com"
        ts = str(int(time.time()))
        external_user_id = f"safaraone-guide-{guide_id}"

        # Create applicant
        path = "/resources/applicants?levelName=id-and-selfie"
        body = {"externalUserId": external_user_id}
        body_str = '{"externalUserId":"' + external_user_id + '"}'

        signature_str = ts + "POST" + path + body_str
        signature = hmac.new(
            secret_key.encode("utf-8"),
            signature_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "X-App-Token": app_token,
            "X-App-Access-Sig": signature,
            "X-App-Access-Ts": ts,
        }

        resp = requests.post(base_url + path, json=body, headers=headers, timeout=15)
        applicant = resp.json()
        applicant_id = applicant.get("id", "")

        from app import db
        record.smile_job_id = applicant_id  # Reuse field for Sumsub applicant ID
        db.session.commit()

        verify_url = f"https://in.sumsub.com/idensic/l/#/{applicant_id}"
        return {"async_mode": True, "verify_url": verify_url}

    except Exception as e:
        logger.error(f"[KYC] Sumsub submission failed: {e}")
        return {"success": True, "stub": True}
