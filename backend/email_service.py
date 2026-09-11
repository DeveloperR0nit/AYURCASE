"""
AYURCASE Email Service
Handles sending welcome and notification emails to registered patients and users.
Supports live SMTP delivery (TLS/SSL) with fallback to local logging and SQLite persistence.
"""

import os
import json
import html
import threading
import urllib.request
import urllib.error
from datetime import datetime


try:
    from database import get_db_connection
except ImportError:
    from backend.database import get_db_connection

def send_via_brevo(recipient, recipient_name, subject, body_text, body_html):
    """
    Sends a transactional email through Brevo's HTTPS API.
    Uses HTTPS instead of SMTP so it works on Render Free.
    """
    api_key = os.getenv("BREVO_API_KEY", "").strip()

    if not api_key:
        return {
            "success": False,
            "error": "BREVO_API_KEY is not configured"
        }

    from_email = (
        os.getenv("BREVO_FROM_EMAIL")
        or os.getenv("SMTP_FROM_EMAIL")
        or ""
    ).strip()

    from_name = (
        os.getenv("BREVO_FROM_NAME")
        or os.getenv("SMTP_FROM_NAME")
        or "AYURCASE Digital Health Portal"
    ).strip()

    if not from_email:
        return {
            "success": False,
            "error": "BREVO_FROM_EMAIL is not configured"
        }

    payload = {
        "sender": {
            "name": from_name,
            "email": from_email
        },
        "to": [
            {
                "email": recipient,
                "name": recipient_name or ""
            }
        ],
        "subject": subject,
        "textContent": body_text,
        "htmlContent": body_html
    }

    try:
        data = json.dumps(payload).encode("utf-8")

        request = urllib.request.Request(
            "https://api.brevo.com/v3/smtp/email",
            data=data,
            headers={
                "accept": "application/json",
                "api-key": api_key,
                "content-type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(request, timeout=15) as response:
            response_body = response.read().decode("utf-8")
            result = json.loads(response_body) if response_body else {}

        print(
            f"[EMAIL SERVICE] Email successfully sent via Brevo API "
            f"to {recipient}"
        )

        return {
            "success": True,
            "status": "SENT",
            "recipient": recipient,
            "message_id": result.get("messageId")
        }

    except urllib.error.HTTPError as e:
        error_body = e.read().decode("utf-8", errors="replace")
        print(
            f"[EMAIL SERVICE] Brevo API HTTP error "
            f"{e.code}: {error_body}"
        )
        return {
            "success": False,
            "status": "FAILED",
            "error": f"Brevo API HTTP {e.code}: {error_body}"
        }

    except Exception as e:
        print(f"[EMAIL SERVICE] Brevo API error: {e}")
        return {
            "success": False,
            "status": "FAILED",
            "error": str(e)
        }

def get_smtp_config():
    """Retrieves SMTP configuration from environment variables."""
    try:
        from dotenv import load_dotenv
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            load_dotenv(override=True)
    except Exception:
        pass

    host = os.getenv("SMTP_HOST", "").strip()
    port_str = os.getenv("SMTP_PORT", "587").strip()
    try:
        port = int(port_str)
    except ValueError:
        port = 587

    user = os.getenv("SMTP_USER", "").strip()
    password = (os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or "").strip().replace(" ", "")
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip() or user or "no-reply@ayurcase.gov.in"
    from_name = os.getenv("SMTP_FROM_NAME", "AYURCASE Digital Health Portal").strip()

    use_ssl = (
        os.getenv("SMTP_USE_SSL", "false").lower() in ("true", "1", "yes")
        or port == 465
    )
    use_tls = (
        os.getenv("SMTP_USE_TLS", "true").lower() in ("true", "1", "yes")
        and not use_ssl
    )

    return {
        "host": host,
        "port": port,
        "user": user,
        "password": password,
        "from_email": from_email,
        "from_name": from_name,
        "use_ssl": use_ssl,
        "use_tls": use_tls,
        "configured": bool(host and user and password),
    }


def format_detail(val, fallback="Not specified"):
    """Returns a clean display string for a demographic field."""
    if val is None:
        return fallback
    s = str(val).strip()
    return s if s else fallback


def build_welcome_email_content(user_data, user_info=None):
    """
    Constructs both the plain text and rich HTML email contents containing
    a welcome message and all demographic/account details entered at signup.
    """
    details = (user_info or {}).get("details", {})

    full_name = (
        user_data.get("name")
        or user_data.get("full_name")
        or (user_info or {}).get("full_name")
        or "Valued Patient"
    ).strip()

    email_addr = (
        user_data.get("email")
        or user_data.get("username")
        or (user_info or {}).get("username")
        or ""
    ).strip()

    phone_num = (
        user_data.get("phone")
        or details.get("phone")
        or (user_info or {}).get("phone")
        or "Not provided"
    ).strip()

    abha_id = (
        user_data.get("abha_id")
        or user_data.get("abhaId")
        or details.get("abha_id")
        or (user_info or {}).get("identifier")
        or "ABHA Assigned"
    ).strip()

    age_val = user_data.get("age") or details.get("age")
    age_str = f"{age_val} years" if age_val else "Not specified"

    gender_val = format_detail(user_data.get("gender") or details.get("gender"))

    blood_group_val = format_detail(
        user_data.get("blood_group")
        or user_data.get("bloodGroup")
        or details.get("blood_group"),
        fallback="Not recorded"
    )

    raw_prakriti = (
        user_data.get("prakriti_primary")
        or user_data.get("prakriti")
        or details.get("prakriti_primary")
        or details.get("prakriti")
    )
    prakriti_val = str(raw_prakriti).strip() if (raw_prakriti and str(raw_prakriti).strip() not in ("Not set", "None")) else "Not set"

    portal_login_url = os.getenv(
        "PATIENT_LOGIN_URL",
        "https://ayurcase-u601.onrender.com/login-patient.html"
    ).strip()

    timestamp_str = datetime.now().strftime("%d %B %Y, %I:%M %p")

    subject = f"Welcome to AYURCASE - Digital Health Account Created [ABHA: {abha_id}]"

    # Plain text version
    body_text = f"""Welcome to AYURCASE - National Digital Ayush Health Platform
================================================================================

Dear {full_name},

Welcome to AYURCASE! Your digital health account has been successfully created under the Ayushman Bharat Digital Mission (ABDM). We are delighted to welcome you to India's premier digital Ayurveda and AYUSH health platform.

YOUR REGISTRATION & ACCOUNT DETAILS:
--------------------------------------------------------------------------------
- Full Name:            {full_name}
- ABHA Health ID:       {abha_id}
- Registered Email:     {email_addr}
- Contact Phone:        {phone_num}
- Age:                  {age_str}
- Gender:               {gender_val}
- Blood Group:          {blood_group_val}
- Ayurvedic Prakriti:   {prakriti_val}
- Account Created:      {timestamp_str}
--------------------------------------------------------------------------------

WHAT YOU CAN DO WITH YOUR AYURCASE ACCOUNT:
1. Digital ABHA Health Card:
   Review and download your official ABDM-compliant health card with QR code.
2. Prakriti Self-Assessment:
   Discover and track your Ayurvedic dosha balance (Vata, Pitta, Kapha).
3. Book AYUSH Consultations:
   Schedule in-clinic or online appointments with verified Ayurvedic physicians.
4. Secure Clinical Records:
   Access your diagnosis summaries, prescriptions, and follow-up schedules anytime.

LOGIN TO PATIENT PORTAL:
You can log in anytime using your ABHA ID ({abha_id}) or your registered email ({email_addr}) at:
{portal_login_url}

SECURITY NOTICE:
Never share your AYURCASE password with anyone. AYURCASE support will never ask for your password via email, phone, or message.

Warm regards,
The AYURCASE Healthcare Team
Ministry of Ayush Standards • ABDM Compliant
"""

    # Escaped values for safe HTML rendering
    safe_name = html.escape(full_name)
    safe_email = html.escape(email_addr)
    safe_phone = html.escape(phone_num)
    safe_abha = html.escape(abha_id)
    safe_age = html.escape(age_str)
    safe_gender = html.escape(gender_val)
    safe_blood = html.escape(blood_group_val)
    safe_prakriti = html.escape(prakriti_val)
    safe_time = html.escape(timestamp_str)

    # Rich HTML version
    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>{html.escape(subject)}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f7f4; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; color: #1e293b; line-height: 1.6;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f4f7f4; padding: 30px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 620px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;" cellspacing="0" cellpadding="0" border="0">
          
          <!-- BRAND HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #1b4d36 0%, #2d7350 100%); padding: 32px 28px; text-align: center; color: #ffffff;">
              <div style="display: inline-block; width: 50px; height: 50px; line-height: 50px; border-radius: 12px; background: rgba(255,255,255,0.18); font-size: 24px; margin-bottom: 12px;">🌿</div>
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; color: #ffffff;">AYURCASE</h1>
              <p style="margin: 6px 0 0; font-size: 13px; color: #d1fae5; font-weight: 500; letter-spacing: 0.3px;">National Digital Ayush Health Platform • ABDM Compliant</p>
            </td>
          </tr>

          <!-- MAIN BODY -->
          <tr>
            <td style="padding: 32px 28px;">
              
              <!-- WELCOME BANNER -->
              <div style="background-color: #e8f5ec; border-left: 4px solid #2d7350; border-radius: 8px; padding: 14px 18px; margin-bottom: 24px;">
                <h2 style="margin: 0 0 6px; font-size: 18px; color: #173b2b;">Welcome to AYURCASE, {safe_name}!</h2>
                <p style="margin: 0; font-size: 13.5px; color: #2d553e;">Your digital health account has been successfully created under the <strong>Ayushman Bharat Digital Mission (ABDM)</strong> framework.</p>
              </div>

              <p style="font-size: 14px; color: #334155; margin: 0 0 20px;">
                We are thrilled to welcome you. You now have secure, centralized access to your verified ABHA health records, consultation bookings, and personalized Ayurvedic wellness guidance.
              </p>

              <!-- REGISTRATION DETAILS CARD -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8faf8; border: 1px solid #dcf0e2; border-radius: 12px; margin-bottom: 26px; overflow: hidden;">
                <tr>
                  <td colspan="2" style="background-color: #e1f1e6; padding: 12px 18px; font-size: 13px; font-weight: 700; color: #173b2b; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #dcf0e2;">
                    📋 Your Registration &amp; Profile Details
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; width: 38%; border-bottom: 1px solid #edf5ee;">Full Name:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #edf5ee;">{safe_name}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">ABHA Health ID:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #1b4d36; font-weight: 700; font-family: monospace; border-bottom: 1px solid #edf5ee;">
                    <span style="background-color: #d1fae5; color: #065f46; padding: 3px 8px; border-radius: 6px; font-size: 12.5px;">{safe_abha}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Registered Email:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 500; border-bottom: 1px solid #edf5ee;">{safe_email}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Phone Number:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #edf5ee;">{safe_phone}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Age:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 500; border-bottom: 1px solid #edf5ee;">{safe_age}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Gender:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 500; border-bottom: 1px solid #edf5ee;">{safe_gender}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Blood Group:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #b91c1c; font-weight: 700; border-bottom: 1px solid #edf5ee;">{safe_blood}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Ayurvedic Prakriti:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #15803d; font-weight: 600; border-bottom: 1px solid #edf5ee;">{safe_prakriti}</td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600;">Registration Date:</td>
                  <td style="padding: 10px 18px; font-size: 12.5px; color: #475569; font-weight: 500;">{safe_time}</td>
                </tr>
              </table>

              <!-- HIGHLIGHT FEATURES -->
              <h3 style="font-size: 15px; color: #173b2b; margin: 0 0 12px; font-weight: 700;">Explore Your Health Features:</h3>
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 26px;">
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #334155;">
                    <strong style="color: #2d7350;">🪪 Digital ABHA Health Card:</strong> Access your QR-coded national health credential anytime.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #334155;">
                    <strong style="color: #2d7350;">🌿 Prakriti Assessment:</strong> Discover your body constitution &amp; personalized dietary guidelines.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #334155;">
                    <strong style="color: #2d7350;">📅 Doctor Appointments:</strong> Book consultations with accredited AYUSH clinical specialists.
                  </td>
                </tr>
                <tr>
                  <td style="padding: 6px 0; font-size: 13px; color: #334155;">
                    <strong style="color: #2d7350;">📂 Digital Records:</strong> Track prescriptions, follow-up schedules, and Ayurvedic remedies.
                  </td>
                </tr>
              </table>

              <!-- ACTION BUTTON -->
              <div style="text-align: center; margin: 30px 0;">
                <a href="{portal_login_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2d7350; color: #ffffff; text-decoration: none; font-size: 14.5px; font-weight: 700; padding: 13px 32px; border-radius: 10px; box-shadow: 0 3px 10px rgba(45,115,80,0.3); letter-spacing: 0.2px;">
                  Login to Patient Portal &rarr;
                </a>
              </div>

              <!-- SECURITY NOTICE -->
              <div style="border-top: 1px solid #e2e8f0; padding-top: 18px; margin-top: 24px; font-size: 12px; color: #64748b;">
                <strong>Security Reminder:</strong> Never share your password or OTP. AYURCASE support will never contact you asking for your credentials.
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color: #f8faf8; padding: 22px 28px; text-align: center; font-size: 11.5px; color: #94a3b8; border-top: 1px solid #edf2ee;">
              <p style="margin: 0 0 6px;">AYURCASE Digital Clinical Ecosystem • Ministry of Ayush Standards • ABDM Compliant</p>
              <p style="margin: 0;">This is an automated confirmation email sent to {safe_email} upon registration.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "recipient": email_addr,
        "recipient_name": full_name,
        "abha_id": abha_id,
    }


def record_email_log(recipient, subject, email_type, status, details_dict, body_text, body_html, error_message=None):
    """Logs the email dispatch event to the SQLite email_logs table."""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS email_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                recipient TEXT NOT NULL,
                subject TEXT NOT NULL,
                email_type TEXT DEFAULT 'WELCOME_EMAIL',
                status TEXT DEFAULT 'SENT',
                details_json TEXT,
                body_text TEXT,
                body_html TEXT,
                error_message TEXT,
                sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        cursor.execute(
            """
            INSERT INTO email_logs (recipient, subject, email_type, status, details_json, body_text, body_html, error_message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (
                recipient,
                subject,
                email_type,
                status,
                json.dumps(details_dict or {}),
                body_text,
                body_html,
                error_message,
            ),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[EMAIL SERVICE] Database logging error: {e}")


def send_welcome_email(user_data, user_info=None):
    """
    Sends the welcome email to the newly created user account.
    If SMTP credentials are provided in .env, sends via live SMTP.
    Otherwise, simulates delivery locally and logs cleanly to console & database.
    """
    try:
        content = build_welcome_email_content(user_data, user_info)
        recipient = content["recipient"]

        if not recipient:
            print("[EMAIL SERVICE] No recipient email provided. Skipping welcome email.")
            return {"success": False, "error": "Missing recipient email"}

        cfg = get_smtp_config()
        details_summary = {
            "name": content["recipient_name"],
            "email": recipient,
            "abha_id": content["abha_id"],
            "phone": user_data.get("phone"),
            "age": user_data.get("age"),
            "gender": user_data.get("gender"),
            "blood_group": user_data.get("blood_group") or user_data.get("bloodGroup"),
            "prakriti": user_data.get("prakriti_primary") or user_data.get("prakriti") or "Not set",
        }

        # Case 1: SMTP credentials are configured in .env -> Real delivery
               # Send through Brevo HTTPS API
        if os.getenv("BREVO_API_KEY"):
            result = send_via_brevo(
                recipient=recipient,
                recipient_name=content["recipient_name"],
                subject=content["subject"],
                body_text=content["body_text"],
                body_html=content["body_html"]
            )

            if result["success"]:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="WELCOME_EMAIL",
                    status="SENT",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                )

                return result

            else:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="WELCOME_EMAIL",
                    status="FAILED",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                    error_message=result.get("error"),
                )

                return result
        # Case 2: Local development fallback (no SMTP credentials configured)
        else:
            print("\n" + "=" * 78)
            print(f"[AYURCASE EMAIL DISPATCH] Welcome Email to: {recipient}")
            print(f"Subject: {content['subject']}")
            print("-" * 78)
            print(f"Dear {content['recipient_name']}, welcome to AYURCASE!")
            print(f"ABHA ID:      {content['abha_id']}")
            print(f"Phone Number: {user_data.get('phone') or 'Not provided'}")
            print(f"Age / Gender: {user_data.get('age') or 'Not specified'} / {user_data.get('gender') or 'Not specified'}")
            print(f"Blood Group:  {user_data.get('blood_group') or user_data.get('bloodGroup') or 'Not recorded'}")
            print(f"Prakriti:     {user_data.get('prakriti_primary') or user_data.get('prakriti') or 'Not set'}")
            print("-" * 78)
            print("[NOTE] Logged to SQLite 'email_logs'. To send via live SMTP, configure SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD in .env")
            print("=" * 78 + "\n")

            record_email_log(
                recipient=recipient,
                subject=content["subject"],
                email_type="WELCOME_EMAIL",
                status="SIMULATED_LOCAL",
                details_dict=details_summary,
                body_text=content["body_text"],
                body_html=content["body_html"],
            )
            return {"success": True, "status": "SIMULATED_LOCAL", "recipient": recipient}

    except Exception as general_err:
        print(f"[EMAIL SERVICE] Unexpected error during email preparation: {general_err}")
        return {"success": False, "error": str(general_err)}


def send_welcome_email_async(user_data, user_info=None):
    """
    Dispatches the welcome email in a background daemon thread so the signup
    HTTP response returns immediately without blocking.
    """
    thread = threading.Thread(
        target=send_welcome_email,
        args=(user_data, user_info),
        daemon=True,
        name="AYURCASE-WelcomeEmail-Worker"
    )
    thread.start()
    return thread


def build_appointment_email_content(appointment_data, patient_data=None, doctor_data=None):
    """
    Constructs both plain text and rich HTML email contents for an appointment confirmation,
    including appointment timings, attending doctor, chamber address, contact numbers, and pre-visit tips.
    """
    patient_info = patient_data or {}
    doctor_info = doctor_data or {}

    apt_id = appointment_data.get("id") or appointment_data.get("appointment_id") or "APT"
    ref_code = f"APT-{str(apt_id).zfill(4)}" if str(apt_id).isdigit() else str(apt_id)

    patient_name = (
        appointment_data.get("patient_name")
        or patient_info.get("name")
        or patient_info.get("full_name")
        or "Valued Patient"
    ).strip()

    recipient_email = (
        appointment_data.get("patient_email")
        or appointment_data.get("email")
        or patient_info.get("email")
        or patient_info.get("username")
        or ""
    ).strip()

    patient_phone = (
        appointment_data.get("patient_phone")
        or appointment_data.get("phone")
        or patient_info.get("phone")
        or "Not provided"
    )

    abha_id = (
        appointment_data.get("patient_abha_id")
        or appointment_data.get("abha_id")
        or patient_info.get("abha_id")
        or patient_info.get("identifier")
        or "ABDM Verified"
    )

    doctor_name = (
        appointment_data.get("doctor_name")
        or doctor_info.get("full_name")
        or doctor_info.get("name")
        or "Attending Ayurvedic Practitioner"
    ).strip()

    doctor_spec = (
        doctor_info.get("specialization")
        or appointment_data.get("specialization")
        or "Ayurvedic Internal Medicine (Kayachikitsa)"
    ).strip()

    doctor_qual = (
        doctor_info.get("qualification")
        or appointment_data.get("qualification")
        or "BAMS, MD (Ayurveda)"
    ).strip()

    doctor_reg = (
        doctor_info.get("council_reg_no")
        or appointment_data.get("council_reg_no")
        or "AYUSH-WB-2024-REG"
    ).strip()

    apt_date_raw = appointment_data.get("appointment_date") or ""
    try:
        dt_obj = datetime.strptime(apt_date_raw, "%Y-%m-%d")
        formatted_date = dt_obj.strftime("%A, %d %B %Y")
    except Exception:
        formatted_date = apt_date_raw or "To be confirmed"

    apt_time = appointment_data.get("appointment_time") or "11:30 AM"
    consult_type = appointment_data.get("consultation_type") or "In-Clinic Consultation"
    symptoms_notes = (appointment_data.get("symptoms_notes") or appointment_data.get("notes") or "General Health & Wellness Review").strip()

    # Chamber and Clinic Contact Information
    chamber_name = os.getenv("CLINIC_NAME", "Vedacare Ayurveda Clinic & Wellness Centre").strip()
    chamber_address = os.getenv(
        "CLINIC_ADDRESS",
        "OPD Block, 4th Floor, 18/2 Gariahat Road, Ballygunge, Kolkata - 700019, West Bengal"
    ).strip()
    chamber_phone = os.getenv("CLINIC_PHONE", "+91 98300 12345").strip()
    chamber_whatsapp = os.getenv("CLINIC_WHATSAPP", "+91 98300 12345").strip()
    chamber_email = os.getenv("CLINIC_EMAIL", "care@ayurcase.com").strip()
    chamber_hours = os.getenv(
        "CLINIC_HOURS",
        "Monday to Saturday: 09:00 AM – 07:30 PM | Sunday: 10:00 AM – 02:00 PM"
    ).strip()

    portal_url = os.getenv(
        "PATIENT_PORTAL_URL",
        "https://ayurcase-u601.onrender.com/patient-dashboard.html"
    ).strip()

    subject = f"Confirmed: Consultation with {doctor_name} on {formatted_date} [{apt_time}]"

    # Plain text version
    body_text = f"""Welcome to AYURCASE - Consultation Appointment Confirmation
================================================================================

Dear {patient_name},

Your consultation appointment has been successfully scheduled and CONFIRMED.
Below are the complete details of your booking along with the chamber's address and contact information.

APPOINTMENT SUMMARY:
--------------------------------------------------------------------------------
- Booking Reference:    #{ref_code}
- Status:               CONFIRMED
- Attending Doctor:     {doctor_name}
- Department:           {doctor_spec}
- Qualifications:       {doctor_qual} (Reg: {doctor_reg})
- Appointment Date:     {formatted_date}
- Time Slot:            {apt_time}
- Consultation Mode:    {consult_type}
- Patient Name:         {patient_name}
- ABHA Health ID:       {abha_id}
- Reason for Visit:     {symptoms_notes}
--------------------------------------------------------------------------------

CHAMBER LOCATION & CONTACT INFORMATION:
--------------------------------------------------------------------------------
- Chamber / Clinic:     {chamber_name}
- Address:              {chamber_address}
- Reception & Booking:  {chamber_phone}
- WhatsApp Desk:        {chamber_whatsapp}
- Official Email:       {chamber_email}
- Visiting Hours:       {chamber_hours}
--------------------------------------------------------------------------------

PRE-CONSULTATION INSTRUCTIONS:
1. Please arrive at the chamber 15 minutes before your scheduled appointment time.
2. Please bring any prior medical records, prescriptions, or laboratory reports.
3. For Nadi Pariksha (Pulse Diagnosis), having a light meal 2 to 3 hours prior is recommended.

PATIENT DASHBOARD:
You can review, manage, or reschedule your appointment in your dashboard at:
{portal_url}

Warm regards,
{chamber_name} & The AYURCASE Healthcare Team
National Digital Ayush Health Platform • ABDM Compliant
"""

    # Escaped safe HTML strings
    safe_patient_name = html.escape(patient_name)
    safe_doctor_name = html.escape(doctor_name)
    safe_doctor_spec = html.escape(doctor_spec)
    safe_doctor_qual = html.escape(doctor_qual)
    safe_doctor_reg = html.escape(doctor_reg)
    safe_date = html.escape(formatted_date)
    safe_time = html.escape(apt_time)
    safe_mode = html.escape(consult_type)
    safe_notes = html.escape(symptoms_notes)
    safe_ref = html.escape(ref_code)
    safe_abha = html.escape(str(abha_id))
    safe_chamber_name = html.escape(chamber_name)
    safe_chamber_address = html.escape(chamber_address)
    safe_chamber_phone = html.escape(chamber_phone)
    safe_chamber_whatsapp = html.escape(chamber_whatsapp)
    safe_chamber_email = html.escape(chamber_email)
    safe_chamber_hours = html.escape(chamber_hours)
    safe_recipient = html.escape(recipient_email)
    wa_clean = "".join(filter(str.isdigit, chamber_whatsapp))

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Appointment Confirmed - AYURCASE</title>
</head>
<body style="margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #f1f5f3; color: #1e293b; line-height: 1.6;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f1f5f3; padding: 30px 10px;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" style="max-width: 640px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2e8f0;" cellspacing="0" cellpadding="0" border="0">
          
          <!-- BRAND HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #1b4d36 0%, #2d7350 100%); padding: 30px 26px; text-align: center; color: #ffffff;">
              <div style="display: inline-block; width: 50px; height: 50px; line-height: 50px; border-radius: 12px; background: rgba(255,255,255,0.18); font-size: 24px; margin-bottom: 10px;">🌿</div>
              <h1 style="margin: 0; font-size: 24px; font-weight: 700; letter-spacing: 0.5px; color: #ffffff;">AYURCASE</h1>
              <p style="margin: 5px 0 0; font-size: 13px; color: #d1fae5; font-weight: 500;">National Digital Ayush Health Platform • ABDM Compliant</p>
            </td>
          </tr>

          <!-- MAIN CONTENT -->
          <tr>
            <td style="padding: 30px 26px;">
              
              <!-- CONFIRMATION BANNER -->
              <div style="background-color: #e8f5ec; border-left: 4px solid #2d7350; border-radius: 8px; padding: 16px 18px; margin-bottom: 24px;">
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                  <tr>
                    <td style="vertical-align: middle;">
                      <h2 style="margin: 0 0 4px; font-size: 18px; color: #173b2b; font-weight: 700;">✅ Consultation Confirmed!</h2>
                      <p style="margin: 0; font-size: 13.5px; color: #2d553e;">Dear <strong>{safe_patient_name}</strong>, your appointment with <strong>{safe_doctor_name}</strong> has been successfully confirmed.</p>
                    </td>
                  </tr>
                </table>
              </div>

              <!-- APPOINTMENT DETAILS CARD -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #f8faf8; border: 1px solid #dcf0e2; border-radius: 12px; margin-bottom: 24px; overflow: hidden;">
                <tr>
                  <td colspan="2" style="background-color: #e1f1e6; padding: 12px 18px; font-size: 13px; font-weight: 700; color: #173b2b; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #dcf0e2;">
                    📅 Appointment Schedule &amp; Practitioner
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; width: 38%; border-bottom: 1px solid #edf5ee;">Reference ID:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 700; font-family: monospace; border-bottom: 1px solid #edf5ee;">
                    <span style="background-color: #e2e8f0; color: #1e293b; padding: 3px 8px; border-radius: 6px;">#{safe_ref}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Attending Doctor:</td>
                  <td style="padding: 10px 18px; font-size: 13.5px; color: #1b4d36; font-weight: 700; border-bottom: 1px solid #edf5ee;">
                    {safe_doctor_name}
                    <div style="font-size: 12px; font-weight: 500; color: #64748b; margin-top: 2px;">{safe_doctor_spec} • {safe_doctor_qual} (Reg: {safe_doctor_reg})</div>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Date &amp; Time:</td>
                  <td style="padding: 10px 18px; font-size: 13.5px; color: #0f172a; font-weight: 700; border-bottom: 1px solid #edf5ee;">
                    <span style="color: #2d7350;">{safe_date}</span> at <strong>{safe_time}</strong>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Consultation Mode:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #edf5ee;">
                    <span style="background-color: #dbeafe; color: #1e40af; padding: 3px 8px; border-radius: 6px; font-size: 12px;">{safe_mode}</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Patient Name &amp; ABHA:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #edf5ee;">
                    {safe_patient_name} <span style="font-size: 11.5px; color: #059669; font-weight: 600;">({safe_abha})</span>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #edf5ee;">Reason / Symptoms:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #334155; font-style: italic; border-bottom: 1px solid #edf5ee;">
                    "{safe_notes}"
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600;">Status:</td>
                  <td style="padding: 10px 18px; font-size: 12.5px; font-weight: 700; color: #065f46;">
                    <span style="background-color: #d1fae5; color: #065f46; padding: 3px 9px; border-radius: 6px;">CONFIRMED</span>
                  </td>
                </tr>
              </table>

              <!-- CHAMBER ADDRESS & CONTACT INFO CARD -->
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #fcfbf7; border: 1px solid #e7dfce; border-radius: 12px; margin-bottom: 24px; overflow: hidden;">
                <tr>
                  <td colspan="2" style="background-color: #f3ece0; padding: 12px 18px; font-size: 13px; font-weight: 700; color: #5a421f; text-transform: uppercase; letter-spacing: 0.5px; border-bottom: 1px solid #e7dfce;">
                    🏥 Chamber Address &amp; Contact Info
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600; width: 38%; border-bottom: 1px solid #f2ece2;">Facility Name:</td>
                  <td style="padding: 10px 18px; font-size: 13.5px; color: #2d1d06; font-weight: 700; border-bottom: 1px solid #f2ece2;">
                    {safe_chamber_name}
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600; border-bottom: 1px solid #f2ece2;">Chamber Address:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #2d1d06; font-weight: 500; line-height: 1.5; border-bottom: 1px solid #f2ece2;">
                    📍 {safe_chamber_address}
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600; border-bottom: 1px solid #f2ece2;">Chamber Phone:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #2d1d06; font-weight: 700; border-bottom: 1px solid #f2ece2;">
                    📞 <a href="tel:{safe_chamber_phone}" style="color: #2d7350; text-decoration: none;">{safe_chamber_phone}</a>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600; border-bottom: 1px solid #f2ece2;">WhatsApp Desk:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #2d1d06; font-weight: 700; border-bottom: 1px solid #f2ece2;">
                    💬 <a href="https://wa.me/{wa_clean}" target="_blank" rel="noopener noreferrer" style="color: #15803d; text-decoration: none;">{safe_chamber_whatsapp}</a>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600; border-bottom: 1px solid #f2ece2;">Official Email:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #2d1d06; font-weight: 500; border-bottom: 1px solid #f2ece2;">
                    ✉️ <a href="mailto:{safe_chamber_email}" style="color: #2d7350; text-decoration: none;">{safe_chamber_email}</a>
                  </td>
                </tr>

                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #78654c; font-weight: 600;">Visiting Hours:</td>
                  <td style="padding: 10px 18px; font-size: 12.5px; color: #475569; font-weight: 500;">
                    🕒 {safe_chamber_hours}
                  </td>
                </tr>
              </table>

              <!-- PRE-CONSULTATION INSTRUCTIONS -->
              <div style="background-color: #f1f8f4; border-radius: 10px; padding: 16px 18px; margin-bottom: 26px; border: 1px solid #d4ebd9;">
                <h3 style="margin: 0 0 8px; font-size: 13.5px; color: #173b2b; font-weight: 700;">💡 Important Pre-Consultation Instructions:</h3>
                <ul style="margin: 0; padding-left: 20px; font-size: 12.5px; color: #334155;">
                  <li style="margin-bottom: 4px;">Please arrive at the chamber <strong>15 minutes prior</strong> to your scheduled slot.</li>
                  <li style="margin-bottom: 4px;">Carry all prior medical reports, prescription records, or lab investigation results.</li>
                  <li style="margin-bottom: 0;">For Ayurvedic <em>Nadi Pariksha</em> (Pulse Examination), an empty stomach or a light meal taken 2-3 hours prior yields the most accurate readings.</li>
                </ul>
              </div>

              <!-- ACTION BUTTON -->
              <div style="text-align: center; margin: 28px 0;">
                <a href="{portal_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background-color: #2d7350; color: #ffffff; text-decoration: none; font-size: 14.5px; font-weight: 700; padding: 13px 32px; border-radius: 10px; box-shadow: 0 3px 10px rgba(45,115,80,0.3); letter-spacing: 0.2px;">
                  View in Patient Dashboard &rarr;
                </a>
              </div>

              <!-- SECURITY NOTICE -->
              <div style="border-top: 1px solid #e2e8f0; padding-top: 16px; margin-top: 24px; font-size: 11.5px; color: #64748b;">
                <strong>Notice:</strong> If you need to reschedule or cancel your appointment, please contact the chamber reception at least 4 hours in advance.
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color: #f8faf8; padding: 22px 26px; text-align: center; font-size: 11.5px; color: #94a3b8; border-top: 1px solid #edf2ee;">
              <p style="margin: 0 0 4px;">{safe_chamber_name} • Powered by AYURCASE Digital Health</p>
              <p style="margin: 0;">Automated appointment notification sent to {safe_recipient}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "recipient": recipient_email,
        "recipient_name": patient_name,
        "ref_code": ref_code,
        "doctor_name": doctor_name,
        "date": formatted_date,
        "time": apt_time,
    }


def send_appointment_confirmation_email(appointment_data, patient_data=None, doctor_data=None):
    """
    Sends an appointment confirmation email to the patient.
    If SMTP credentials are configured in .env, sends via live SMTP.
    Otherwise, logs locally to console and SQLite email_logs.
    """
    try:
        content = build_appointment_email_content(appointment_data, patient_data, doctor_data)
        recipient = content["recipient"]

        if not recipient:
            print("[EMAIL SERVICE] No recipient email found for appointment confirmation. Skipping.")
            return {"success": False, "error": "Missing recipient email"}

        cfg = get_smtp_config()
        details_summary = {
            "appointment_id": appointment_data.get("id") or appointment_data.get("appointment_id"),
            "ref_code": content["ref_code"],
            "patient_name": content["recipient_name"],
            "recipient_email": recipient,
            "doctor_name": content["doctor_name"],
            "appointment_date": content["date"],
            "appointment_time": content["time"],
            "consultation_type": appointment_data.get("consultation_type"),
            "status": "Confirmed",
        }

        # Case 1: SMTP credentials are configured -> Real delivery
               # Send through Brevo HTTPS API
        if os.getenv("BREVO_API_KEY"):
            result = send_via_brevo(
                recipient=recipient,
                recipient_name=content["recipient_name"],
                subject=content["subject"],
                body_text=content["body_text"],
                body_html=content["body_html"]
            )

            if result["success"]:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="APPOINTMENT_CONFIRMATION",
                    status="SENT",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                )

                return result

            else:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="APPOINTMENT_CONFIRMATION",
                    status="FAILED",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                    error_message=result.get("error"),
                )

                return result
        # Case 2: Local development fallback
        else:
            print("\n" + "=" * 78)
            print(f"[AYURCASE EMAIL DISPATCH] Appointment Confirmation to: {recipient}")
            print(f"Subject: {content['subject']}")
            print("-" * 78)
            print(f"Doctor:       {content['doctor_name']}")
            print(f"Date & Time:  {content['date']} at {content['time']}")
            print(f"Patient:      {content['recipient_name']}")
            print(f"Chamber:      Vedacare Ayurveda Clinic & Wellness Centre")
            print("=" * 78 + "\n")

            record_email_log(
                recipient=recipient,
                subject=content["subject"],
                email_type="APPOINTMENT_CONFIRMATION",
                status="SIMULATED_LOCAL",
                details_dict=details_summary,
                body_text=content["body_text"],
                body_html=content["body_html"],
            )
            return {"success": True, "status": "SIMULATED_LOCAL", "recipient": recipient}

    except Exception as general_err:
        print(f"[EMAIL SERVICE] Unexpected error during appointment email dispatch: {general_err}")
        return {"success": False, "error": str(general_err)}


def send_appointment_confirmation_email_async(appointment_data, patient_data=None, doctor_data=None):
    """
    Dispatches appointment confirmation email in a background daemon thread so the
    scheduling response returns immediately without UI lag.
    """
    thread = threading.Thread(
        target=send_appointment_confirmation_email,
        args=(appointment_data, patient_data, doctor_data),
        daemon=True,
        name="AYURCASE-AppointmentEmail-Worker"
    )
    thread.start()
    return thread


# ==============================================================================
# 3. ACCOUNT DELETION CONFIRMATION EMAIL
# ==============================================================================

def build_account_deletion_email_content(user_data):
    """
    Constructs both plain text and rich HTML email contents confirming
    that the patient's account has been permanently deleted and all
    associated clinical data and session records have been purged.
    """
    full_name = (
        user_data.get("name")
        or user_data.get("full_name")
        or user_data.get("patient_name")
        or "Valued Patient"
    ).strip()

    recipient_email = (
        user_data.get("email")
        or user_data.get("username")
        or user_data.get("identifier")
        or ""
    ).strip()

    abha_id = (
        user_data.get("abha_id")
        or user_data.get("abhaId")
        or "ABHA Record"
    ).strip()

    deletion_date = datetime.now().strftime("%A, %d %B %Y, %I:%M %p")

    clinic_name = os.getenv("CLINIC_NAME", "Vedacare Ayurveda Clinic & Wellness Centre").strip()
    clinic_phone = os.getenv("CLINIC_PHONE", "+91 98300 12345").strip()
    clinic_email = os.getenv("CLINIC_EMAIL", "care@ayurcase.com").strip()
    signup_url = os.getenv(
        "PATIENT_SIGNUP_URL",
        "https://ayurcase-u601.onrender.com/signup-patient.html"
    ).strip()

    subject = f"AYURCASE - Account Deletion & Data Removal Confirmation [ABHA: {abha_id}]"

    safe_name = html.escape(full_name)
    safe_email = html.escape(recipient_email)
    safe_abha = html.escape(abha_id)
    safe_date = html.escape(deletion_date)
    safe_clinic_name = html.escape(clinic_name)
    safe_clinic_phone = html.escape(clinic_phone)
    safe_clinic_email = html.escape(clinic_email)
    safe_signup_url = html.escape(signup_url)

    body_text = f"""AYURCASE - National Digital Ayush Health Platform
Account Deletion & Permanent Data Removal Confirmation
================================================================================

Dear {full_name},

This email confirms that your AYURCASE patient account associated with {recipient_email} has been permanently deleted upon your request on {deletion_date}.

CONFIRMATION OF PERMANENT DATA PURGE:
--------------------------------------------------------------------------------
- Account Status:        PERMANENTLY CLOSED & REMOVED
- Primary Email:         {recipient_email}
- Linked ABHA ID:        {abha_id} (Purged from active records)
- Personal Profile:      Permanently Erased
- Active Prescriptions:  Purged
- Consultations & Cases: Purged
- Security Sessions:     All active tokens revoked & cleared
- Deletion Timestamp:    {deletion_date}
--------------------------------------------------------------------------------

DATA PRIVACY & COMPLIANCE (DPDP & ABDM):
In strict compliance with India's Digital Personal Data Protection (DPDP) Act and Ayushman Bharat Digital Mission (ABDM) guidelines, your personal credentials, profile details, and linked clinical records have been purged from our active operational databases.

DID NOT REQUEST THIS?
If you did not initiate this account deletion, please contact our administrative desk immediately at:
- Phone: {clinic_phone}
- Email: {clinic_email}

WANT TO REJOIN IN THE FUTURE?
You are always welcome back. Should you need Ayurvedic healthcare or clinical consultations in the future, you can register a new account anytime at:
{signup_url}

Thank you for having chosen AYURCASE. We wish you enduring health and wellness.

Warm regards,
The AYURCASE Digital Health Team
{clinic_name}
================================================================================
Automated account closure notice sent to {recipient_email}.
"""

    body_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AYURCASE Account Deletion Confirmation</title>
</head>
<body style="margin: 0; padding: 0; background-color: #f4f7f5; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #1e293b;">
  <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f4f7f5; padding: 30px 12px;">
    <tr>
      <td align="center">
        <table width="100%" border="0" cellspacing="0" cellpadding="0" style="max-width: 620px; background-color: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.06); border: 1px solid #e2ece6;">
          
          <!-- HEADER -->
          <tr>
            <td style="background: linear-gradient(135deg, #1b4d36 0%, #2d7350 100%); padding: 30px 32px; text-align: center; color: #ffffff;">
              <table width="100%" border="0" cellspacing="0" cellpadding="0">
                <tr>
                  <td align="center">
                    <div style="display: inline-block; background: rgba(255, 255, 255, 0.15); padding: 7px 16px; border-radius: 30px; font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; border: 1px solid rgba(255, 255, 255, 0.25);">
                      Ayushman Bharat Digital Mission (ABDM)
                    </div>
                    <h1 style="margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px; color: #ffffff;">AYURCASE</h1>
                    <p style="margin: 6px 0 0; font-size: 13.5px; color: #d4ebd9; font-weight: 500;">National Digital Ayush Health Platform</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>

          <!-- BODY CONTENT -->
          <tr>
            <td style="padding: 32px 32px 24px;">
              
              <!-- WARNING & NOTICE BADGE -->
              <div style="background-color: #fff1f2; border: 1.5px solid #fecdd3; border-radius: 12px; padding: 18px 22px; margin-bottom: 26px;">
                <table width="100%" border="0" cellspacing="0" cellpadding="0">
                  <tr>
                    <td width="42" valign="top">
                      <div style="width: 36px; height: 36px; background-color: #ffe4e6; border-radius: 50%; text-align: center; line-height: 36px; font-size: 18px;">
                        🗑️
                      </div>
                    </td>
                    <td style="padding-left: 10px;">
                      <h3 style="margin: 0 0 4px; font-size: 15px; color: #be123c; font-weight: 700;">Account Permanently Deleted</h3>
                      <p style="margin: 0; font-size: 12.5px; color: #881337; line-height: 1.5;">
                        Your patient profile, ABHA credentials on file, and associated clinical data have been permanently removed from our active databases.
                      </p>
                    </td>
                  </tr>
                </table>
              </div>

              <!-- GREETING -->
              <h2 style="margin: 0 0 12px; font-size: 18px; color: #0f172a; font-weight: 700;">Dear {safe_name},</h2>
              <p style="margin: 0 0 22px; font-size: 14px; line-height: 1.6; color: #334155;">
                This email serves as official confirmation that your <strong>AYURCASE</strong> patient account registered under <strong>{safe_email}</strong> was permanently deleted upon your request on <strong>{safe_date}</strong>.
              </p>

              <!-- PURGE SUMMARY TABLE -->
              <table width="100%" border="0" cellspacing="0" cellpadding="0" style="background-color: #f8faf9; border: 1px solid #e2ece6; border-radius: 12px; overflow: hidden; margin-bottom: 26px;">
                <tr style="background-color: #eef5f0; border-bottom: 1px solid #d9e8dd;">
                  <td colspan="2" style="padding: 12px 18px; font-size: 12px; font-weight: 700; color: #1e5a38; text-transform: uppercase; letter-spacing: 0.6px;">
                    📋 Account Closure & Purge Summary
                  </td>
                </tr>
                <tr>
                  <td width="38%" style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Account Status:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #be123c; font-weight: 700; border-bottom: 1px solid #eef2ef;">
                    <span style="display: inline-block; background-color: #ffe4e6; color: #be123c; padding: 2px 10px; border-radius: 6px; font-size: 11.5px; border: 1px solid #fecdd3;">PERMANENTLY CLOSED</span>
                  </td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Primary Email:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #eef2ef;">{safe_email}</td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Linked ABHA ID:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #eef2ef;">{safe_abha} <span style="font-size: 11px; color: #64748b;">(De-linked)</span></td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Personal Profile:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #eef2ef;">Permanently Erased</td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Prescriptions & Cases:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #eef2ef;">Purged from Active Records</td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600; border-bottom: 1px solid #eef2ef;">Active Sessions:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #0f172a; font-weight: 600; border-bottom: 1px solid #eef2ef;">Revoked & Cleared</td>
                </tr>
                <tr>
                  <td style="padding: 10px 18px; font-size: 13px; color: #64748b; font-weight: 600;">Closure Timestamp:</td>
                  <td style="padding: 10px 18px; font-size: 13px; color: #475569; font-weight: 500;">{safe_date}</td>
                </tr>
              </table>

              <!-- COMPLIANCE & PRIVACY NOTE -->
              <div style="background-color: #f8fafc; border-radius: 10px; padding: 14px 18px; margin-bottom: 24px; border: 1px solid #e2e8f0; font-size: 12px; color: #475569; line-height: 1.55;">
                <strong style="color: #0f172a;">🔒 Data Privacy & Compliance:</strong> Under the Digital Personal Data Protection (DPDP) standards and Ayushman Bharat Digital Mission guidelines, all personal health records, identifiers, and session tokens have been completely purged from our active operational databases.
              </div>

              <!-- DID NOT REQUEST THIS? -->
              <div style="background-color: #fffbeb; border: 1px solid #fef3c7; border-radius: 10px; padding: 14px 18px; margin-bottom: 26px; font-size: 12.5px; color: #78350f; line-height: 1.55;">
                <strong style="color: #92400e;">⚠️ Did not request this?</strong> If this account was deleted by mistake or without your authorization, please immediately contact our administrative desk:
                <div style="margin-top: 6px;">
                  📞 <strong>Phone:</strong> {safe_clinic_phone} &nbsp;|&nbsp; ✉️ <strong>Email:</strong> <a href="mailto:{safe_clinic_email}" style="color: #2d7350; text-decoration: none;">{safe_clinic_email}</a>
                </div>
              </div>

              <!-- RE-REGISTER CTA -->
              <div style="text-align: center; margin: 28px 0 10px;">
                <p style="margin: 0 0 14px; font-size: 13px; color: #64748b;">Should you need Ayurvedic clinical care or consultations in the future, you are always welcome back:</p>
                <a href="{safe_signup_url}" target="_blank" rel="noopener noreferrer" style="display: inline-block; background: linear-gradient(135deg, #2d7350 0%, #1b4d36 100%); color: #ffffff; text-decoration: none; font-size: 14px; font-weight: 700; padding: 13px 30px; border-radius: 10px; box-shadow: 0 4px 14px rgba(45,115,80,0.3); letter-spacing: 0.2px;">
                  Register New Account &rarr;
                </a>
              </div>
            </td>
          </tr>

          <!-- FOOTER -->
          <tr>
            <td style="background-color: #f8faf8; padding: 22px 28px; text-align: center; font-size: 11.5px; color: #94a3b8; border-top: 1px solid #edf2ee;">
              <p style="margin: 0 0 4px; font-weight: 600; color: #64748b;">{safe_clinic_name} • AYURCASE Digital Health Platform</p>
              <p style="margin: 0;">Automated account closure notification sent to {safe_email}.</p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>
"""

    return {
        "subject": subject,
        "body_text": body_text,
        "body_html": body_html,
        "recipient": recipient_email,
        "recipient_name": full_name,
        "abha_id": abha_id,
        "deletion_date": deletion_date
    }


def send_account_deletion_email(user_data):
    """
    Sends an account deletion confirmation email to the user.
    If SMTP credentials are configured in .env, sends via live SMTP.
    Otherwise, logs locally to console and SQLite email_logs table.
    """
    try:
        content = build_account_deletion_email_content(user_data)
        recipient = content["recipient"]

        if not recipient:
            print("[EMAIL SERVICE] No recipient email found for account deletion. Skipping.")
            return {"success": False, "error": "Missing recipient email"}

        cfg = get_smtp_config()
        details_summary = {
            "recipient_name": content["recipient_name"],
            "recipient_email": recipient,
            "abha_id": content["abha_id"],
            "deletion_date": content["deletion_date"],
            "action": "ACCOUNT_DELETED",
            "status": "CLOSED"
        }

        # Case 1: SMTP credentials are configured -> Real delivery
                # Send through Brevo HTTPS API
        if os.getenv("BREVO_API_KEY"):
            result = send_via_brevo(
                recipient=recipient,
                recipient_name=content["recipient_name"],
                subject=content["subject"],
                body_text=content["body_text"],
                body_html=content["body_html"]
            )

            if result["success"]:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="ACCOUNT_DELETION",
                    status="SENT",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                )

                return result

            else:
                record_email_log(
                    recipient=recipient,
                    subject=content["subject"],
                    email_type="ACCOUNT_DELETION",
                    status="FAILED",
                    details_dict=details_summary,
                    body_text=content["body_text"],
                    body_html=content["body_html"],
                    error_message=result.get("error"),
                )

                return result
        # Case 2: Local development fallback
        else:
            print("\n" + "=" * 78)
            print(f"[AYURCASE EMAIL DISPATCH] Account Deletion Confirmation to: {recipient}")
            print(f"Subject: {content['subject']}")
            print("-" * 78)
            print(f"Patient:       {content['recipient_name']}")
            print(f"ABHA ID:       {content['abha_id']}")
            print(f"Date & Time:   {content['deletion_date']}")
            print(f"Account:       Permanently Closed & Purged")
            print("=" * 78 + "\n")

            record_email_log(
                recipient=recipient,
                subject=content["subject"],
                email_type="ACCOUNT_DELETION",
                status="SIMULATED_LOCAL",
                details_dict=details_summary,
                body_text=content["body_text"],
                body_html=content["body_html"],
            )
            return {"success": True, "status": "SIMULATED_LOCAL", "recipient": recipient}

    except Exception as general_err:
        print(f"[EMAIL SERVICE] Unexpected error during deletion email dispatch: {general_err}")
        return {"success": False, "error": str(general_err)}


def send_account_deletion_email_async(user_data):
    """
    Dispatches the account deletion confirmation email in a background daemon thread
    so the API response returns immediately without latency.
    """
    thread = threading.Thread(
        target=send_account_deletion_email,
        args=(user_data,),
        daemon=True,
        name="AYURCASE-AccountDeletionEmail-Worker"
    )
    thread.start()
    return thread

