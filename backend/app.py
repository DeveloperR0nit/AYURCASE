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
        get_admin_summary,
        get_doctor_dashboard,
        get_doctors_list,
        create_appointment,
        get_appointments,
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
        get_admin_summary,
        get_doctor_dashboard,
        get_doctors_list,
        create_appointment,
        get_appointments,
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



@app.route("/api/patients/<identifier>", methods=["GET"])
def api_patient_detail(identifier):
    """Fetches patient profile, active prescriptions, and case history from database."""
    patient = get_patient_data(identifier)
    if not patient:
        return jsonify({"success": False, "error": "Patient record not found."}), 404

    return jsonify({
        "success": True,
        "patient": patient
    })


@app.route("/api/admin/summary", methods=["GET"])
def api_admin_summary():
    """Returns aggregated hospital and AYUSH clinic summary for administrators."""
    summary = get_admin_summary()
    return jsonify({
        "success": True,
        "summary": summary
    })


# =====================================================
# DOCTORS & APPOINTMENT APIS
# =====================================================

@app.route("/api/doctor-dashboard", methods=["GET"])
def api_doctor_dashboard():
    """Returns current dashboard data for one authenticated practitioner."""
    doctor_id = request.args.get("doctor_id")
    if not doctor_id:
        return jsonify({"success": False, "error": "doctor_id is required."}), 400

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
                doctor_id=doctor_id
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
