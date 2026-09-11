import os
import sys
from datetime import date

from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv
from google import genai

# Add backend directory to sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.insert(0, CURRENT_DIR)

try:
    from backend.database import (
        init_db,
        authenticate_user,
        register_patient,
        get_all_cases,
        add_case,
        delete_case,
        sync_cases_batch,
        get_patient_data,
        update_patient_profile,
        delete_patient_account,
        get_admin_summary,
        get_admin_doctor_patients,
        get_doctor_dashboard,
        get_doctors_list,
        create_appointment,
        get_appointments,
        delete_appointment,
        cancel_appointment_by_patient_name,
        save_storage_key,
        get_storage_key,
        get_all_storage,
        sync_storage_batch,
        save_user_preference,
        get_user_preferences,
        save_study_progress,
        get_study_progress,
        create_user_session,
        validate_user_session,
        delete_user_session,
        add_notice,
        get_notices,
        delete_notice,
        add_notice_comment,
        get_notice_comments,
        get_recent_history,
        get_hospital_patient_inflow,
        update_patient_case_record,
        merge_patient_records,
        deactivate_patient_record,
        reassign_patient_doctor,
        add_doctor_record,
        update_doctor_record,
        remove_doctor_record,
        get_emergency_cases,
        get_all_registered_patients,
        save_followup_prescription,
        get_patient_prescriptions,
        add_emergency_case,
        add_article,
        get_all_articles,
        add_lab_report,
        get_patient_lab_reports,
        get_all_lab_reports,
        add_ai_review,
        get_all_ai_reviews,
        add_upcoming_patient_ai_query,
        update_patient_name_everywhere,
    )
except ImportError:
    from database import (
        init_db,
        authenticate_user,
        register_patient,
        get_all_cases,
        add_case,
        delete_case,
        sync_cases_batch,
        get_patient_data,
        update_patient_profile,
        delete_patient_account,
        get_admin_summary,
        get_admin_doctor_patients,
        get_doctor_dashboard,
        get_doctors_list,
        create_appointment,
        get_appointments,
        delete_appointment,
        cancel_appointment_by_patient_name,
        save_storage_key,
        get_storage_key,
        get_all_storage,
        sync_storage_batch,
        save_user_preference,
        get_user_preferences,
        save_study_progress,
        get_study_progress,
        create_user_session,
        validate_user_session,
        delete_user_session,
        add_notice,
        get_notices,
        delete_notice,
        add_notice_comment,
        get_notice_comments,
        get_recent_history,
        get_hospital_patient_inflow,
        update_patient_case_record,
        merge_patient_records,
        deactivate_patient_record,
        reassign_patient_doctor,
        add_doctor_record,
        update_doctor_record,
        remove_doctor_record,
        get_emergency_cases,
        get_all_registered_patients,
        save_followup_prescription,
        get_patient_prescriptions,
        add_emergency_case,
        add_article,
        get_all_articles,
        add_lab_report,
        get_patient_lab_reports,
        get_all_lab_reports,
        add_ai_review,
        get_all_ai_reviews,
        add_upcoming_patient_ai_query,
        update_patient_name_everywhere,
    )


load_dotenv()

app = Flask(__name__)
CORS(app)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Initialize database on startup
init_db()

DEFAULT_GEMINI_MODEL = "gemini-3.6-flash"
MAX_ASSISTANT_QUESTION_LENGTH = 4000
_gemini_client = None
_gemini_client_key = None


def get_gemini_client():
    """Return a configured Gemini client only when this deployment has a key."""
    global _gemini_client, _gemini_client_key

    api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
    if not api_key:
        return None

    if _gemini_client is None or _gemini_client_key != api_key:
        _gemini_client = genai.Client(api_key=api_key)
        _gemini_client_key = api_key

    return _gemini_client


def get_gemini_model():
    return (os.getenv("GEMINI_MODEL") or DEFAULT_GEMINI_MODEL).strip()


def assistant_fallback(question):
    """Give the chat UI a helpful reply when the provider cannot respond."""
    normalized = question.lower()

    if any(term in normalized for term in ("chest pain", "difficulty breathing", "suicid", "unconscious", "severe bleeding")):
        return (
            "Your message may describe an emergency. Please contact local emergency "
            "services or seek urgent medical care now."
        )

    if any(term in normalized for term in ("appointment", "book", "consultation")):
        return (
            "I received your appointment question. In AYURCASE, open the appointment "
            "section, select an available practitioner, choose a date and time, then "
            "confirm the booking. The live AI service is temporarily unavailable, so "
            "please try your question again shortly for more specific help."
        )

    if "abha" in normalized or "profile" in normalized:
        return (
            "I received your profile question. You can review your Digital ABHA Health "
            "Card and profile from the patient dashboard. The live AI service is "
            "temporarily unavailable, so please try again shortly for more specific help."
        )

    return (
        "I received your question. The live AI service is temporarily unavailable, "
        "but your message was not lost. Please try again shortly. For urgent health "
        "concerns, contact a qualified clinician or local emergency services."
    )


# =====================================================
# AUTHENTICATION & USER APIS
# =====================================================

@app.route("/api/auth/login", methods=["POST"])
def api_login():
    """Authenticates users (Doctor, Patient, Admin) against SQLite database with cryptographic password verification."""
    data = request.json or {}
    username = data.get("username")
    password = data.get("password")
    role = data.get("role")
    selected_doctor_username = (data.get("selected_doctor_username") or "").strip()

    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username/Identifier and password are required."
        }), 400

    user = authenticate_user(username, password, role)
    if not user:
        return jsonify({
            "success": False,
            "error": "Invalid credentials or unauthorized role access."
        }), 401

    if role == "doctor":
        if not selected_doctor_username:
            return jsonify({
                "success": False,
                "error": "Select the practitioner account before signing in."
            }), 400
        if user["username"].casefold() != selected_doctor_username.casefold():
            return jsonify({
                "success": False,
                "error": "The selected practitioner does not match these credentials."
            }), 401

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user['full_name']}!",
        "user": user
    })


@app.route("/api/auth/register-patient", methods=["POST"])
def api_register_patient():
    """Registers a new patient with credentials and demographic profile in SQLite."""
    data = request.json or {}
    result = register_patient(data)
    if not result.get("success"):
        return jsonify(result), 400
    return jsonify(result), 201


# =====================================================
# CLINICAL CASES & PATIENT APIS (SQLite Persisted)
# =====================================================

@app.route("/api/cases", methods=["GET", "POST"])
def api_cases():
    """Fetches all cases or adds a new case to SQLite database."""
    if request.method == "POST":
        data = request.json or {}
        if not data.get("name") and not data.get("patient_name"):
            return jsonify({"success": False, "error": "Patient name is required."}), 400

        try:
            new_case = add_case(data)
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        return jsonify({
            "success": True,
            "case": new_case,
            "id": new_case["id"],
            "message": f"Case for {new_case['name']} successfully recorded in SQLite database."
        }), 201

    cases = get_all_cases(request.args.get("doctor_id"))
    return jsonify({
        "success": True,
        "cases": cases
    })


@app.route("/api/cases/<identifier>", methods=["DELETE"])
def api_delete_case(identifier):
    """Deletes a clinical case from SQLite database by ID or patient name."""
    deleted = delete_case(identifier)
    if not deleted:
        return jsonify({"success": False, "error": f"Case '{identifier}' not found."}), 404
    return jsonify({
        "success": True,
        "message": f"Case '{identifier}' successfully deleted from database."
    })


@app.route("/api/cases/sync", methods=["POST"])
def api_sync_cases():
    """Batch synchronizes cases from frontend into SQLite database."""
    data = request.json or {}
    cases_list = data.get("cases") or []
    synced_cases = sync_cases_batch(cases_list, data.get("doctor_id"))
    return jsonify({
        "success": True,
        "cases": synced_cases,
        "count": len(synced_cases),
        "message": "Cases successfully synchronized with SQLite database."
    })


# =====================================================
# UNIVERSAL APP STORAGE APIS (Moving LocalStorage to SQLite)
# =====================================================

@app.route("/api/storage/all", methods=["GET"])
def api_storage_all():
    """Returns all key-value state stored in SQLite database."""
    storage = get_all_storage()
    return jsonify({
        "success": True,
        "storage": storage
    })


@app.route("/api/storage/<key>", methods=["GET", "POST"])
def api_storage_key(key):
    """Retrieves or saves a single storage key in SQLite database."""
    if request.method == "POST":
        data = request.json or {}
        val = data.get("value")
        save_storage_key(key, val)
        return jsonify({
            "success": True,
            "message": f"Key '{key}' successfully saved to SQLite database."
        })

    val = get_storage_key(key)
    return jsonify({
        "success": True,
        "key": key,
        "value": val
    })


@app.route("/api/storage/sync", methods=["POST"])
def api_storage_sync():
    """Batch synchronizes localStorage payload into SQLite database and returns full state."""
    data = request.json or {}
    storage_dict = data.get("storage") or {}
    updated_storage = sync_storage_batch(storage_dict)
    return jsonify({
        "success": True,
        "storage": updated_storage,
        "message": "All local storage data successfully synchronized into SQLite database."
    })


# =====================================================
# USER PREFERENCES & THEME APIS (SQLite Persisted)
# =====================================================

@app.route("/api/user/preferences", methods=["GET", "POST"])
def api_user_preferences():
    """Retrieves or saves user preferences (theme, settings) in SQLite database."""
    if request.method == "POST":
        data = request.json or {}
        user_id = data.get("user_id") or 1
        key = data.get("key") or "theme"
        value = data.get("value") or "light"
        save_user_preference(user_id, key, value)
        prefs = get_user_preferences(user_id)
        return jsonify({
            "success": True,
            "preferences": prefs,
            "message": f"Preference '{key}' saved in SQLite database."
        })

    user_id = request.args.get("user_id") or 1
    prefs = get_user_preferences(user_id)
    return jsonify({
        "success": True,
        "preferences": prefs
    })


# =====================================================
# STUDY & EDUCATIONAL PROGRESS APIS (SQLite Persisted)
# =====================================================

@app.route("/api/study/progress", methods=["GET", "POST"])
def api_study_progress():
    """Retrieves or saves study module progress, bookmarks, and completions in SQLite."""
    if request.method == "POST":
        data = request.json or {}
        user_id = data.get("user_id") or 1
        module_key = data.get("module_key") or "general"
        progress_data = data.get("progress_data") or {}
        save_study_progress(user_id, module_key, progress_data)
        return jsonify({
            "success": True,
            "message": f"Study progress for '{module_key}' saved in SQLite database."
        })

    user_id = request.args.get("user_id") or 1
    progress = get_study_progress(user_id)
    return jsonify({
        "success": True,
        "progress": progress
    })


# =====================================================
# ACTIVE SESSIONS APIS (SQLite Persisted)
# =====================================================

@app.route("/api/auth/session", methods=["GET", "POST"])
def api_auth_session():
    """Stores or validates user sessions against SQLite user_sessions table."""
    if request.method == "POST":
        data = request.json or {}
        token = data.get("token")
        user_id = data.get("user_id") or 1
        role = data.get("role") or "patient"
        user_data = data.get("user_data") or {}

        if not token:
            return jsonify({"success": False, "error": "Session token required."}), 400

        create_user_session(token, user_id, role, user_data)
        return jsonify({
            "success": True,
            "message": "Session successfully persisted in SQLite database."
        })

    auth_header = request.headers.get("Authorization", "")
    token = request.args.get("token")
    if not token and auth_header.startswith("Bearer "):
        token = auth_header[7:].strip()

    if not token:
        return jsonify({"success": False, "error": "No token provided."}), 400

    session = validate_user_session(token)
    if not session:
        return jsonify({"success": False, "error": "Session invalid or expired."}), 401

    return jsonify({
        "success": True,
        "session": session
    })


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """Removes active session from SQLite database."""
    data = request.json or {}
    token = data.get("token")
    if token:
        delete_user_session(token)
    return jsonify({
        "success": True,
        "message": "Logged out and session cleared from SQLite database."
    })



@app.route("/api/patients/<identifier>", methods=["GET", "PUT", "POST", "DELETE"])
def api_patient_detail(identifier):
    """Fetches, updates, or deletes patient profile, active prescriptions, and case history."""
    if request.method == "DELETE":
        deleted = delete_patient_account(identifier)
        if not deleted:
            return jsonify({"success": False, "error": "Patient record could not be found or deleted."}), 404
        
        # If client provided email and deleted didn't have one in DB:
        req_data = request.get_json(silent=True) or {}
        client_email = request.args.get("email") or req_data.get("email")
        if isinstance(deleted, dict) and not deleted.get("email") and client_email:
            deleted["email"] = client_email
            try:
                try:
                    from email_service import send_account_deletion_email_async
                except ImportError:
                    from backend.email_service import send_account_deletion_email_async
                send_account_deletion_email_async(deleted)
            except Exception as em_err:
                print(f"[ACCOUNT DELETION] Failed to dispatch deletion email: {em_err}")

        return jsonify({
            "success": True,
            "message": "Patient account and associated records deleted permanently. Confirmation email sent.",
            "deleted": deleted if isinstance(deleted, dict) else {}
        })

    if request.method in ["PUT", "POST"]:
        data = request.get_json(silent=True) or {}
        # Strictly enforce lock on email and gender
        data.pop("email", None)
        data.pop("username", None)
        data.pop("gender", None)
        updated = update_patient_profile(identifier, data)
        if not updated:
            return jsonify({"success": False, "error": "Patient record could not be updated."}), 404
        return jsonify({
            "success": True,
            "message": "Patient profile updated successfully.",
            "patient": updated
        })

    patient = get_patient_data(identifier)
    if not patient:
        return jsonify({"success": False, "error": "Patient record not found."}), 404

    return jsonify({
        "success": True,
        "patient": patient
    })


@app.route("/api/patient/update-profile", methods=["POST", "PUT"])
def api_update_patient_profile():
    """Direct alias endpoint for updating patient profile."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier") or data.get("abha_id") or data.get("abhaId") or data.get("id") or data.get("user_id")
    if not identifier:
        return jsonify({"success": False, "error": "Patient identifier required."}), 400
    # Strictly enforce lock on email and gender
    data.pop("email", None)
    data.pop("username", None)
    data.pop("gender", None)
    updated = update_patient_profile(identifier, data)
    if not updated:
        return jsonify({"success": False, "error": "Patient record could not be updated."}), 404
    return jsonify({
        "success": True,
        "message": "Patient profile updated successfully.",
        "patient": updated
    })


@app.route("/api/doctor/update-patient-name", methods=["POST", "PUT"])
@app.route("/api/patient/update-name", methods=["POST", "PUT"])
def api_update_patient_name():
    """Updates patient name across clinical records, cases, appointments, and reviews."""
    data = request.get_json(silent=True) or {}
    old_name = data.get("old_name") or data.get("current_name")
    new_name = data.get("new_name") or data.get("name")
    patient_id = data.get("patient_id") or data.get("id")
    if not old_name or not new_name:
        return jsonify({"success": False, "error": "Both old_name and new_name are required."}), 400
    res = update_patient_name_everywhere(old_name, new_name, patient_id)
    return jsonify(res), (200 if res.get("success") else 400)


@app.route("/api/patient/delete-account", methods=["POST", "DELETE"])
def api_delete_patient_account():
    """Endpoint to permanently delete patient account and send confirmation email."""
    data = request.get_json(silent=True) or {}
    identifier = data.get("identifier") or data.get("abha_id") or data.get("abhaId") or data.get("id") or data.get("user_id")
    if not identifier:
        return jsonify({"success": False, "error": "Patient identifier required."}), 400
    deleted = delete_patient_account(identifier)
    if not deleted:
        return jsonify({"success": False, "error": "Patient record could not be found or deleted."}), 404
    
    # If client passed email in body and deleted didn't have one:
    client_email = data.get("email")
    if isinstance(deleted, dict) and not deleted.get("email") and client_email:
        deleted["email"] = client_email
        try:
            try:
                from email_service import send_account_deletion_email_async
            except ImportError:
                from backend.email_service import send_account_deletion_email_async
            send_account_deletion_email_async(deleted)
        except Exception as em_err:
            print(f"[ACCOUNT DELETION] Failed to dispatch deletion email: {em_err}")

    return jsonify({
        "success": True,
        "message": "Patient account deleted permanently. Confirmation email dispatched.",
        "deleted": deleted if isinstance(deleted, dict) else {}
    })


@app.route("/api/admin/summary", methods=["GET"])
def api_admin_summary():
    """Returns aggregated hospital and AYUSH clinic summary for administrators."""
    summary = get_admin_summary()
    history = get_recent_history()
    summary["recent_history"] = history
    summary["history"] = history
    summary["inflow_daily"] = get_hospital_patient_inflow("daily", 14, metric="registrations")
    summary["inflow_weekly"] = get_hospital_patient_inflow("weekly", 8, metric="registrations")
    return jsonify({
        "success": True,
        "summary": summary
    })


@app.route("/api/admin/emergency", methods=["GET"])
def api_admin_emergency():
    """Returns active emergency triage cases for immediate clinical attention."""
    try:
        cases = get_emergency_cases()
        return jsonify({
            "success": True,
            "emergency_cases": cases,
            "count": len(cases)
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/admin/registered-patients", methods=["GET"])
def api_admin_registered_patients():
    """Returns all registered patient profiles and accounts in the hospital database."""
    try:
        patients = get_all_registered_patients()
        return jsonify({
            "success": True,
            "patients": patients,
            "count": len(patients)
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/admin/history", methods=["GET"])
def api_admin_history():
    """Returns recent patient consultation history, including issue and prescribed medicines."""
    try:
        history = get_recent_history()
        return jsonify({
            "success": True,
            "history": history,
            "recent_history": history,
            "count": len(history)
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# CLINICAL FOLLOW-UPS, PRESCRIPTIONS & EMERGENCY CASES
# =====================================================

@app.route("/api/doctor/followup-prescription", methods=["POST"])
@app.route("/api/followup-prescription", methods=["POST"])
def api_followup_prescription():
    """Saves a follow-up consultation outcome, prescription, suggestions, and attendance status."""
    try:
        data = request.get_json(silent=True) or {}
        patient_name = (data.get("patient_name") or "").strip()
        doctor_id = data.get("doctor_id") or 1
        prescription = (data.get("prescription") or "").strip()
        suggestion = (data.get("suggestion") or "").strip()
        absent = bool(data.get("absent", False))

        if not patient_name:
            return jsonify({"success": False, "error": "Patient name is required."}), 400

        if not absent and not prescription:
            return jsonify({"success": False, "error": "Prescription details are required when patient is present."}), 400

        result = save_followup_prescription(
            patient_name=patient_name,
            doctor_id=doctor_id,
            prescription=prescription,
            suggestion=suggestion,
            absent=absent,
        )
        status_code = 200 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/patient/prescriptions", methods=["GET"])
def api_patient_prescriptions():
    """Returns all clinical prescriptions for a patient across all consultations."""
    identifier = (
        request.args.get("identifier")
        or request.args.get("patient_id")
        or request.args.get("abha_id")
        or request.args.get("name")
        or ""
    ).strip()
    if not identifier:
        return jsonify({"success": False, "error": "Patient identifier is required."}), 400
    try:
        prescriptions = get_patient_prescriptions(identifier)
        return jsonify({
            "success": True,
            "prescriptions": prescriptions,
            "count": len(prescriptions),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/doctor/emergency", methods=["POST"])
@app.route("/api/emergency", methods=["POST"])
def api_add_emergency():
    """Registers an acute emergency triage case for immediate clinical and administrative care."""
    try:
        data = request.get_json(silent=True) or {}
        patient_name = (data.get("patient_name") or "").strip()
        if not patient_name:
            return jsonify({"success": False, "error": "Patient name is required."}), 400

        issue = (data.get("issue") or "").strip()
        if not issue:
            return jsonify({"success": False, "error": "Emergency clinical issue is required."}), 400

        age = data.get("age")
        gender = data.get("gender") or "Not Specified"
        doctor_id = data.get("doctor_id") or 1
        doctor_name = (data.get("doctor_name") or "On-Duty Emergency Clinician").strip()
        triage_level = data.get("triage_level") or "Emergency"
        bed_number = data.get("bed_number") or "Triage Bay"
        status = data.get("status") or "Under Immediate Care"

        result = add_emergency_case(
            patient_name=patient_name,
            age=age,
            gender=gender,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            issue=issue,
            triage_level=triage_level,
            bed_number=bed_number,
            status=status,
        )
        status_code = 201 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/articles", methods=["GET", "POST"])
def api_articles():
    """Retrieves or publishes clinical research and Ayurvedic articles."""
    try:
        if request.method == "POST":
            data = request.get_json(silent=True) or {}
            title = (data.get("title") or "").strip()
            author = (data.get("author") or "Hospital Clinician").strip()
            category = (data.get("category") or "Clinical Research").strip()
            minutes = data.get("minutes", 15)
            source = (data.get("source") or "AYURCASE Clinical Faculty").strip()
            excerpt = (data.get("excerpt") or "").strip()
            content = (data.get("content") or "").strip()
            icon = (data.get("icon") or "fa-solid fa-file-lines").strip()

            if not title:
                return jsonify({"success": False, "error": "Article title is required."}), 400

            image_url = (data.get("image_url") or data.get("image") or "").strip()
            result = add_article(
                title=title,
                author=author,
                category=category,
                minutes=minutes,
                source=source,
                excerpt=excerpt,
                content=content,
                icon=icon,
                image_url=image_url,
            )
            return jsonify(result), 201 if result.get("success") else 400

        articles = get_all_articles()
        return jsonify({"success": True, "articles": articles, "count": len(articles)})
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/doctor/lab-report", methods=["POST"])
@app.route("/api/lab-report", methods=["POST"])
def api_add_lab_report():
    """Records a clinical laboratory report (Sugar, Pressure, Hemoglobin) and emails it to the patient."""
    try:
        data = request.get_json(silent=True) or {}
        patient_name = (data.get("patient_name") or "").strip()
        if not patient_name:
            return jsonify({"success": False, "error": "Patient name is required."}), 400

        sugar = (data.get("sugar") or "").strip()
        pressure = (data.get("pressure") or "").strip()
        hemoglobin = (data.get("hemoglobin") or "").strip()

        if not sugar and not pressure and not hemoglobin:
            return jsonify({"success": False, "error": "At least one lab parameter (Sugar, Pressure, or Hemoglobin) is required."}), 400

        notes = (data.get("notes") or "").strip()
        doctor_id = data.get("doctor_id") or 1
        doctor_name = (data.get("doctor_name") or "Dr. Arindam Sen").strip()
        patient_email = (data.get("patient_email") or data.get("email") or "").strip()

        result = add_lab_report(
            patient_name=patient_name,
            sugar=sugar,
            pressure=pressure,
            hemoglobin=hemoglobin,
            notes=notes,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            patient_email=patient_email,
        )
        status_code = 201 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/patient/lab-reports", methods=["GET"])
@app.route("/api/lab-reports", methods=["GET"])
def api_patient_lab_reports():
    """Returns clinical laboratory reports for a patient by identifier (name, email, or ABHA ID)."""
    identifier = (
        request.args.get("identifier")
        or request.args.get("patient_name")
        or request.args.get("name")
        or request.args.get("email")
        or request.args.get("patient_id")
        or request.args.get("abha_id")
        or ""
    ).strip()
    try:
        if identifier:
            reports = get_patient_lab_reports(identifier)
        else:
            reports = get_all_lab_reports()
        return jsonify({
            "success": True,
            "lab_reports": reports,
            "count": len(reports),
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


# =====================================================
# CLINICAL AI EVALUATION & REVIEW (Doctor 1-5 Star & Comments)
# =====================================================

@app.route("/api/doctor/ai-review", methods=["POST"])
@app.route("/api/ai-review", methods=["POST"])
def api_add_ai_review():
    """Saves a doctor's clinical review and 1-5 rating of an AI response and patient question."""
    try:
        data = request.get_json(silent=True) or {}
        review_id = data.get("review_id") or data.get("id")
        patient_name = (data.get("patient_name") or data.get("patient") or "").strip()
        patient_question = (data.get("patient_question") or data.get("question") or "").strip()
        ai_answer = (data.get("ai_answer") or data.get("answer") or "").strip()
        rating = data.get("rating")
        comment = (data.get("comment") or data.get("comments") or "").strip()
        doctor_id = data.get("doctor_id") or 1
        doctor_name = (data.get("doctor_name") or "Dr. Arindam Sen").strip()

        if not patient_question and not review_id:
            return jsonify({"success": False, "error": "Patient question is required."}), 400
        if not ai_answer and not review_id:
            return jsonify({"success": False, "error": "AI answer is required."}), 400
        if rating is None or rating == "":
            return jsonify({"success": False, "error": "Rating (1 to 5 stars) is required."}), 400

        try:
            int_rating = int(rating)
            if int_rating < 1 or int_rating > 5:
                raise ValueError()
        except (ValueError, TypeError):
            return jsonify({"success": False, "error": "Rating must be an integer between 1 and 5."}), 400

        result = add_ai_review(
            patient_question=patient_question,
            ai_answer=ai_answer,
            rating=int_rating,
            comment=comment,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            review_id=review_id,
            patient_name=patient_name
        )
        status_code = 201 if result.get("success") else 400
        return jsonify(result), status_code
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/doctor/ai-reviews", methods=["GET"])
@app.route("/api/ai-reviews", methods=["GET"])
def api_get_ai_reviews():
    """Returns clinical AI reviews, optionally filtered by ?status=Upcoming or ?status=Reviewed."""
    try:
        limit = int(request.args.get("limit", 50))
        status = request.args.get("status")
        reviews = get_all_ai_reviews(status=status, limit=limit)
        upcoming_list = get_all_ai_reviews(status="Upcoming", limit=100)
        return jsonify({
            "success": True,
            "reviews": reviews,
            "count": len(reviews),
            "upcoming_count": len(upcoming_list)
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/doctor/ai-review", methods=["POST"])
@app.route("/api/doctor/ai-reviews", methods=["POST"])
@app.route("/api/doctor/ai-reviews/<int:review_id>", methods=["POST", "PUT"])
def api_submit_doctor_ai_review(review_id=None):
    """Submits doctor's rating and feedback for an AI solution."""
    try:
        data = request.get_json(silent=True) or {}
        r_id = review_id or data.get("review_id") or data.get("id")
        res = add_ai_review(
            doctor_id=data.get("doctor_id"),
            doctor_name=data.get("doctor_name"),
            patient_name=data.get("patient_name"),
            patient_question=data.get("patient_question"),
            ai_answer=data.get("ai_answer"),
            rating=data.get("rating", 5),
            comment=data.get("comment", ""),
            review_id=r_id
        )
        if not res.get("success"):
            return jsonify(res), 400
        return jsonify(res), 200
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/doctor/ai-reviews/history", methods=["GET"])
@app.route("/api/ai-reviews/history", methods=["GET"])
def api_get_ai_reviews_history():
    """Returns past evaluated and rated AI reviews."""
    try:
        limit = int(request.args.get("limit", 50))
        history = get_all_ai_reviews(status="Reviewed", limit=limit)
        return jsonify({
            "success": True,
            "history": history,
            "reviews": history,
            "count": len(history)
        })
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500



@app.route("/api/patient/ask-ai", methods=["POST"])
@app.route("/api/patient/ai-query", methods=["POST"])
def api_patient_ask_ai():
    """
    Allows a patient to submit their health or symptom inquiry.
    Generates an immediate AI Ayurvedic assessment and queues it into ai_reviews
    for doctor clinical evaluation and verification.
    """
    try:
        data = request.get_json(silent=True) or {}
        question = (data.get("question") or data.get("problem") or "").strip()
        patient_name = (data.get("patient_name") or data.get("name") or "Rohit Sharma").strip()

        if not question:
            return jsonify({"success": False, "error": "Health question or symptoms are required."}), 400

        recommendation = ""
        api_key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if api_key:
            try:
                client = genai.Client(api_key=api_key)
                prompt = f"""
You are an expert Ayurvedic clinical assistant on AYURCASE.
A patient named {patient_name} reports the following health question or symptoms:
"{question}"

Provide a concise, practical, and authentic Ayurvedic assessment:
1. Probable Ayurvedic pathology and Dosha imbalance (e.g. Pitta Prakopa, Vata Vriddhi, Kapha Sanchaya).
2. Primary traditional formulations (herbal churnas, rasayanas, decoctions with safe standard adult dosage guidelines).
3. Pathya and Apathya (Dietary and lifestyle dos & don'ts).
4. Note that this protocol has been submitted to your AYURCASE doctor for clinical review.
Keep the answer authoritative, safe, and helpful (under 120 words).
"""
                resp = client.models.generate_content(
                    model=get_gemini_model(),
                    contents=prompt
                )
                recommendation = str(getattr(resp, "text", "") or "").strip()
            except Exception as gemini_err:
                app.logger.warning(f"Gemini error for patient query: {gemini_err}")

        if not recommendation:
            q_lower = question.lower()
            if any(w in q_lower for w in ["burn", "acid", "reflux", "heartburn", "gerd", "amlapitta"]):
                recommendation = "Assessment: Urdhwaga Amlapitta (Pitta aggravation with sour reflux). Recommended Protocol: Avipattikar Churna 3g twice daily before food with lukewarm water; Kamadudha Rasa (Mukta Yukta) 250mg morning & night. Pathya: Tender coconut water, coriander seed infusion, avoid oily, sour, and fermented foods. Submitted for doctor verification."
            elif any(w in q_lower for w in ["joint", "knee", "stiff", "arthritis", "crepitus", "pain", "swelling"]):
                recommendation = "Assessment: Sandhigata Vata (Osteoarthritic Vata aggravation in Majja Dhatu). Recommended Protocol: Yogaraj Guggulu 2 tablets twice daily after meals with warm water; Dashamoola Kashayam 15ml with 45ml boiled water BD. External: Gentle application of Mahanarayana Taila. Avoid exposure to cold air. Submitted for doctor verification."
            elif any(w in q_lower for w in ["sleep", "insomnia", "stress", "anxiety", "anidra"]):
                recommendation = "Assessment: Anidra & Vata-Manovaha Srotas disturbance. Recommended Protocol: Ashwagandha Churna 3g at bedtime with warm cow's milk; Brahmi Vati 1 tablet twice daily; apply warm sesame oil or Ksheerabala Taila on soles of feet (Padabhyanga). Submitted for doctor verification."
            elif any(w in q_lower for w in ["bloat", "gas", "indigestion", "constipat", "stomach"]):
                recommendation = "Assessment: Agnimandya with Adhmana (Sluggish digestive fire with trapped gas). Recommended Protocol: Hingwashtak Churna 2g with first morsel of food with warm ghee; Triphala Churna 3g at bedtime with warm water. Drink warm water throughout the day. Submitted for doctor verification."
            else:
                recommendation = f"Assessment: Tridosha assessment required for '{question[:50]}...'. Recommended Protocol: Panchakola Phanta or Trikatu Churna 1g before meals to balance Agni. Stay adequately hydrated with lukewarm water and avoid heavy, cold, or processed meals. Submitted for doctor verification."

        # Save to database as a pending review query for doctors
        save_res = add_upcoming_patient_ai_query(
            patient_name=patient_name,
            patient_question=question,
            ai_answer=recommendation,
            doctor_id=1,
            doctor_name="Dr. Arindam Sen"
        )

        return jsonify({
            "success": True,
            "patient_name": patient_name,
            "question": question,
            "recommendation": recommendation,
            "review_id": save_res.get("id"),
            "message": "AI solution generated and submitted to doctor for clinical review."
        }), 201
    except Exception as exc:
        return jsonify({"success": False, "error": str(exc)}), 500


@app.route("/api/admin/inflow", methods=["GET"])

def api_admin_inflow():
    """Returns patient footfall / registration analytics (daily or weekly) for trading-style chart."""
    period = request.args.get("period", "daily").lower()
    metric = request.args.get("metric", "registrations").lower()
    try:
        count = int(request.args.get("count", 14 if period == "daily" else 8))
    except (TypeError, ValueError):
        count = 14 if period == "daily" else 8
    try:
        inflow = get_hospital_patient_inflow(period=period, count=count, metric=metric)
        return jsonify({
            "success": True,
            "data": inflow
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/doctors/<int:doctor_id>/patients", methods=["GET"])
def api_admin_doctor_patients(doctor_id):
    """Returns the patient directory and schedule for one doctor in the admin console."""
    doctor = get_admin_doctor_patients(doctor_id)
    if not doctor:
        return jsonify({"success": False, "error": "Doctor not found."}), 404
    return jsonify({"success": True, "doctor": doctor})


@app.route("/api/admin/patients/update", methods=["POST"])
def api_admin_patient_update():
    """Updates clinical and demographic details for a patient record."""
    body = request.get_json(silent=True) or {}
    case_id = body.get("case_id") or body.get("id")
    if not case_id:
        return jsonify({"success": False, "error": "case_id is required."}), 400

    try:
        res = update_patient_case_record(int(case_id), body)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/patients/merge", methods=["POST"])
def api_admin_patient_merge():
    """Merges duplicate patient case into primary patient case."""
    body = request.get_json(silent=True) or {}
    primary_id = body.get("primary_id") or body.get("primary_case_id")
    duplicate_id = body.get("duplicate_id") or body.get("duplicate_case_id")

    if not primary_id or not duplicate_id:
        return jsonify({"success": False, "error": "Both primary_id and duplicate_id are required."}), 400

    try:
        res = merge_patient_records(int(primary_id), int(duplicate_id))
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/patients/deactivate", methods=["POST"])
def api_admin_patient_deactivate():
    """Toggles patient case status to 'Deactivated' or 'Completed'."""
    body = request.get_json(silent=True) or {}
    case_id = body.get("case_id") or body.get("id")
    action = body.get("action", "deactivate")

    if not case_id:
        return jsonify({"success": False, "error": "case_id is required."}), 400

    try:
        res = deactivate_patient_record(int(case_id), action=action)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/patients/reassign-doctor", methods=["POST"])
def api_admin_patient_reassign_doctor():
    """Reassigns appointed doctor for a patient in follow-up activity or case registry."""
    body = request.get_json(silent=True) or {}
    try:
        res = reassign_patient_doctor(body)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/doctors/add", methods=["POST"])
def api_admin_doctor_add():
    """Adds a new verified practitioner to the AYUSH wing."""
    body = request.get_json(silent=True) or {}
    try:
        res = add_doctor_record(body)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/doctors/update", methods=["POST"])
def api_admin_doctor_update():
    """Updates practitioner credentials, qualification, and specialization."""
    body = request.get_json(silent=True) or {}
    doc_id = body.get("doctor_id") or body.get("id")
    if not doc_id:
        return jsonify({"success": False, "error": "doctor_id is required."}), 400
    try:
        res = update_doctor_record(int(doc_id), body)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/doctors/remove", methods=["POST"])
def api_admin_doctor_remove():
    """Sets doctor status to 'Past Doctor' (or reactivates), safely preserving all clinical data."""
    body = request.get_json(silent=True) or {}
    doc_id = body.get("doctor_id") or body.get("id")
    action = body.get("action", "remove")
    if not doc_id:
        return jsonify({"success": False, "error": "doctor_id is required."}), 400
    try:
        res = remove_doctor_record(int(doc_id), action=action)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# EMAIL & NOTIFICATION APIS
# =====================================================

@app.route("/api/admin/emails", methods=["GET"])
def api_admin_emails():
    """Returns recent dispatched emails and delivery status from SQLite."""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id, recipient, subject, email_type, status, details_json, error_message, sent_at FROM email_logs ORDER BY id DESC LIMIT 50;")
        rows = cursor.fetchall()
        emails = [dict(r) for r in rows]
        conn.close()
        return jsonify({"success": True, "emails": emails, "count": len(emails)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/emails/latest", methods=["GET"])
def api_latest_email():
    """Returns the most recent email sent to a given recipient or ABHA ID."""
    recipient = request.args.get("recipient") or request.args.get("email") or ""
    try:
        from database import get_db_connection
        conn = get_db_connection()
        cursor = conn.cursor()
        if recipient:
            cursor.execute("SELECT * FROM email_logs WHERE recipient = ? ORDER BY id DESC LIMIT 1;", (recipient.strip(),))
        else:
            cursor.execute("SELECT * FROM email_logs ORDER BY id DESC LIMIT 1;")
        row = cursor.fetchone()
        conn.close()
        if not row:
            return jsonify({"success": False, "message": "No emails found"}), 404
        return jsonify({"success": True, "email": dict(row)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/test-email", methods=["GET", "POST"])
def api_test_email():
    """Sends a test email to verify SMTP configuration and returns status."""
    data = request.get_json(silent=True) or {}
    recipient = request.args.get("to") or data.get("to") or os.getenv("SMTP_USER")
    try:
        from email_service import send_welcome_email
        test_payload = {
            "name": "AYURCASE Test User",
            "email": recipient,
            "phone": "+91 98765 43210",
            "abha_id": "ABHA-TEST-0001",
            "age": 28,
            "gender": "Other",
            "blood_group": "O+",
            "prakriti_primary": "Tridoshic"
        }
        res = send_welcome_email(test_payload)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/admin/test-appointment-email", methods=["GET", "POST"])
def api_test_appointment_email():
    """Sends a test appointment confirmation email to verify email styling and delivery."""
    data = request.get_json(silent=True) or {}
    recipient = request.args.get("to") or data.get("to") or os.getenv("SMTP_USER")
    try:
        from email_service import send_appointment_confirmation_email
        test_apt = {
            "id": 999,
            "patient_name": "Ronit Saha",
            "patient_email": recipient,
            "patient_phone": "+91 98765 43210",
            "patient_abha_id": "ABHA-2088-3764",
            "doctor_name": "Dr. Arindam Sen",
            "specialization": "Kayachikitsa & Nadi Pariksha Specialist",
            "qualification": "BAMS, MD (Ayurveda)",
            "council_reg_no": "AYUSH-WB-2014-0891",
            "appointment_date": str(date.today()),
            "appointment_time": "11:30 AM",
            "consultation_type": "In-Clinic Consultation",
            "symptoms_notes": "Ayurvedic pulse diagnosis and clinical assessment for digestive balance",
            "status": "Confirmed"
        }
        res = send_appointment_confirmation_email(test_apt)
        status_code = 200 if res.get("success") else 400
        return jsonify(res), status_code
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# DOCTORS & APPOINTMENT APIS
# =====================================================

@app.route("/api/doctor-dashboard", methods=["GET"])
def api_doctor_dashboard():
    """Returns current dashboard data for one authenticated practitioner."""
    doctor_id = request.args.get("doctor_id") or "1"
    dashboard = get_doctor_dashboard(doctor_id)
    if not dashboard:
        return jsonify({"success": False, "error": "Practitioner account not found."}), 404
    return jsonify({"success": True, "dashboard": dashboard})

@app.route("/api/doctors", methods=["GET"])
def api_doctors():
    """Returns list of available AYUSH doctors for selection."""
    try:
        doctors = get_doctors_list()
        return jsonify({"success": True, "doctors": doctors})
    except Exception as e:
        print("Error fetching doctors:", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/appointments", methods=["GET", "POST"])
def api_appointments():
    """Retrieves or books appointments between patients and doctors."""
    if request.method == "POST":
        data = request.json or {}
        patient_name = data.get("patient_name")
        doctor_name = data.get("doctor_name")
        appointment_date = data.get("appointment_date")
        appointment_time = data.get("appointment_time")
        consultation_type = data.get("consultation_type", "In-Clinic Consultation")
        symptoms_notes = data.get("symptoms_notes", "")
        patient_id = data.get("patient_id")
        doctor_id = data.get("doctor_id")
        patient_email = data.get("patient_email")
        patient_phone = data.get("patient_phone")
        patient_abha_id = data.get("patient_abha_id") or data.get("abha_id")

        if not patient_name or not doctor_name or not appointment_date or not appointment_time:
            return jsonify({
                "success": False,
                "error": "patient_name, doctor_name, appointment_date, and appointment_time are required."
            }), 400

        try:
            requested_date = date.fromisoformat(appointment_date)
        except (TypeError, ValueError):
            return jsonify({"success": False, "error": "appointment_date must use YYYY-MM-DD format."}), 400

        if requested_date < date.today():
            return jsonify({"success": False, "error": "Appointments cannot be scheduled in the past."}), 400

        try:
            new_apt = create_appointment(
                patient_name=patient_name,
                doctor_name=doctor_name,
                appointment_date=appointment_date,
                appointment_time=appointment_time,
                consultation_type=consultation_type,
                symptoms_notes=symptoms_notes,
                patient_id=patient_id,
                doctor_id=doctor_id,
                age=data.get("age"),
                gender=data.get("gender"),
                patient_email=patient_email,
                patient_phone=patient_phone,
                patient_abha_id=patient_abha_id,
            )
            return jsonify({"success": True, "appointment": new_apt}), 201
        except ValueError as e:
            return jsonify({"success": False, "error": str(e)}), 400
        except Exception as e:
            print("Error creating appointment:", e)
            return jsonify({"success": False, "error": str(e)}), 500

    else:
        # GET
        doctor_id = request.args.get("doctor_id")
        doctor_name = request.args.get("doctor_name")
        patient_id = request.args.get("patient_id")
        patient_name = request.args.get("patient_name")

        try:
            appointments = get_appointments(
                doctor_id=doctor_id,
                doctor_name=doctor_name,
                patient_id=patient_id,
                patient_name=patient_name
            )
            return jsonify({"success": True, "appointments": appointments})
        except Exception as e:
            print("Error fetching appointments:", e)
            return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/appointments/<int:appointment_id>", methods=["DELETE"])
def api_delete_appointment(appointment_id):
    """Cancels or deletes a clinical appointment by its integer ID."""
    try:
        success = delete_appointment(appointment_id)
        if not success:
            return jsonify({"success": False, "error": f"Appointment #{appointment_id} not found or already deleted."}), 404
        return jsonify({"success": True, "message": f"Appointment #{appointment_id} successfully cancelled and removed."})
    except Exception as e:
        print(f"Error deleting appointment #{appointment_id}:", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/appointments/cancel", methods=["POST", "DELETE"])
def api_cancel_appointment():
    """Cancels appointment by appointment_id or patient_name."""
    data = request.get_json(silent=True) or {}
    appointment_id = data.get("appointment_id") or request.args.get("appointment_id")
    patient_name = data.get("patient_name") or request.args.get("patient_name")
    try:
        if appointment_id:
            success = delete_appointment(int(appointment_id))
            if success:
                return jsonify({"success": True, "message": f"Appointment #{appointment_id} cancelled successfully."})
        if patient_name:
            success = cancel_appointment_by_patient_name(patient_name)
            if success:
                return jsonify({"success": True, "message": f"Follow-up appointment for '{patient_name}' cancelled successfully."})
        return jsonify({"success": False, "error": "Appointment not found or already cancelled."}), 404
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# GEMINI AI CLINICAL COPILOT
# =====================================================

@app.route("/api/recommend", methods=["POST"])
def recommend():
    data = request.get_json(silent=True) or {}
    problem = str(data.get("problem") or "").strip()
    mode = str(data.get("mode") or "").strip().lower()

    if not problem:
        return jsonify({
            "error": "Please enter some patient information."
        }), 400

    # The UI limits questions to 4,000 characters. Truncating here keeps the
    # public endpoint predictable when it is called directly after deployment.
    problem = problem[:MAX_ASSISTANT_QUESTION_LENGTH]

    try:
        client = get_gemini_client()
    except Exception as error:
        app.logger.warning("Gemini client configuration failed: %s", type(error).__name__)
        return jsonify({
            "recommendation": assistant_fallback(problem),
            "source": "fallback",
            "reason": "configuration_unavailable",
        })

    if not client:
        return jsonify({
            "recommendation": assistant_fallback(problem),
            "source": "fallback",
            "reason": "not_configured",
        })

    if mode == "patient-assistant":
        prompt = f"""
You are the AYURCASE Assistant, a helpful general-purpose assistant inside the
AYURCASE portal. You can answer everyday general questions, explain how to use
this website, and provide general health and wellness information.

AYURCASE patient portal context:
- Patients can view their Digital ABHA Health Card and profile.
- Patients can book and review appointments, view case history, explore their
  Prakriti score, and use the learning section.
- Do not claim that a website action has been completed unless the user can see
  confirmation in the portal. If unsure about a feature, say so plainly.

For health questions:
- Give general educational information and practical, low-risk suggestions.
- Do not diagnose conditions, prescribe medication, or give medication doses.
- Explain uncertainty and encourage a qualified clinician when appropriate.
- For symptoms that could be urgent or life-threatening, advise immediate local
  emergency care.

For non-health questions, answer helpfully and directly. Keep responses clear,
concise, and friendly.
- Never return an empty response. If you cannot safely answer, explain why and
  offer a safe, practical next step instead.

User question:
{problem}
"""
    else:
        prompt = f"""
You are a patient guidance assistant for a healthcare application.

The patient has reported:

{problem}

Provide general health information and appropriate next-step guidance.

Important rules:
- Do not claim to diagnose the patient.
- Do not prescribe medication.
- Do not provide medication dosages.
- Do not present your response as a medical diagnosis.
- Explain uncertainty when appropriate.
- Recommend consulting a qualified healthcare professional when appropriate.
- If the symptoms could indicate an emergency, clearly recommend seeking urgent medical attention.
- Keep the response clear and easy to understand.
- Never return an empty response. If you cannot safely answer, explain why and
  offer a safe, practical next step instead.
"""

    try:
        response = client.models.generate_content(
            model=get_gemini_model(),
            contents=prompt,
        )

        recommendation = str(getattr(response, "text", "") or "").strip()
        if not recommendation:
            raise RuntimeError("Gemini returned an empty response")

        return jsonify({
            "recommendation": recommendation,
            "source": "gemini",
        })
    except Exception as error:
        # Do not log the user's health question. Deployment logs can be
        # retained by hosting providers, so record only the failure type.
        app.logger.warning(
    "Gemini request failed: %s: %s",
    type(error).__name__,
    error
)
        return jsonify({
            "recommendation": assistant_fallback(problem),
            "source": "fallback",
            "reason": "provider_unavailable",
        })


# =====================================================
# NOTICES & CLINICAL ORDERS ENDPOINTS
# =====================================================

@app.get("/api/notices")
def api_get_notices():
    """Retrieves all hospital notices, meetings, and orders."""
    order = request.args.get("order", "desc")
    try:
        notices = get_notices(order=order)
        return jsonify({
            "success": True,
            "notices": notices,
            "count": len(notices),
            "order": order,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/api/notices")
def api_create_notice():
    """Creates a new administrative notice/order."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    content = data.get("content", "").strip()
    notice_type = data.get("notice_type", "General").strip()
    priority = data.get("priority", "Normal").strip()
    posted_by = data.get("posted_by", "Hospital Administration").strip()

    if not title:
        return jsonify({"success": False, "error": "Notice title is required."}), 400
    if not content:
        return jsonify({"success": False, "error": "Notice content is required."}), 400

    try:
        notice = add_notice(
            title=title,
            content=content,
            notice_type=notice_type,
            priority=priority,
            posted_by=posted_by
        )
        return jsonify({"success": True, "notice": notice}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.delete("/api/notices/<int:notice_id>")
def api_delete_notice(notice_id):
    """Deletes an administrative notice."""
    try:
        success = delete_notice(notice_id)
        return jsonify({"success": success})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.post("/api/notices/<int:notice_id>/comments")
def api_add_notice_comment(notice_id):
    """Allows a doctor to post a comment / reply / acknowledgement on a notice."""
    data = request.get_json(silent=True) or {}
    comment_text = data.get("comment_text", "").strip()
    author_name = data.get("author_name", "Doctor").strip()
    doctor_id = data.get("doctor_id")
    author_role = data.get("author_role", "doctor").strip()

    if not comment_text:
        return jsonify({"success": False, "error": "Comment text cannot be empty."}), 400

    try:
        comment = add_notice_comment(
            notice_id=notice_id,
            doctor_id=doctor_id,
            author_name=author_name,
            comment_text=comment_text,
            author_role=author_role
        )
        return jsonify({"success": True, "comment": comment}), 201
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.get("/api/notices/<int:notice_id>/comments")
def api_get_notice_comments(notice_id):
    """Retrieves all comments for a specific notice."""
    try:
        comments = get_notice_comments(notice_id)
        return jsonify({"success": True, "comments": comments})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# =====================================================
# STATIC FRONTEND SERVING & SECURITY
# =====================================================

@app.get("/api/health")
def health_check():
    """A lightweight endpoint for hosting-platform health checks."""
    return jsonify({
        "status": "ok",
        "ai_configured": bool((os.getenv("GEMINI_API_KEY") or "").strip()),
        "model": get_gemini_model(),
    })


@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/<path:path>")
def frontend_files(path):
    # Security: Explicitly block any request trying to access databases, env files, or source code
    restricted_extensions = (".db", ".env", ".py", ".pyc", ".sqlite", ".sqlite3")
    lower_path = path.lower()
    if any(lower_path.endswith(ext) or f"{ext}/" in lower_path for ext in restricted_extensions) or ".." in path:
        return jsonify({"error": "Access denied"}), 403

    return send_from_directory(BASE_DIR, path)


@app.after_request
def add_no_cache_headers(response):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


if __name__ == "__main__":
    app.run(
        host="0.0.0.0",
        port=int(os.getenv("PORT", "5000")),
        debug=os.getenv("FLASK_DEBUG") == "1",
    )
