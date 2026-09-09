"""
AYURCASE Database Module
Provides SQLite schema setup, connection management, cryptographic password hashing,
and data persistence for Users (Doctors, Patients, Admins), Clinical Cases, and Prescriptions.
"""

import os
import json
import sqlite3
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "ayurcase.db")


def get_db_connection():
    """Returns a SQLite connection with foreign keys enabled, WAL mode, and dict-like row access."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 30000;")
        conn.execute("PRAGMA foreign_keys = ON;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Initializes tables and seeds initial verified credentials if not already present."""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. USERS TABLE (Base Authentication for all roles)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('doctor', 'patient', 'admin')),
            full_name TEXT NOT NULL,
            identifier TEXT,
            phone TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 2. DOCTORS TABLE
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS doctors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            specialization TEXT NOT NULL,
            council_reg_no TEXT NOT NULL,
            qualification TEXT,
            cases_count INTEGER DEFAULT 0,
            status TEXT DEFAULT 'Active',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # 3. PATIENTS TABLE
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS patients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE,
            abha_id TEXT UNIQUE NOT NULL,
            name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            phone TEXT,
            blood_group TEXT,
            prakriti_primary TEXT DEFAULT 'Pitta',
            prakriti_secondary TEXT DEFAULT 'Kapha',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # 4. ADMINS TABLE
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER UNIQUE NOT NULL,
            department TEXT NOT NULL,
            security_code TEXT,
            access_level TEXT DEFAULT 'SuperAdmin',
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # 5. CASES TABLE (Clinical Case Taking)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            patient_name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            chief_complaint TEXT NOT NULL,
            diagnosis TEXT,
            prakriti TEXT,
            status TEXT DEFAULT 'New',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # 6. PRESCRIPTIONS TABLE
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS prescriptions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            case_id INTEGER,
            patient_id INTEGER,
            medicine_name TEXT NOT NULL,
            dosage TEXT NOT NULL,
            timing TEXT NOT NULL,
            anupana TEXT,
            duration TEXT,
            prescribed_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (case_id) REFERENCES cases(id) ON DELETE CASCADE,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE CASCADE
        );
        """
    )

    # 7. AUDIT LOGS TABLE (ABDM & Security Compliance)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            action TEXT NOT NULL,
            details TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # 8. APPOINTMENTS TABLE (Patient Doctor Scheduling)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            doctor_id INTEGER,
            patient_name TEXT NOT NULL,
            doctor_name TEXT NOT NULL,
            appointment_date TEXT NOT NULL,
            appointment_time TEXT NOT NULL,
            consultation_type TEXT DEFAULT 'In-Clinic Consultation',
            symptoms_notes TEXT,
            status TEXT DEFAULT 'Confirmed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
            FOREIGN KEY (doctor_id) REFERENCES doctors(id) ON DELETE SET NULL
        );
        """
    )

        # 9. UNIVERSAL APP STORAGE (Key-Value Store in SQLite)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS app_storage (
            storage_key TEXT PRIMARY KEY,
            storage_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 10. USER PREFERENCES (Theme, Layout, Display Settings)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            preference_key TEXT NOT NULL,
            preference_value TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, preference_key)
        );
        """
    )

    # 11. STUDY & EDUCATIONAL PROGRESS (Learning Modules, Wishlist, Completed Items)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS study_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            module_key TEXT NOT NULL,
            progress_data TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(user_id, module_key)
        );
        """
    )

    # 12. USER SESSIONS TABLE (Active sessions tracked in SQLite)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_sessions (
            session_token TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            user_data TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )

    # Ensure case_date column exists in cases table
    cursor.execute("PRAGMA table_info(cases);")
    case_cols = [col[1] for col in cursor.fetchall()]
    if "case_date" not in case_cols:
        cursor.execute("ALTER TABLE cases ADD COLUMN case_date TEXT;")

    conn.commit()

    # Seed Default Accounts if empty
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_default_data(cursor, conn)
    else:
        # If database already has users, ensure initial appointments exist
        cursor.execute("SELECT COUNT(*) FROM appointments;")
        if cursor.fetchone()[0] == 0:
            seed_initial_appointments(cursor, conn)

    
    seed_default_cases(cursor, conn)
    conn.close()


def seed_default_cases(cursor, conn):
    """Seeds default cases (matching script.js defaultcases) into cases table if not present."""
    default_cases_data = [
        ("Rahul Sharma", 32, "Male", "Chronic headache", "14/8/2026", "Active", "Vataja Shiroroga", "Vata-Pitta"),
        ("Priya Das", 27, "Female", "Digestive discomfort", "16/8/2026", "Follow-up", "Agnimandya (Digestive impairment)", "Pitta-Kapha"),
        ("Ankit Roy", 41, "Male", "Sleep disturbance", "24/8/2026", "New", "Anidra (Insomnia)", "Vata-Kapha"),
        ("Sneha Mukherjee", 36, "Female", "Joint discomfort", "27/8/2026", "Active", "Sandhigata Vata", "Vataja"),
    ]
    for c in default_cases_data:
        cursor.execute("SELECT id FROM cases WHERE patient_name = ? LIMIT 1;", (c[0],))
        if not cursor.fetchone():
            cursor.execute(
                """
                INSERT INTO cases (patient_name, age, gender, chief_complaint, case_date, status, diagnosis, prakriti)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                c
            )
    conn.commit()

def seed_initial_appointments(cursor, conn):
    """Seeds initial appointments matching doctor dashboard follow-ups."""
    cursor.execute("SELECT id FROM doctors LIMIT 1;")
    doc_row = cursor.fetchone()
    doc_id = doc_row[0] if doc_row else 1

    cursor.execute("SELECT id FROM patients LIMIT 1;")
    pat_row = cursor.fetchone()
    pat_id = pat_row[0] if pat_row else 1

    initial_appointments = [
        (pat_id, doc_id, "Rahul Sharma", "Dr. Arindam Sen", "2026-08-31", "10:30 AM", "In-Clinic Consultation", "Follow-up consultation", "Confirmed"),
        (None, doc_id, "Priya Das", "Dr. Arindam Sen", "2026-09-01", "11:15 AM", "In-Clinic Consultation", "Progress assessment", "Confirmed"),
        (None, doc_id, "Sneha Mukherjee", "Dr. Arindam Sen", "2026-09-03", "04:00 PM", "Tele-AYUSH Consultation", "Case review", "Confirmed"),
    ]
    for apt in initial_appointments:
        cursor.execute(
            """
            INSERT INTO appointments (patient_id, doctor_id, patient_name, doctor_name, appointment_date, appointment_time, consultation_type, symptoms_notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            apt,
        )
    conn.commit()


def seed_default_data(cursor, conn):
    """Seeds default Doctors, Patients, Admins, Cases, and Prescriptions."""
    # 1. Doctor: Dr. Arindam Sen
    doc1_hash = generate_password_hash("ayur2026")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
        VALUES (?, ?, 'doctor', 'Dr. Arindam Sen', 'AYUSH-WB-2018-0941', '+91 98301 23456');
        """,
        ("dr.sen@ayurcase.com", doc1_hash),
    )
    doc1_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO doctors (user_id, specialization, council_reg_no, qualification, cases_count, status)
        VALUES (?, 'Kayachikitsa (Internal Medicine)', 'AYUSH-WB-2018-0941', 'BAMS, MD (Ayu)', 142, 'Active Online');
        """,
        (doc1_id,),
    )

    # 2. Doctor 2: Dr. Priyadarshini Rao
    doc2_hash = generate_password_hash("ayur2026")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
        VALUES (?, ?, 'doctor', 'Dr. Priyadarshini Rao', 'AYUSH-KA-2019-1120', '+91 98450 78901');
        """,
        ("dr.rao@ayurcase.com", doc2_hash),
    )
    doc2_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO doctors (user_id, specialization, council_reg_no, qualification, cases_count, status)
        VALUES (?, 'Panchakarma Specialist', 'AYUSH-KA-2019-1120', 'BAMS, MS (Ayu)', 98, 'In Consultation');
        """,
        (doc2_id,),
    )

    # 3. Patient: Rohit Sharma
    patient_hash = generate_password_hash("patient123")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
        VALUES (?, ?, 'patient', 'Rohit Sharma', 'ABHA-9182-4410', '+91 98765 43210');
        """,
        ("patient@ayurcase.com", patient_hash),
    )
    pat_user_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO patients (user_id, abha_id, name, age, gender, phone, blood_group, prakriti_primary, prakriti_secondary)
        VALUES (?, 'ABHA-9182-4410', 'Rohit Sharma', 34, 'Male', '+91 98765 43210', 'B+', 'Pitta', 'Kapha');
        """,
        (pat_user_id,),
    )
    patient_db_id = cursor.lastrowid

    # 4. Admin: Rajesh Varma
    admin_hash = generate_password_hash("admin123")
    cursor.execute(
        """
        INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
        VALUES (?, ?, 'admin', 'Rajesh Varma', 'ADM-KOL-001', '+91 94330 11223');
        """,
        ("admin@ayurcase.gov.in", admin_hash),
    )
    admin_user_id = cursor.lastrowid
    cursor.execute(
        """
        INSERT INTO admins (user_id, department, security_code, access_level)
        VALUES (?, 'Chief Hospital Administration', 'SEC-8821', 'SuperAdmin');
        """,
        (admin_user_id,),
    )

    # 5. Default Clinical Cases
    cursor.execute(
        """
        INSERT INTO cases (patient_id, doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status)
        VALUES (?, ?, 'Rohit Sharma', 34, 'Male', 'Chronic digestive distress, acid reflux, occasional insomnia', 'Amlapitta with Vata Anubandha', 'Pitta-Kapha', 'Active');
        """,
        (patient_db_id, doc1_id),
    )
    case1_id = cursor.lastrowid

    cursor.execute(
        """
        INSERT INTO cases (patient_id, doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status)
        VALUES (NULL, ?, 'Ananya Roy', 28, 'Female', 'Joint stiffness in knees and lower back stiffness in the mornings', 'Sandhigata Vata', 'Vata-Pitta', 'Follow-up');
        """,
        (doc1_id,),
    )

    cursor.execute(
        """
        INSERT INTO cases (patient_id, doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status)
        VALUES (NULL, ?, 'Vikramaditya Das', 45, 'Male', 'General lethargy, heaviness in chest after meals, mild skin rash', 'Kaphaja Grahani', 'Kapha-Pitta', 'New');
        """,
        (doc1_id,),
    )

    # 6. Prescriptions for Rohit Sharma
    prescriptions = [
        (case1_id, patient_db_id, "Ashwagandha Churna", "3g (Half teaspoon)", "Twice daily (Post meal)", "Warm Milk", "30 Days"),
        (case1_id, patient_db_id, "Triphala Kwatha", "20 ml", "Bedtime", "Lukewarm Water", "15 Days"),
        (case1_id, patient_db_id, "Brahmi Vati", "1 Tablet", "Morning (Post breakfast)", "Honey / Water", "21 Days"),
    ]
    for p in prescriptions:
        cursor.execute(
            """
            INSERT INTO prescriptions (case_id, patient_id, medicine_name, dosage, timing, anupana, duration)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            p,
        )

    # 7. Initial Audit Log
    cursor.execute(
        """
        INSERT INTO audit_logs (user_id, action, details)
        VALUES (?, 'SYSTEM_INIT', 'AYURCASE SQLite database initialized with verified credentials.');
        """,
        (admin_user_id,),
    )

    conn.commit()


def authenticate_user(username_or_identifier, password, role=None):
    """
    Authenticates a user against the database with password hash checking.
    Accepts email/username OR identifier (like ABHA ID or Council ID).
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    query = """
        SELECT * FROM users
        WHERE (LOWER(username) = LOWER(?) OR LOWER(identifier) = LOWER(?) OR LOWER(full_name) = LOWER(?))
    """
    params = [username_or_identifier.strip(), username_or_identifier.strip(), username_or_identifier.strip()]

    if role:
        query += " AND role = ?"
        params.append(role)

    cursor.execute(query, params)
    user = cursor.fetchone()

    if not user:
        conn.close()
        return None

    pw_matches = check_password_hash(user["password_hash"], password)

    if pw_matches:
        # Fetch additional role details
        role_details = {}
        if user["role"] == "doctor":
            cursor.execute("SELECT * FROM doctors WHERE user_id = ?", (user["id"],))
            doc = cursor.fetchone()
            if doc:
                role_details = dict(doc)
        elif user["role"] == "patient":
            cursor.execute("SELECT * FROM patients WHERE user_id = ?", (user["id"],))
            pat = cursor.fetchone()
            if pat:
                role_details = dict(pat)
        elif user["role"] == "admin":
            cursor.execute("SELECT * FROM admins WHERE user_id = ?", (user["id"],))
            adm = cursor.fetchone()
            if adm:
                role_details = dict(adm)

        # Log sign in
        cursor.execute(
            "INSERT INTO audit_logs (user_id, action, details) VALUES (?, 'USER_LOGIN', ?)",
            (user["id"], f"Successful login for {user['role']} ({user['username']})"),
        )
        conn.commit()
        conn.close()

        return {
            "id": user["id"],
            "username": user["username"],
            "role": user["role"],
            "full_name": user["full_name"],
            "identifier": user["identifier"],
            "phone": user["phone"],
            "details": role_details,
        }

    conn.close()
    return None


def register_patient(data):
    """
    Registers a new patient in the SQLite database.
    Creates user record with role 'patient' and associated patient demographic record.
    Returns a dict with success status, error (if any), and created user dictionary.
    """
    conn = get_db_connection()
    cursor = conn.cursor()

    name = (data.get("name") or data.get("full_name") or "").strip()
    username = (data.get("username") or data.get("email") or "").strip()
    password = data.get("password") or ""
    abha_id = (data.get("abha_id") or data.get("abhaId") or "").strip()
    phone = (data.get("phone") or "").strip()
    age = data.get("age") or 30
    gender = data.get("gender") or "Other"
    blood_group = data.get("blood_group") or data.get("bloodGroup") or "O+"
    prakriti_primary = data.get("prakriti_primary") or data.get("prakriti") or "Pitta"
    prakriti_secondary = data.get("prakriti_secondary") or "Kapha"

    if not name or not username or not password:
        conn.close()
        return {"success": False, "error": "Full Name, Email/Username, and Password are required."}

    # Format or generate ABHA ID if missing
    if not abha_id:
        import random
        abha_id = f"ABHA-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"

    # Check if username or abha_id already exists
    cursor.execute(
        "SELECT id FROM users WHERE LOWER(username) = LOWER(?) OR LOWER(identifier) = LOWER(?);",
        (username, abha_id)
    )
    if cursor.fetchone():
        conn.close()
        return {"success": False, "error": "A user with this Email/Username or ABHA ID already exists."}

    cursor.execute("SELECT id FROM patients WHERE LOWER(abha_id) = LOWER(?);", (abha_id,))
    if cursor.fetchone():
        conn.close()
        return {"success": False, "error": "A patient with this ABHA ID is already registered."}

    password_hash = generate_password_hash(password)

    try:
        # Insert into users
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
            VALUES (?, ?, 'patient', ?, ?, ?);
            """,
            (username, password_hash, name, abha_id, phone),
        )
        user_id = cursor.lastrowid

        # Insert into patients
        cursor.execute(
            """
            INSERT INTO patients (user_id, abha_id, name, age, gender, phone, blood_group, prakriti_primary, prakriti_secondary)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, abha_id, name, age, gender, phone, blood_group, prakriti_primary, prakriti_secondary),
        )
        patient_db_id = cursor.lastrowid

        # Audit log
        cursor.execute(
            "INSERT INTO audit_logs (user_id, action, details) VALUES (?, 'PATIENT_REGISTERED', ?);",
            (user_id, f"Self-registration of patient {name} (ABHA: {abha_id})"),
        )

        conn.commit()

        user_info = {
            "id": user_id,
            "username": username,
            "role": "patient",
            "full_name": name,
            "identifier": abha_id,
            "phone": phone,
            "details": {
                "id": patient_db_id,
                "user_id": user_id,
                "name": name,
                "abha_id": abha_id,
                "age": age,
                "gender": gender,
                "phone": phone,
                "blood_group": blood_group,
                "prakriti_primary": prakriti_primary,
                "prakriti_secondary": prakriti_secondary
            }
        }
        conn.close()
        return {"success": True, "user": user_info, "message": f"Welcome, {name}! Your patient account has been created."}

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"success": False, "error": str(e)}


def get_all_cases():
    """Retrieves all clinical cases directly from SQLite, formatted for frontend and script.js."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT c.*, u.full_name as doctor_name
        FROM cases c
        LEFT JOIN users u ON c.doctor_id = u.id
        ORDER BY c.id DESC;
        """
    )
    rows = cursor.fetchall()
    cases = []
    for r in rows:
        d = dict(r)
        c_date = d.get("case_date") or (d["created_at"].split(" ")[0] if d.get("created_at") else "Today")
        cases.append({
            "id": d["id"],
            "name": d["patient_name"],
            "patient_name": d["patient_name"],
            "age": d["age"],
            "gender": d["gender"],
            "complaint": d["chief_complaint"],
            "chief_complaint": d["chief_complaint"],
            "diagnosis": d.get("diagnosis") or "Under AYUSH Evaluation",
            "prakriti": d.get("prakriti") or "General",
            "date": c_date,
            "case_date": c_date,
            "status": d.get("status") or "Active",
            "doctor_name": d.get("doctor_name") or "Dr. Arindam Sen",
            "created_at": d.get("created_at")
        })
    conn.close()
    return cases


def add_case(data):
    """Inserts a new clinical case into SQLite and returns the complete case object."""
    conn = get_db_connection()
    cursor = conn.cursor()

    p_name = data.get("name") or data.get("patient_name") or "Unknown Patient"
    age = data.get("age") or 30
    gender = data.get("gender") or "Other"
    complaint = data.get("complaint") or data.get("chief_complaint") or "General AYUSH Consultation"
    diagnosis = data.get("diagnosis") or "Under AYUSH Evaluation"
    prakriti = data.get("prakriti") or "General"
    status = data.get("status") or "New"
    case_date = data.get("date") or data.get("case_date") or None

    cursor.execute(
        """
        INSERT INTO cases (patient_name, age, gender, chief_complaint, diagnosis, prakriti, status, case_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (p_name, age, gender, complaint, diagnosis, prakriti, status, case_date),
    )
    new_id = cursor.lastrowid
    conn.commit()

    cursor.execute("SELECT * FROM cases WHERE id = ?;", (new_id,))
    row = dict(cursor.fetchone())
    conn.close()

    c_date = row.get("case_date") or (row["created_at"].split(" ")[0] if row.get("created_at") else "Today")
    return {
        "id": row["id"],
        "name": row["patient_name"],
        "patient_name": row["patient_name"],
        "age": row["age"],
        "gender": row["gender"],
        "complaint": row["chief_complaint"],
        "chief_complaint": row["chief_complaint"],
        "diagnosis": row.get("diagnosis") or "Under AYUSH Evaluation",
        "prakriti": row.get("prakriti") or "General",
        "date": c_date,
        "case_date": c_date,
        "status": row.get("status") or "New",
        "created_at": row.get("created_at")
    }


def delete_case(id_or_name):
    """Deletes a clinical case from SQLite by ID or patient name."""
    conn = get_db_connection()
    cursor = conn.cursor()
    deleted = False

    try:
        case_id = int(id_or_name)
        cursor.execute("DELETE FROM cases WHERE id = ?;", (case_id,))
        if cursor.rowcount > 0:
            deleted = True
    except (ValueError, TypeError):
        pass

    if not deleted:
        cursor.execute(
            "DELETE FROM cases WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));",
            (str(id_or_name).strip(),)
        )
        if cursor.rowcount > 0:
            deleted = True

    conn.commit()
    conn.close()
    return deleted


def sync_cases_batch(cases_list):
    """Merges an array of cases from client into SQLite cases table and returns all cases."""
    if not isinstance(cases_list, list):
        return get_all_cases()

    conn = get_db_connection()
    cursor = conn.cursor()

    for c in cases_list:
        p_name = c.get("name") or c.get("patient_name")
        if not p_name:
            continue
        age = c.get("age") or 30
        gender = c.get("gender") or "Other"
        complaint = c.get("complaint") or c.get("chief_complaint") or "General Consultation"
        diagnosis = c.get("diagnosis") or "Under AYUSH Evaluation"
        prakriti = c.get("prakriti") or "General"
        status = c.get("status") or "Active"
        case_date = c.get("date") or c.get("case_date")

        cursor.execute("SELECT id FROM cases WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (p_name.strip(),))
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE cases
                SET age = ?, gender = ?, chief_complaint = ?, status = ?, case_date = COALESCE(?, case_date)
                WHERE id = ?;
                """,
                (age, gender, complaint, status, case_date, existing[0]),
            )
        else:
            cursor.execute(
                """
                INSERT INTO cases (patient_name, age, gender, chief_complaint, diagnosis, prakriti, status, case_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (p_name, age, gender, complaint, diagnosis, prakriti, status, case_date),
            )

    conn.commit()
    conn.close()
    return get_all_cases()


# =====================================================
# UNIVERSAL APP STORAGE HELPERS (SQLite Key-Value Store)
# =====================================================

def save_storage_key(key, value):
    """Persists a key-value pair in SQLite app_storage table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    str_val = value if isinstance(value, str) else json.dumps(value)
    cursor.execute(
        """
        INSERT INTO app_storage (storage_key, storage_value, updated_at)
        VALUES (?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(storage_key) DO UPDATE SET
            storage_value = excluded.storage_value,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (str(key), str_val),
    )
    conn.commit()
    conn.close()
    return True


def get_storage_key(key):
    """Retrieves a single value from app_storage."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT storage_value FROM app_storage WHERE storage_key = ?;", (str(key),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    val = row[0]
    try:
        return json.loads(val)
    except Exception:
        return val


def get_all_storage():
    """Retrieves all key-value pairs stored in SQLite app_storage."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT storage_key, storage_value FROM app_storage;")
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        val = r["storage_value"]
        try:
            result[r["storage_key"]] = json.loads(val)
        except Exception:
            result[r["storage_key"]] = val
    return result


def sync_storage_batch(data_dict):
    """Batch synchronizes a dictionary of {key: value} into SQLite and returns full storage state."""
    if not isinstance(data_dict, dict):
        return get_all_storage()

    conn = get_db_connection()
    cursor = conn.cursor()
    for k, v in data_dict.items():
        if v is None:
            continue
        str_val = v if isinstance(v, str) else json.dumps(v)
        cursor.execute(
            """
            INSERT INTO app_storage (storage_key, storage_value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(storage_key) DO UPDATE SET
                storage_value = excluded.storage_value,
                updated_at = CURRENT_TIMESTAMP;
            """,
            (str(k), str_val),
        )
    conn.commit()
    conn.close()
    return get_all_storage()


# =====================================================
# USER PREFERENCES HELPERS (Theme & UI Settings in SQLite)
# =====================================================

def save_user_preference(user_id, key, value):
    """Persists a user preference into SQLite user_preferences table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    cursor.execute(
        """
        INSERT INTO user_preferences (user_id, preference_key, preference_value, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, preference_key) DO UPDATE SET
            preference_value = excluded.preference_value,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (uid, str(key), str(value)),
    )
    conn.commit()
    conn.close()
    return True


def get_user_preferences(user_id=None):
    """Retrieves user preferences from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    cursor.execute("SELECT preference_key, preference_value FROM user_preferences WHERE user_id = ?;", (uid,))
    rows = cursor.fetchall()
    conn.close()
    return {r["preference_key"]: r["preference_value"] for r in rows}


# =====================================================
# STUDY PROGRESS & LEARNING IN SQLITE
# =====================================================

def save_study_progress(user_id, module_key, data):
    """Persists study progress, bookmarks, and completions in SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    str_data = data if isinstance(data, str) else json.dumps(data)
    cursor.execute(
        """
        INSERT INTO study_progress (user_id, module_key, progress_data, updated_at)
        VALUES (?, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(user_id, module_key) DO UPDATE SET
            progress_data = excluded.progress_data,
            updated_at = CURRENT_TIMESTAMP;
        """,
        (uid, str(module_key), str_data),
    )
    conn.commit()
    conn.close()
    return True


def get_study_progress(user_id=None):
    """Retrieves study progress from SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    uid = user_id or 1
    cursor.execute("SELECT module_key, progress_data FROM study_progress WHERE user_id = ?;", (uid,))
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for r in rows:
        try:
            result[r["module_key"]] = json.loads(r["progress_data"])
        except Exception:
            result[r["module_key"]] = r["progress_data"]
    return result


# =====================================================
# USER SESSIONS IN SQLITE
# =====================================================

def create_user_session(token, user_id, role, user_data, expires_at=None):
    """Stores a user login session in SQLite user_sessions table."""
    conn = get_db_connection()
    cursor = conn.cursor()
    str_data = user_data if isinstance(user_data, str) else json.dumps(user_data)
    cursor.execute(
        """
        INSERT INTO user_sessions (session_token, user_id, role, user_data, expires_at)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(session_token) DO UPDATE SET
            user_data = excluded.user_data;
        """,
        (str(token), int(user_id), str(role), str_data, expires_at),
    )
    conn.commit()
    conn.close()
    return True


def validate_user_session(token):
    """Validates session token against SQLite."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_sessions WHERE session_token = ?;", (str(token),))
    row = cursor.fetchone()
    conn.close()
    if not row:
        return None
    d = dict(row)
    try:
        d["user_data"] = json.loads(d["user_data"])
    except Exception:
        pass
    return d


def delete_user_session(token):
    """Deletes a session from SQLite on logout."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_sessions WHERE session_token = ?;", (str(token),))
    deleted = cursor.rowcount > 0
    conn.commit()
    conn.close()
    return deleted

def get_patient_data(abha_or_user_id):
    """Fetches patient profile, active prescriptions, and cases."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT p.*, u.username as email
        FROM patients p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.abha_id = ? OR p.user_id = ?
        """,
        (str(abha_or_user_id), str(abha_or_user_id)),
    )
    patient = cursor.fetchone()

    if not patient:
        conn.close()
        return None

    pat_dict = dict(patient)

    # Fetch Prescriptions
    cursor.execute(
        "SELECT * FROM prescriptions WHERE patient_id = ? ORDER BY prescribed_date DESC",
        (pat_dict["id"],),
    )
    pat_dict["prescriptions"] = [dict(r) for r in cursor.fetchall()]

    # Fetch Cases
    cursor.execute(
        "SELECT * FROM cases WHERE patient_id = ? ORDER BY created_at DESC",
        (pat_dict["id"],),
    )
    pat_dict["cases"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return pat_dict


def get_admin_summary():
    """Fetches summary counts for doctors, patients, cases, and logs."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM doctors")
    doc_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients")
    pat_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM cases")
    case_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT d.*, u.full_name, u.username, u.identifier
        FROM doctors d
        JOIN users u ON d.user_id = u.id
        """
    )
    doctors = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        """
        SELECT a.*, u.username
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT 10
        """
    )
    logs = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "doctor_count": doc_count,
        "patient_count": pat_count,
        "case_count": case_count,
        "doctors": doctors,
        "audit_logs": logs,
    }


# =====================================================
# DOCTORS & APPOINTMENTS DATA HELPERS
# =====================================================

def get_doctors_list():
    """Returns a list of all active AYUSH doctors with their specialization and availability."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id AS doctor_id, d.user_id, u.full_name, u.username, u.identifier,
               d.specialization, d.qualification, d.cases_count, d.status
        FROM doctors d
        JOIN users u ON d.user_id = u.id
        WHERE d.status LIKE '%Active%' OR d.status LIKE '%Online%' OR d.status LIKE '%Consultation%'
        ORDER BY d.id ASC;
        """
    )
    doctors = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return doctors


def create_appointment(patient_name, doctor_name, appointment_date, appointment_time,
                       consultation_type="In-Clinic Consultation", symptoms_notes="",
                       patient_id=None, doctor_id=None):
    """Creates and persists an appointment in the database."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # Resolve doctor_id if missing or check validity
        if doctor_id:
            cursor.execute("SELECT id FROM doctors WHERE id = ?;", (doctor_id,))
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM doctors WHERE user_id = ?;", (doctor_id,))
                d_row = cursor.fetchone()
                doctor_id = d_row[0] if d_row else None

        if not doctor_id and doctor_name:
            cursor.execute(
                """
                SELECT d.id FROM doctors d
                JOIN users u ON d.user_id = u.id
                WHERE u.full_name LIKE ? OR u.full_name = ?
                LIMIT 1;
                """,
                (f"%{doctor_name}%", doctor_name)
            )
            row = cursor.fetchone()
            if row:
                doctor_id = row[0]

        # Resolve patient_id: if passed patient_id is users.id, resolve to patients.id!
        if patient_id:
            cursor.execute("SELECT id FROM patients WHERE id = ?;", (patient_id,))
            if not cursor.fetchone():
                cursor.execute("SELECT id FROM patients WHERE user_id = ?;", (patient_id,))
                p_row = cursor.fetchone()
                patient_id = p_row[0] if p_row else None

        if not patient_id and patient_name:
            cursor.execute(
                """
                SELECT id FROM patients
                WHERE name LIKE ? OR name = ?
                LIMIT 1;
                """,
                (f"%{patient_name}%", patient_name)
            )
            row = cursor.fetchone()
            if row:
                patient_id = row[0]

        cursor.execute(
            """
            INSERT INTO appointments (
                patient_id, doctor_id, patient_name, doctor_name,
                appointment_date, appointment_time, consultation_type,
                symptoms_notes, status
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Confirmed');
            """,
            (
                patient_id,
                doctor_id,
                patient_name,
                doctor_name,
                appointment_date,
                appointment_time,
                consultation_type,
                symptoms_notes,
            ),
        )
        appointment_id = cursor.lastrowid

        # Safely record in audit logs
        try:
            audit_uid = None
            if patient_id:
                cursor.execute("SELECT user_id FROM patients WHERE id = ?;", (patient_id,))
                u_row = cursor.fetchone()
                if u_row:
                    audit_uid = u_row[0]
            cursor.execute(
                """
                INSERT INTO audit_logs (user_id, action, details)
                VALUES (?, 'APPOINTMENT_SCHEDULED', ?);
                """,
                (
                    audit_uid,
                    f"Appointment #{appointment_id} scheduled for {patient_name} with {doctor_name} on {appointment_date} at {appointment_time}",
                ),
            )
        except Exception as log_err:
            print("Audit log notice:", log_err)

        conn.commit()

        cursor.execute("SELECT * FROM appointments WHERE id = ?", (appointment_id,))
        new_apt = dict(cursor.fetchone())
        return new_apt
    finally:
        conn.close()


def get_appointments(doctor_id=None, doctor_name=None, patient_id=None, patient_name=None):
    """Retrieves appointments with optional filtering."""
    conn = get_db_connection()
    cursor = conn.cursor()

    query = "SELECT * FROM appointments WHERE 1=1"
    params = []

    if doctor_id:
        query += " AND (doctor_id = ? OR doctor_id IN (SELECT id FROM doctors WHERE user_id = ?))"
        params.extend([doctor_id, doctor_id])
    if doctor_name:
        query += " AND (doctor_name LIKE ? OR doctor_name = ?)"
        params.extend([f"%{doctor_name}%", doctor_name])
    if patient_id:
        query += " AND (patient_id = ? OR patient_id IN (SELECT id FROM patients WHERE user_id = ?))"
        params.extend([patient_id, patient_id])
    if patient_name:
        query += " AND (patient_name LIKE ? OR patient_name = ?)"
        params.extend([f"%{patient_name}%", patient_name])

    # Dates are stored as ISO (YYYY-MM-DD) strings, so lexical ordering also
    # produces chronological ordering.  This lets dashboards show the next
    # appointment rather than merely the most recently created one.
    query += " ORDER BY appointment_date ASC, id DESC;"
    cursor.execute(query, params)
    appointments = [dict(row) for row in cursor.fetchall()]
    conn.close()
    return appointments



if __name__ == "__main__":
    init_db()
    print("AYURCASE Database successfully initialized at:", DB_PATH)

