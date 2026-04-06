"""
SafaraOne — KYC Service (Phase 8, Day 4, Feature #69)
======================================================
Uses extensions.py for db — zero circular import risk.
"""

import os
import logging
from datetime import datetime

# Clean import — no app dependency
from extensions import db
from models import KYCRecord, User

logger = logging.getLogger(__name__)

SMILE_PARTNER_ID  = os.environ.get("SMILE_IDENTITY_PARTNER_ID", "")
SMILE_API_KEY     = os.environ.get("SMILE_IDENTITY_API_KEY", "")
SUMSUB_APP_TOKEN  = os.environ.get("SUMSUB_APP_TOKEN", "")
SUMSUB_SECRET_KEY = os.environ.get("SUMSUB_SECRET_KEY", "")


# ─────────────────────────────────────────────────────────────────────────────
# Smile Identity
# ─────────────────────────────────────────────────────────────────────────────

def _submit_via_smile(guide_id, id_type, id_number, country,
                      selfie_image_base64, id_image_base64) -> dict:
    try:
        from smile_id_core import WebApi
        partner_params = {
            "user_id":  f"guide_{guide_id}",
            "job_id":   f"job_{guide_id}_{int(datetime.utcnow().timestamp())}",
            "job_type": 1,
        }
        id_info = {
            "first_name": "", "last_name": "",
            "country": country, "id_type": id_type,
            "id_number": id_number, "entered": True,
        }
        image_details = [
            {"image_type_id": 0, "image": selfie_image_base64},
            {"image_type_id": 1, "image": id_image_base64},
        ]
        options = {"return_job_status": True, "return_history": False, "return_images": False}
        web_api  = WebApi(
            partner_id=SMILE_PARTNER_ID,
            default_callback="",
            api_key=SMILE_API_KEY,
            sid_server=0,
        )
        response   = web_api.submit_job(partner_params, image_details, id_info, options)
        success    = bool(response.get("job_complete") and response.get("job_success"))
        confidence = None
        if response.get("result"):
            confidence = float(response["result"].get("ConfidenceValue", 0) or 0)
        return {
            "provider": "smile_identity", "job_id": partner_params["job_id"],
            "success": success, "confidence_value": confidence,
            "risk_score": max(0, 100 - (confidence or 0)),
        }
    except ImportError:
        logger.warning("[KYC] smile_id_core not installed — pip install smile-identity-core")
        return {"provider": "smile_identity", "success": False, "error": "SDK not installed"}
    except Exception as e:
        logger.error(f"[KYC] Smile Identity error: {e}")
        return {"provider": "smile_identity", "success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Sumsub Fallback
# ─────────────────────────────────────────────────────────────────────────────

def _submit_via_sumsub(guide_id, id_type, country) -> dict:
    try:
        import hashlib, hmac, time, requests as req
        ts     = str(int(time.time()))
        method = "POST"
        path   = "/resources/applicants?levelName=basic-kyc-level"
        body   = f'{{"externalUserId":"guide_{guide_id}","fixedInfo":{{"country":"{country}","idDocType":"{id_type}"}}}}'
        sig    = hmac.new(
            SUMSUB_SECRET_KEY.encode("utf-8"),
            f"{ts}{method}{path}{body}".encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = {
            "X-App-Token": SUMSUB_APP_TOKEN,
            "X-App-Access-Sig": sig,
            "X-App-Access-Ts": ts,
            "Content-Type": "application/json",
        }
        resp = req.post(f"https://api.sumsub.com{path}", data=body, headers=headers, timeout=10)
        data = resp.json()
        if "id" in data:
            applicant_id = data["id"]
            link_resp    = req.get(
                f"https://api.sumsub.com/resources/sdkIntegrations/levels/basic-kyc-level/websdkLink"
                f"?ttlInSecs=3600&externalUserId=guide_{guide_id}",
                headers=headers, timeout=10,
            )
            return {
                "provider": "sumsub", "applicant_id": applicant_id,
                "verify_url": link_resp.json().get("url"),
                "success": True, "async_mode": True,
            }
        return {"provider": "sumsub", "success": False, "error": str(data)}
    except Exception as e:
        logger.error(f"[KYC] Sumsub error: {e}")
        return {"provider": "sumsub", "success": False, "error": str(e)}


# ─────────────────────────────────────────────────────────────────────────────
# Stub mode
# ─────────────────────────────────────────────────────────────────────────────

def _stub_kyc(guide_id, id_type, country) -> dict:
    print(
        f"\n{'='*60}\n"
        f"🪪 KYC STUB — Guide #{guide_id} submitted {id_type} ({country})\n"
        f"Approve manually via admin panel: /admin/kyc\n"
        f"{'='*60}\n"
    )
    logger.info(f"[KYC STUB] Guide #{guide_id} queued for manual admin review")
    return {"provider": "stub", "success": True, "async_mode": True,
            "message": "KYC queued for manual admin review."}


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def submit_kyc(guide_id: int, id_type: str, id_number: str, country: str = "TZ",
               selfie_image_base64: str = None, id_image_base64: str = None) -> dict:
    """Submit identity verification for a guide. Creates/updates KYCRecord."""
    try:
        record = KYCRecord.query.filter_by(guide_id=guide_id).first()
        if not record:
            record = KYCRecord(guide_id=guide_id)
            db.session.add(record)

        record.id_type      = id_type
        record.country      = country
        record.id_number    = f"****{id_number[-4:]}" if id_number and len(id_number) > 4 else "****"
        record.status       = "pending"
        record.submitted_at = datetime.utcnow()
        db.session.commit()

        if SMILE_PARTNER_ID and SMILE_API_KEY and selfie_image_base64 and id_image_base64:
            result = _submit_via_smile(guide_id, id_type, id_number, country,
                                       selfie_image_base64, id_image_base64)
            if result.get("success") and not result.get("async_mode"):
                record.smile_job_id     = result.get("job_id")
                record.confidence_value = result.get("confidence_value")
                record.risk_score       = result.get("risk_score")
                confidence = record.confidence_value or 0
                record.status = "approved" if confidence >= 80 else ("pending" if confidence >= 50 else "flagged")
                db.session.commit()
        elif SUMSUB_APP_TOKEN and SUMSUB_SECRET_KEY:
            result = _submit_via_sumsub(guide_id, id_type, country)
        else:
            result = _stub_kyc(guide_id, id_type, country)

        return result

    except Exception as e:
        logger.error(f"[KYC] submit_kyc failed for guide #{guide_id}: {e}")
        return {"success": False, "error": str(e)}


def process_sumsub_webhook(payload: dict) -> bool:
    """Handle Sumsub async webhook result. Called from POST /api/kyc/sumsub-webhook."""
    from services.notification_service import notify_kyc_result
    try:
        review_result = payload.get("reviewResult", {})
        review_answer = review_result.get("reviewAnswer")
        external_id   = payload.get("externalUserId", "")
        if not external_id.startswith("guide_"):
            return False
        guide_id = int(external_id.replace("guide_", ""))

        record = KYCRecord.query.filter_by(guide_id=guide_id).first()
        if not record:
            return False

        approved           = review_answer == "GREEN"
        record.status      = "approved" if approved else "rejected"
        record.reviewed_at = datetime.utcnow()
        record.admin_notes = (review_result.get("rejectLabels") or [""])[0] if not approved else None
        db.session.commit()

        guide = db.session.get(User, guide_id)
        if guide:
            notify_kyc_result(guide, approved, record.admin_notes)
        return True
    except Exception as e:
        logger.error(f"[KYC] Sumsub webhook error: {e}")
        return False


def get_kyc_status(guide_id: int) -> dict:
    """Return current KYC status dict for a guide. Safe to call anywhere."""
    try:
        record = KYCRecord.query.filter_by(guide_id=guide_id).first()
        if not record:
            return {"status": "not_submitted", "record": None}
        return {"status": record.status, "record": record.to_dict()}
    except Exception as e:
        logger.error(f"[KYC] get_kyc_status failed: {e}")
        return {"status": "error", "record": None}
