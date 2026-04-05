"""
SafaraOne — Email Service (Phase 7, Feature #46)
=================================================
Handles all transactional emails:
  - Booking receipt (after successful payment)
  - Cancellation confirmation (with refund status)

Provider chain (first available key wins):
  1. Resend       — free 3,000/month, no SDK needed, just RESEND_API_KEY
  2. SendGrid     — SENDGRID_API_KEY
  3. Brevo        — BREVO_API_KEY
  4. Console stub — logs to server output when no key is configured

To enable email:
  Add RESEND_API_KEY to your Render environment variables.
  Sign up free at resend.com (no credit card required).
  Also set RESEND_FROM_EMAIL to a verified email or use the
  onboarding default: onboarding@resend.dev (works immediately).

Usage:
    from services.email_service import send_booking_receipt, send_cancellation_email
"""

import os
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

RESEND_API_KEY     = os.environ.get("RESEND_API_KEY", "")
SENDGRID_API_KEY   = os.environ.get("SENDGRID_API_KEY", "")
BREVO_API_KEY      = os.environ.get("BREVO_API_KEY", "")
# Resend free tier allows onboarding@resend.dev as sender until you verify a domain
FROM_EMAIL         = os.environ.get("RESEND_FROM_EMAIL",
                     os.environ.get("SENDGRID_FROM_EMAIL", "onboarding@resend.dev"))
FROM_NAME          = "SafaraOne"


# ─────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────────────────────────────────────

def _send_via_resend(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """Send email via Resend API (free tier, no SDK needed). Returns True on success."""
    import urllib.request
    import json as _json
    try:
        payload = _json.dumps({
            "from": f"{FROM_NAME} <{FROM_EMAIL}>",
            "to":   [to_email],
            "subject": subject,
            "html": html_body,
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {RESEND_API_KEY}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status in (200, 201):
                logger.info(f"[EMAIL] Resend sent '{subject}' to {to_email}")
                return True
            logger.warning(f"[EMAIL] Resend non-2xx: {resp.status}")
            return False
    except Exception as e:
        logger.error(f"[EMAIL] Resend error: {e}")
        return False


def _send_via_sendgrid(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """Send email via SendGrid. Returns True on success."""
    try:
        import sendgrid
        from sendgrid.helpers.mail import Mail, Email, To, Content

        sg = sendgrid.SendGridAPIClient(api_key=SENDGRID_API_KEY)
        message = Mail(
            from_email=Email(FROM_EMAIL, FROM_NAME),
            to_emails=To(to_email, to_name),
            subject=subject,
            html_content=Content("text/html", html_body),
        )
        response = sg.client.mail.send.post(request_body=message.get())
        if response.status_code in (200, 201, 202):
            logger.info(f"[EMAIL] SendGrid sent '{subject}' to {to_email}")
            return True
        logger.warning(f"[EMAIL] SendGrid non-2xx: {response.status_code}")
        return False
    except Exception as e:
        logger.error(f"[EMAIL] SendGrid error: {e}")
        return False


def _send_via_brevo(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """Send email via Brevo (Sendinblue). Returns True on success."""
    try:
        import sib_api_v3_sdk
        from sib_api_v3_sdk.rest import ApiException

        configuration = sib_api_v3_sdk.Configuration()
        configuration.api_key["api-key"] = BREVO_API_KEY
        api_instance = sib_api_v3_sdk.TransactionalEmailsApi(
            sib_api_v3_sdk.ApiClient(configuration)
        )
        send_smtp_email = sib_api_v3_sdk.SendSmtpEmail(
            sender={"name": FROM_NAME, "email": FROM_EMAIL},
            to=[{"email": to_email, "name": to_name}],
            subject=subject,
            html_content=html_body,
        )
        api_instance.send_transac_email(send_smtp_email)
        logger.info(f"[EMAIL] Brevo sent '{subject}' to {to_email}")
        return True
    except Exception as e:
        logger.error(f"[EMAIL] Brevo error: {e}")
        return False


def _send_stub(to_email: str, subject: str, html_body: str) -> bool:
    """Console stub — logs email when no provider key is configured."""
    logger.info(
        f"\n{'='*60}\n"
        f"[EMAIL STUB — no provider key configured]\n"
        f"To      : {to_email}\n"
        f"Subject : {subject}\n"
        f"Body    : (HTML — {len(html_body)} chars)\n"
        f"{'='*60}"
    )
    print(
        f"\n{'='*60}\n"
        f"📧 EMAIL STUB\n"
        f"To      : {to_email}\n"
        f"Subject : {subject}\n"
        f"[HTML body suppressed — {len(html_body)} chars]\n"
        f"{'='*60}\n"
    )
    return True  # Return True so app flow continues uninterrupted


def _dispatch(to_email: str, to_name: str, subject: str, html_body: str) -> bool:
    """Route to the correct provider, with automatic fallback chain.
    Priority: Resend → SendGrid → Brevo → console stub
    """
    # 1. Resend (primary — free, no SDK, just needs RESEND_API_KEY)
    if RESEND_API_KEY and not RESEND_API_KEY.startswith("re_paste_"):
        success = _send_via_resend(to_email, to_name, subject, html_body)
        if success:
            return True
        logger.warning("[EMAIL] Resend failed — trying SendGrid fallback")

    # 2. SendGrid
    if SENDGRID_API_KEY and not SENDGRID_API_KEY.startswith("SG.paste_"):
        success = _send_via_sendgrid(to_email, to_name, subject, html_body)
        if success:
            return True
        logger.warning("[EMAIL] SendGrid failed — trying Brevo fallback")

    # 3. Brevo
    if BREVO_API_KEY and not BREVO_API_KEY.startswith("paste_"):
        success = _send_via_brevo(to_email, to_name, subject, html_body)
        if success:
            return True
        logger.warning("[EMAIL] Brevo failed — falling back to console stub")

    # 4. Console stub
    return _send_stub(to_email, subject, html_body)


# ─────────────────────────────────────────────────────────────────────────────
# HTML template builders
# ─────────────────────────────────────────────────────────────────────────────

def _base_html(title: str, content: str) -> str:
    """Wraps email content in SafaraOne branded HTML shell."""
    return f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>{title}</title>
  <style>
    body {{
      margin: 0; padding: 0;
      background: #0f1117;
      font-family: 'Segoe UI', Arial, sans-serif;
      color: #e2e8f0;
    }}
    .wrapper {{
      max-width: 600px;
      margin: 0 auto;
      padding: 40px 20px;
    }}
    .card {{
      background: rgba(255,255,255,0.05);
      border: 1px solid rgba(255,255,255,0.1);
      border-radius: 16px;
      padding: 36px;
      backdrop-filter: blur(10px);
    }}
    .logo {{
      font-size: 28px;
      font-weight: 800;
      color: #f97316;
      margin-bottom: 8px;
      letter-spacing: -0.5px;
    }}
    .logo span {{ color: #ffffff; }}
    .tagline {{
      font-size: 13px;
      color: #94a3b8;
      margin-bottom: 32px;
    }}
    h1 {{
      font-size: 22px;
      color: #ffffff;
      margin: 0 0 24px;
      font-weight: 700;
    }}
    .row {{
      display: flex;
      justify-content: space-between;
      padding: 12px 0;
      border-bottom: 1px solid rgba(255,255,255,0.07);
      font-size: 14px;
    }}
    .row:last-of-type {{ border-bottom: none; }}
    .label {{ color: #94a3b8; }}
    .value {{ color: #e2e8f0; font-weight: 500; text-align: right; }}
    .total-row {{
      background: rgba(249,115,22,0.1);
      border-radius: 8px;
      padding: 14px 16px;
      margin: 20px 0;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }}
    .total-label {{ font-size: 14px; color: #f97316; font-weight: 600; }}
    .total-value {{ font-size: 20px; color: #ffffff; font-weight: 800; }}
    .badge {{
      display: inline-block;
      padding: 4px 12px;
      border-radius: 99px;
      font-size: 12px;
      font-weight: 600;
    }}
    .badge-success {{ background: rgba(16,185,129,0.15); color: #10b981; }}
    .badge-warning {{ background: rgba(251,191,36,0.15); color: #fbbf24; }}
    .badge-danger  {{ background: rgba(239,68,68,0.15);  color: #ef4444; }}
    .footer {{
      margin-top: 32px;
      font-size: 12px;
      color: #475569;
      text-align: center;
      line-height: 1.8;
    }}
    .footer a {{ color: #f97316; text-decoration: none; }}
    .divider {{
      height: 1px;
      background: rgba(255,255,255,0.07);
      margin: 24px 0;
    }}
    p {{ font-size: 14px; color: #94a3b8; line-height: 1.7; margin: 0 0 12px; }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="card">
      <div class="logo">Safara<span>One</span> 🦒</div>
      <div class="tagline">Africa's travel platform</div>
      {content}
    </div>
    <div class="footer">
      © {datetime.now().year} SafaraOne · Tanzania<br/>
      Questions? <a href="mailto:support@safaraone.com">support@safaraone.com</a><br/>
      <a href="#">Unsubscribe</a> · <a href="#">Privacy Policy</a>
    </div>
  </div>
</body>
</html>
""".strip()


def _build_receipt_html(username: str, booking_info: dict) -> str:
    """
    Build HTML for booking receipt email.

    booking_info keys:
      - booking_id    : int or str
      - item_name     : str  (guide/stay/experience name)
      - item_type     : str  ("Guide", "Stay", "Experience")
      - scheduled_date: str  (human-readable date)
      - amount_usd    : str  (e.g. "120.00")
      - amount_tzs    : str | None (e.g. "312,000" — formatted)
      - currency      : str  ("USD" or "TZS")
      - payment_method: str  ("card", "mobile_money")
      - tx_ref        : str  (Flutterwave tx_ref)
      - guide_name    : str | None
      - guide_phone   : str | None
    """
    bi = booking_info
    currency_display = "TZS" if bi.get("currency") == "TZS" else "USD"
    amount_display = bi.get("amount_tzs") if bi.get("currency") == "TZS" else bi.get("amount_usd", "—")
    payment_label = "Mobile Money" if bi.get("payment_method") == "mobile_money" else "Card"

    guide_section = ""
    if bi.get("guide_name"):
        guide_section = f"""
        <div class="divider"></div>
        <p style="color:#ffffff; font-weight:600; margin-bottom:12px;">Your Guide</p>
        <div class="row">
          <span class="label">Name</span>
          <span class="value">{bi.get('guide_name', '—')}</span>
        </div>
        <div class="row">
          <span class="label">Contact</span>
          <span class="value">{bi.get('guide_phone', '—')}</span>
        </div>
        """

    content = f"""
    <h1>Booking Confirmed! ✅</h1>
    <p>Hi {username}, your booking is confirmed and your spot is secured. Here is your receipt.</p>

    <div class="row">
      <span class="label">Booking Reference</span>
      <span class="value">#{bi.get('booking_id', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Item</span>
      <span class="value">{bi.get('item_name', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Type</span>
      <span class="value">{bi.get('item_type', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Date</span>
      <span class="value">{bi.get('scheduled_date', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Payment Method</span>
      <span class="value">{payment_label}</span>
    </div>
    <div class="row">
      <span class="label">Transaction Ref</span>
      <span class="value" style="font-size:12px; color:#64748b;">{bi.get('tx_ref', '—')}</span>
    </div>

    <div class="total-row">
      <span class="total-label">Amount Paid</span>
      <span class="total-value">{currency_display} {amount_display}</span>
    </div>

    <span class="badge badge-success">Payment Successful</span>

    {guide_section}

    <div class="divider"></div>
    <p>
      Need to cancel? You can cancel from your
      <a href="https://safaraone.com/my-trips" style="color:#f97316;">My Trips</a> page.
      Cancellations made more than 48 hours before your trip date are fully refunded.
    </p>
    <p style="color:#475569; font-size:12px;">
      This is your official receipt. Please keep it for your records.
    </p>
    """
    return _base_html("Booking Confirmed — SafaraOne", content)


def _build_cancellation_html(username: str, booking_info: dict, refund_info: dict) -> str:
    """
    Build HTML for cancellation confirmation email.

    refund_info keys:
      - refund_eligible : bool
      - refund_status   : str  ("processed", "requested", "none")
      - refund_amount   : str | None
      - refund_currency : str | None
      - refund_id       : str | None
      - hours_until_trip: float | None
    """
    bi = booking_info
    ri = refund_info

    if ri.get("refund_status") == "processed":
        refund_badge = '<span class="badge badge-success">Refund Initiated</span>'
        refund_note = f"""
        <div class="row">
          <span class="label">Refund Amount</span>
          <span class="value">{ri.get('refund_currency','USD')} {ri.get('refund_amount','—')}</span>
        </div>
        <div class="row">
          <span class="label">Refund Reference</span>
          <span class="value" style="font-size:12px;">{ri.get('refund_id','—')}</span>
        </div>
        <p>Your refund has been submitted to Flutterwave and should appear in 3–5 business days.</p>
        """
    elif ri.get("refund_status") == "requested":
        refund_badge = '<span class="badge badge-warning">Refund Under Review</span>'
        refund_note = """
        <p>
          Your cancellation was made within 48 hours of your trip date.
          Your refund request has been logged and will be reviewed by our team within 24 hours.
        </p>
        """
    else:
        refund_badge = '<span class="badge badge-danger">No Refund Applicable</span>'
        refund_note = """
        <p>This booking was not eligible for a refund per our cancellation policy.</p>
        """

    content = f"""
    <h1>Booking Cancelled</h1>
    <p>Hi {username}, your booking has been cancelled. Here are the details.</p>

    <div class="row">
      <span class="label">Booking Reference</span>
      <span class="value">#{bi.get('booking_id', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Item</span>
      <span class="value">{bi.get('item_name', '—')}</span>
    </div>
    <div class="row">
      <span class="label">Cancelled On</span>
      <span class="value">{datetime.now().strftime('%d %b %Y, %H:%M')}</span>
    </div>

    <div class="divider"></div>

    <p style="color:#ffffff; font-weight:600; margin-bottom:12px;">Refund Status</p>
    {refund_badge}
    <div style="margin-top: 16px;">
      {refund_note}
    </div>

    <div class="divider"></div>
    <p>
      Browse more guides, stays, and experiences on
      <a href="https://safaraone.com" style="color:#f97316;">SafaraOne</a>.
    </p>
    """
    return _base_html("Booking Cancelled — SafaraOne", content)


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

def send_booking_receipt(user_email: str, username: str, booking_info: dict) -> bool:
    """
    Send a booking confirmation receipt email.

    Args:
        user_email   : Recipient email address
        username     : Tourist's display name
        booking_info : Dict with booking details (see _build_receipt_html for keys)

    Returns:
        True if email was dispatched (or stubbed), False on unrecoverable error.
    """
    subject = f"✅ Booking Confirmed — {booking_info.get('item_name', 'Your Trip')} | SafaraOne"
    html = _build_receipt_html(username, booking_info)
    return _dispatch(user_email, username, subject, html)


def send_cancellation_email(
    user_email: str,
    username: str,
    booking_info: dict,
    refund_info: dict,
) -> bool:
    """
    Send a cancellation confirmation email.

    Args:
        user_email   : Recipient email address
        username     : Tourist's display name
        booking_info : Dict with booking details
        refund_info  : Dict with refund outcome details (see _build_cancellation_html for keys)

    Returns:
        True if email was dispatched (or stubbed), False on unrecoverable error.
    """
    subject = f"Booking Cancelled — #{booking_info.get('booking_id', '')} | SafaraOne"
    html = _build_cancellation_html(username, booking_info, refund_info)
    return _dispatch(user_email, username, subject, html)
