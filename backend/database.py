"""
AYURCASE Database Module
Provides SQLite schema setup, connection management, cryptographic password hashing,
and data persistence for Users (Doctors, Patients, Admins), Clinical Cases, and Prescriptions.
"""

import os
import json
import time
import sqlite3
from datetime import date, timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# Set AYURCASE_DB_PATH to a mounted persistent-disk location in production.
# The default keeps local development behavior unchanged.
DB_PATH = os.path.abspath(
    os.getenv("AYURCASE_DB_PATH") or os.path.join(BASE_DIR, "ayurcase.db")
)

DB_DIRECTORY = os.path.dirname(DB_PATH)
if DB_DIRECTORY:
    os.makedirs(DB_DIRECTORY, exist_ok=True)


def get_db_connection():
    """Returns a SQLite connection with foreign keys enabled, WAL mode, and dict-like row access."""
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    try:
        conn.execute("PRAGMA journal_mode = DELETE;")
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
            prakriti_primary TEXT DEFAULT NULL,
            prakriti_secondary TEXT DEFAULT NULL,
            emergency_contact TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
        );
        """
    )
    try:
        cursor.execute("ALTER TABLE patients ADD COLUMN emergency_contact TEXT;")
    except Exception:
        pass

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

    # 13. NOTICES TABLE (Hospital Administration Notices, Meetings, Orders)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notices (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            notice_type TEXT DEFAULT 'General',
            priority TEXT DEFAULT 'Normal',
            posted_by TEXT DEFAULT 'Hospital Administration',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 14. NOTICE COMMENTS TABLE (Doctor Comments / Acknowledgements on Notices)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS notice_comments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            notice_id INTEGER NOT NULL,
            doctor_id INTEGER,
            author_name TEXT NOT NULL,
            author_role TEXT DEFAULT 'doctor',
            comment_text TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (notice_id) REFERENCES notices(id) ON DELETE CASCADE,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # 15. EMAIL LOGS TABLE (Welcome & Clinical Delivery Tracking)
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

    # Seed sample notices if empty
    cursor.execute("SELECT COUNT(*) FROM notices;")
    if cursor.fetchone()[0] == 0:
        cursor.execute(
            """
            INSERT INTO notices (title, content, notice_type, priority, posted_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', '-2 days'))
            """,
            (
                "Monthly AYUSH Clinical Review & Case Conference",
                "All practitioners are requested to attend the monthly clinical review meeting this Friday at 4:30 PM in Conference Room B / Online Hybrid link. Agenda includes ABDM integration review and complex case discussions.",
                "Meeting",
                "Important",
                "Rajesh Varma (Chief Hospital Admin)"
            )
        )
        first_notice_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO notice_comments (notice_id, author_name, author_role, comment_text, created_at)
            VALUES (?, ?, ?, ?, datetime('now', '-1 day'))
            """,
            (
                first_notice_id,
                "Dr. Arindam Sen",
                "doctor",
                "Noted. I will present the chronic arthritis case study during the second half of the review."
            )
        )
        cursor.execute(
            """
            INSERT INTO notices (title, content, notice_type, priority, posted_by, created_at)
            VALUES (?, ?, ?, ?, ?, datetime('now', '-1 day'))
            """,
            (
                "Hospital Order: Standardized Prakriti & Case Documentation",
                "Per clinical governance directive #2026-09, all new patient admissions must have full Prakriti constitutional assessment and pulse diagnosis recorded within 24 hours of first consultation.",
                "Order",
                "Urgent",
                "Chief Medical Superintendent & Admin"
            )
        )
        second_notice_id = cursor.lastrowid
        cursor.execute(
            """
            INSERT INTO notice_comments (notice_id, author_name, author_role, comment_text, created_at)
            VALUES (?, ?, ?, ?, datetime('now', '-12 hours'))
            """,
            (
                second_notice_id,
                "Dr. Rajesh Sharma",
                "doctor",
                "Acknowledged. The Kaya Chikitsa department has updated its clinical workflow accordingly."
            )
        )

    # Ensure case_date column exists in cases table
    cursor.execute("PRAGMA table_info(cases);")
    case_cols = [col[1] for col in cursor.fetchall()]
    if "case_date" not in case_cols:
        cursor.execute("ALTER TABLE cases ADD COLUMN case_date TEXT;")

    # 15. EMERGENCY CASES TABLE (Acute Triage / Atyayika Chikitsa)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS emergency_cases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT NOT NULL,
            age INTEGER,
            gender TEXT,
            doctor_id INTEGER,
            doctor_name TEXT,
            issue TEXT NOT NULL,
            triage_level TEXT DEFAULT 'Emergency',
            bed_number TEXT,
            status TEXT DEFAULT 'Under Immediate Care',
            admitted_time TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 16. ARTICLES TABLE (Clinical Articles / Research published by doctors)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS articles (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            author TEXT,
            category TEXT,
            minutes INTEGER DEFAULT 15,
            source TEXT,
            excerpt TEXT,
            content TEXT,
            icon TEXT DEFAULT 'fa-solid fa-file-lines',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        """
    )

    # 17. LAB REPORTS TABLE (Sugar, Pressure, Hemoglobin, Clinical Notes & Email Status)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS lab_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_id INTEGER,
            patient_name TEXT NOT NULL,
            patient_email TEXT,
            doctor_id INTEGER,
            doctor_name TEXT,
            sugar TEXT NOT NULL,
            pressure TEXT NOT NULL,
            hemoglobin TEXT NOT NULL,
            notes TEXT,
            status TEXT DEFAULT 'Completed',
            email_status TEXT DEFAULT 'Sent',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (patient_id) REFERENCES patients(id) ON DELETE SET NULL,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    # 18. AI REVIEWS TABLE (Doctor clinical ratings & comments on AI answers and patient queries)
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS ai_reviews (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            doctor_id INTEGER,
            doctor_name TEXT NOT NULL,
            patient_question TEXT NOT NULL,
            ai_answer TEXT NOT NULL,
            rating INTEGER NOT NULL,
            comment TEXT,
            status TEXT DEFAULT 'Reviewed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (doctor_id) REFERENCES users(id) ON DELETE SET NULL
        );
        """
    )

    conn.commit()

    # Seed Default Accounts if empty
    cursor.execute("SELECT COUNT(*) FROM users;")
    user_count = cursor.fetchone()[0]

    if user_count == 0:
        seed_default_data(cursor, conn)

    # seed_default_data creates the original two accounts. Run this for both
    # fresh and existing databases so all four practitioner accounts are
    # always available in the sign-in selector and booking directory.
    ensure_default_doctors(cursor, conn)
    ensure_default_admin(cursor, conn)
    ensure_default_patient(cursor, conn)
    remove_demo_patient_directory(cursor, conn)
    remove_legacy_arindam_follow_up_fixtures(cursor, conn)
    remove_legacy_case_fixtures(cursor, conn)
    ensure_default_emergency_cases(cursor, conn)
    try:
        cursor.execute("ALTER TABLE ai_reviews ADD COLUMN patient_name TEXT;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE ai_reviews ADD COLUMN reviewed_at TIMESTAMP;")
    except Exception:
        pass
    try:
        cursor.execute("ALTER TABLE articles ADD COLUMN image_url TEXT;")
    except Exception:
        pass
    ensure_upcoming_ai_reviews(cursor, conn)
    conn.close()
    seed_recent_clinical_history()


def ensure_default_doctors(cursor, conn):
    """Adds the four supported demo practitioners without changing existing accounts."""
    doctors = [
        ("dr.sen@ayurcase.com", "Dr. Arindam Sen", "AYUSH-WB-2018-0941", "+91 98301 23456", "Kayachikitsa (Internal Medicine)", "BAMS, MD (Ayu)", 142, "Active Online"),
        ("dr.rao@ayurcase.com", "Dr. Priyadarshini Rao", "AYUSH-KA-2019-1120", "+91 98450 78901", "Panchakarma Specialist", "BAMS, MD (Panchakarma)", 98, "In Consultation"),
        ("dr.kapoor@ayurcase.com", "Dr. Meera Kapoor", "AYUSH-DL-2020-1846", "+91 98110 45218", "Prasuti Tantra & Stri Roga", "BAMS, MD (Prasuti & Stri Roga)", 116, "Active Online"),
        ("dr.bose@ayurcase.com", "Dr. Kunal Bose", "AYUSH-WB-2021-0673", "+91 99031 67104", "Kaumarbhritya (Ayurvedic Pediatrics)", "BAMS, MD (Kaumarbhritya)", 87, "Active Online"),
    ]
    for username, name, council, phone, specialty, qualification, cases_count, status in doctors:
        cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
        user = cursor.fetchone()
        if user:
            user_id = user[0]
        else:
            cursor.execute(
                "INSERT INTO users (username, password_hash, role, full_name, identifier, phone) VALUES (?, ?, 'doctor', ?, ?, ?)",
                (username, generate_password_hash("ayur2026"), name, council, phone),
            )
            user_id = cursor.lastrowid
        cursor.execute("SELECT id FROM doctors WHERE user_id = ?", (user_id,))
        doc_row = cursor.fetchone()
        if not doc_row:
            cursor.execute(
                "INSERT INTO doctors (user_id, specialization, council_reg_no, qualification, cases_count, status) VALUES (?, ?, ?, ?, ?, ?)",
                (user_id, specialty, council, qualification, cases_count, status),
            )
        else:
            cursor.execute(
                "UPDATE doctors SET specialization = ?, qualification = ? WHERE id = ?",
                (specialty, qualification, doc_row[0]),
            )
    conn.commit()


def ensure_default_admin(cursor, conn):
    """Ensures the built-in clinic administrator account exists on every database."""
    username = "admin@ayurcase.gov.in"
    cursor.execute("SELECT id FROM users WHERE username = ?", (username,))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
    else:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, full_name, identifier, phone) VALUES (?, ?, 'admin', ?, ?, ?)",
            (
                username,
                generate_password_hash("admin123"),
                "Rajesh Varma",
                "ADM-KOL-001",
                "+91 94330 11223",
            ),
        )
        user_id = cursor.lastrowid

    cursor.execute("SELECT id FROM admins WHERE user_id = ?", (user_id,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO admins (user_id, department, security_code, access_level) VALUES (?, ?, ?, ?)",
            (user_id, "Chief Hospital Administration", "SEC-8821", "SuperAdmin"),
        )
    conn.commit()


def ensure_default_patient(cursor, conn):
    """Adds or ensures the default demo patient account with unassessed Prakriti (NULL / Not set)."""
    username = "patient@ayurcase.com"
    abha_id = "ABHA-9182-4410"
    name = "Rohit Sharma"
    cursor.execute("SELECT id FROM users WHERE username = ? OR identifier = ?", (username, abha_id))
    user = cursor.fetchone()
    if user:
        user_id = user[0]
    else:
        cursor.execute(
            "INSERT INTO users (username, password_hash, role, full_name, identifier, phone) VALUES (?, ?, 'patient', ?, ?, ?)",
            (
                username,
                generate_password_hash("patient123"),
                name,
                abha_id,
                "+91 98765 43210",
            ),
        )
        user_id = cursor.lastrowid

    cursor.execute("SELECT id FROM patients WHERE user_id = ? OR abha_id = ?", (user_id, abha_id))
    pat = cursor.fetchone()
    if not pat:
        cursor.execute(
            """
            INSERT INTO patients (user_id, abha_id, name, age, gender, phone, blood_group, prakriti_primary, prakriti_secondary)
            VALUES (?, ?, ?, 34, 'Male', '+91 98765 43210', 'B+', NULL, NULL)
            """,
            (user_id, abha_id, name),
        )
    conn.commit()


def remove_follow_up_appointments(cursor, conn):
    """Removes sample follow-up appointment records so follow-up only shows real appointments."""
    cursor.execute(
        "DELETE FROM appointments WHERE patient_name IN ('Aarav Mukherjee', 'Priya Nair', 'Kavita Patel', 'Meenakshi Sundaram');"
    )
    conn.commit()


def ensure_default_emergency_cases(cursor, conn):
    """Seeds authentic AYUSH emergency cases if table is empty."""
    cursor.execute("SELECT COUNT(*) FROM emergency_cases;")
    if cursor.fetchone()[0] == 0:
        cursor.execute("SELECT d.id, u.full_name FROM doctors d JOIN users u ON d.user_id = u.id;")
        doc_map = {r["full_name"]: r["id"] for r in cursor.fetchall()}

        doc_sen_id = doc_map.get("Dr. Arindam Sen", 1)
        doc_rao_id = doc_map.get("Dr. Priyadarshini Rao", 2)
        doc_bose_id = doc_map.get("Dr. Kunal Bose", 4)

        emergencies = [
            (
                "Rajeshwar Rao",
                58,
                "Male",
                doc_sen_id,
                "Dr. Arindam Sen",
                "Teevra Shula & Hritshula (Acute severe epigastric & retrosternal distress)",
                "Emergency (Red)",
                "Bay #E-01",
                "Under Immediate Care",
                "Today 05:45 AM"
            ),
            (
                "Sunita Deshmukh",
                42,
                "Female",
                doc_rao_id,
                "Dr. Priyadarshini Rao",
                "Vatavyadhi Atyayika (Acute severe sciatica / Gridhrasi spasms with immobilizing pain)",
                "Urgent (Amber)",
                "Bay #E-02",
                "Under Immediate Care",
                "Today 06:10 AM"
            ),
            (
                "Harish Chandra Verma",
                64,
                "Male",
                doc_bose_id,
                "Dr. Kunal Bose",
                "Sadyo Vrana & Raktasrava (Acute bleeding anorectal fissure & trauma)",
                "Emergency (Red)",
                "Suite #01",
                "Under Immediate Care",
                "Today 06:25 AM"
            ),
        ]
        for name, age, gender, doc_id, doc_name, issue, triage, bed, status, adm_time in emergencies:
            cursor.execute(
                """
                INSERT INTO emergency_cases (patient_name, age, gender, doctor_id, doctor_name, issue, triage_level, bed_number, status, admitted_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (name, age, gender, doc_id, doc_name, issue, triage, bed, status, adm_time)
            )
        conn.commit()


def get_emergency_cases():
    """Returns all active emergency triage cases."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, patient_name, age, gender, doctor_id, doctor_name, issue, triage_level, bed_number, status, admitted_time, created_at
        FROM emergency_cases
        WHERE status != 'Discharged'
        ORDER BY id ASC
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    conn.close()
    return rows


def remove_demo_patient_directory(cursor, conn):
    """Removes only the old AYURCASE sample patients and their linked activity.

    The administrator directory must reflect real registrations and bookings,
    not generated names. The username pattern is exclusive to the temporary
    profiles previously added for the local demo.
    """
    demo_user_query = """
        SELECT u.id
        FROM users u
        WHERE u.username LIKE 'demo.patient.%@ayurcase.test'
           OR u.username = 'patient@ayurcase.com'
    """
    cursor.execute(f"DELETE FROM appointments WHERE patient_id IN (SELECT id FROM patients WHERE user_id IN ({demo_user_query}))")
    cursor.execute(f"DELETE FROM cases WHERE patient_id IN (SELECT id FROM patients WHERE user_id IN ({demo_user_query}))")
    cursor.execute(f"DELETE FROM prescriptions WHERE patient_id IN (SELECT id FROM patients WHERE user_id IN ({demo_user_query}))")
    cursor.execute(f"DELETE FROM users WHERE id IN ({demo_user_query})")
    conn.commit()


def ensure_demo_patient_directory(cursor, conn):
    """Creates a one-time, realistic patient directory for each demo practitioner.

    These accounts are clearly demo data for the local AYURCASE experience and
    are inserted idempotently, so starting the server again never duplicates
    patients or appointment slots.
    """
    cursor.execute(
        """
        SELECT d.id, d.user_id, u.full_name
        FROM doctors d
        JOIN users u ON u.id = d.user_id
        ORDER BY d.id ASC
        LIMIT 4
        """
    )
    doctors = [dict(row) for row in cursor.fetchall()]
    if not doctors:
        return

    first_names = [
        "Aarav", "Ananya", "Vihaan", "Ishita", "Arjun", "Kavya",
        "Ritwik", "Meera", "Aditya", "Nandini", "Samar", "Diya",
        "Rohan", "Tanvi", "Kiran", "Ayesha", "Dev", "Saanvi",
        "Neel", "Charu", "Manav", "Ira", "Yash", "Pallavi",
    ]
    family_names = ["Mukherjee", "Iyer", "Kapoor", "Chatterjee"]
    blood_groups = ["O+", "A+", "B+", "AB+", "O-", "A-", "B-"]
    constitutions = [("Vata", "Pitta"), ("Pitta", "Kapha"), ("Kapha", "Vata")]
    concerns = [
        "Digestive wellness review", "Sleep and stress follow-up",
        "Seasonal allergy consultation", "Joint mobility assessment",
        "Diet and lifestyle consultation", "Headache management review",
    ]
    appointment_times = ["09:00 AM", "09:30 AM", "10:15 AM", "11:00 AM", "11:45 AM", "12:30 PM", "02:00 PM", "02:45 PM"]
    today = date.today()
    patient_password = generate_password_hash("patient123")

    for doctor_index, doctor in enumerate(doctors):
        surname = family_names[doctor_index % len(family_names)]
        for patient_index, first_name in enumerate(first_names):
            name = f"{first_name} {surname}"
            username = f"demo.patient.{doctor_index + 1}.{patient_index + 1}@ayurcase.test"
            abha_id = f"ABHA-73{doctor_index + 1}0-{1000 + patient_index}"
            phone = f"+91 900{doctor_index + 1}{patient_index + 1:06d}"
            age = 24 + ((patient_index * 3 + doctor_index * 5) % 42)
            gender = "Female" if patient_index % 2 else "Male"
            primary, secondary = constitutions[patient_index % len(constitutions)]

            cursor.execute("SELECT id FROM patients WHERE abha_id = ?", (abha_id,))
            patient_row = cursor.fetchone()
            if patient_row:
                patient_id = patient_row[0]
            else:
                cursor.execute(
                    """
                    INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
                    VALUES (?, ?, 'patient', ?, ?, ?)
                    """,
                    (username, patient_password, name, abha_id, phone),
                )
                user_id = cursor.lastrowid
                cursor.execute(
                    """
                    INSERT INTO patients (user_id, abha_id, name, age, gender, phone, blood_group, prakriti_primary, prakriti_secondary)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (user_id, abha_id, name, age, gender, phone, blood_groups[patient_index % len(blood_groups)], primary, secondary),
                )
                patient_id = cursor.lastrowid

            cursor.execute(
                "SELECT id FROM appointments WHERE doctor_id = ? AND patient_id = ? LIMIT 1",
                (doctor["id"], patient_id),
            )
            if not cursor.fetchone():
                appointment_day = today + timedelta(days=patient_index % 12)
                cursor.execute(
                    """
                    INSERT INTO appointments (
                        patient_id, doctor_id, patient_name, doctor_name, appointment_date,
                        appointment_time, consultation_type, symptoms_notes, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_id,
                        doctor["id"],
                        name,
                        doctor["full_name"],
                        appointment_day.isoformat(),
                        appointment_times[patient_index % len(appointment_times)],
                        "Tele-consultation" if patient_index % 5 == 0 else "In-Clinic Consultation",
                        concerns[patient_index % len(concerns)],
                        "Confirmed" if patient_index % 7 else "Follow-up",
                    ),
                )

            # Give every demo patient a clinical case as well, so the admin
            # total and practitioner case dashboards reflect real activity.
            cursor.execute(
                "SELECT id FROM cases WHERE doctor_id = ? AND patient_id = ? LIMIT 1",
                (doctor["user_id"], patient_id),
            )
            if not cursor.fetchone():
                cursor.execute(
                    """
                    INSERT INTO cases (
                        patient_id, doctor_id, patient_name, age, gender, chief_complaint,
                        diagnosis, prakriti, status, case_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_id,
                        doctor["user_id"],
                        name,
                        age,
                        gender,
                        concerns[patient_index % len(concerns)],
                        "Lifestyle and AYUSH care plan",
                        f"{primary}-{secondary}",
                        "Active",
                        (today - timedelta(days=patient_index % 15)).isoformat(),
                    ),
                )
    conn.commit()


def remove_legacy_arindam_follow_up_fixtures(cursor, conn):
    """Removes only the previous hard-coded/template follow-ups for Dr. Sen."""
    cursor.execute(
        """
        SELECT d.id
        FROM doctors d
        JOIN users u ON u.id = d.user_id
        WHERE u.full_name = 'Dr. Arindam Sen'
        """
    )
    row = cursor.fetchone()
    if not row:
        return

    cursor.execute(
        """
        DELETE FROM appointments
        WHERE doctor_id = ?
          AND (
                (patient_name = 'Rahul Sharma' AND symptoms_notes = 'Follow-up consultation')
             OR (patient_name = 'Priya Das' AND symptoms_notes = 'Progress assessment')
             OR (patient_name = 'Sneha Mukherjee' AND symptoms_notes = 'Case review')
             OR symptoms_notes IN (
                    'Pitta acid reflux & indigestion consultation',
                    'Workflow verification test consultation',
                    'Database migration verification follow-up'
                )
          )
        """,
        (row[0],),
    )
    conn.commit()


def remove_legacy_case_fixtures(cursor, conn):
    """Removes the former sample cases so case history contains real clinician work only."""
    fixtures = [
        ("Rohit Sharma", "Chronic digestive distress, acid reflux, occasional insomnia"),
        ("Ananya Roy", "Joint stiffness in knees and lower back stiffness in the mornings"),
        ("Vikramaditya Das", "General lethargy, heaviness in chest after meals, mild skin rash"),
        ("Rahul Sharma", "Chronic headache"),
        ("Priya Das", "Digestive discomfort"),
        ("Ankit Roy", "Sleep disturbance"),
        ("Sneha Mukherjee", "Joint discomfort"),
    ]
    cursor.executemany(
        "DELETE FROM cases WHERE patient_name = ? AND chief_complaint = ?",
        fixtures,
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
        VALUES (?, 'Panchakarma Specialist', 'AYUSH-KA-2019-1120', 'BAMS, MD (Panchakarma)', 98, 'In Consultation');
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
        VALUES (?, 'ABHA-9182-4410', 'Rohit Sharma', 34, 'Male', '+91 98765 43210', 'B+', NULL, NULL);
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
        VALUES (?, ?, 'Rohit Sharma', 34, 'Male', 'Chronic digestive distress, acid reflux, occasional insomnia', 'Amlapitta with Vata Anubandha', NULL, 'Active');
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

    ident = username_or_identifier.strip()
    digits = "".join(filter(str.isdigit, ident))
    phone_suf = f"%{digits[-10:]}" if len(digits) >= 10 else ident
    query = """
        SELECT * FROM users
        WHERE (
            LOWER(username) = LOWER(?) 
            OR LOWER(identifier) = LOWER(?) 
            OR LOWER(full_name) = LOWER(?)
            OR LOWER(phone) = LOWER(?)
            OR (length(?) >= 10 AND replace(replace(phone, ' ', ''), '-', '') LIKE ?)
        )
    """
    params = [ident, ident, ident, ident, digits, phone_suf]

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
    age_raw = data.get("age")
    try:
        age = int(age_raw) if age_raw is not None and str(age_raw).strip() != "" else None
    except (ValueError, TypeError):
        age = None
    gender = (data.get("gender") or "").strip()
    blood_group = (data.get("blood_group") or data.get("bloodGroup") or "").strip()
    prakriti_raw = (data.get("prakriti_primary") or data.get("prakriti") or "").strip()
    if not prakriti_raw or prakriti_raw == "Not set":
        prakriti_primary = None
        prakriti_secondary = None
    elif "-" in prakriti_raw:
        parts = [p.strip() for p in prakriti_raw.split("-") if p.strip()]
        prakriti_primary = parts[0] if len(parts) > 0 else None
        prakriti_secondary = parts[1] if len(parts) > 1 else None
    else:
        prakriti_primary = prakriti_raw
        prakriti_secondary = (data.get("prakriti_secondary") or "").strip() or None

    if not name or not username or not password or not phone:
        conn.close()
        return {"success": False, "error": "Full Name, Email/Username, Password, and Phone Number are required."}

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

        # Dispatch welcome email asynchronously with all user signup details
        try:
            try:
                from email_service import send_welcome_email_async
            except ImportError:
                from backend.email_service import send_welcome_email_async
            send_welcome_email_async(data, user_info)
        except Exception as email_dispatch_err:
            print(f"[REGISTER PATIENT] Failed to dispatch welcome email: {email_dispatch_err}")

        conn.close()
        return {"success": True, "user": user_info, "message": f"Welcome, {name}! Your patient account has been created."}

    except Exception as e:
        conn.rollback()
        conn.close()
        return {"success": False, "error": str(e)}


def _resolve_doctor_user_id(cursor, doctor_id):
    """Normalizes a doctors-table ID (or a doctor user ID) to the user ID stored by cases."""
    if not doctor_id:
        return None
    cursor.execute("SELECT user_id FROM doctors WHERE id = ?", (doctor_id,))
    row = cursor.fetchone()
    if row:
        return row[0]
    cursor.execute("SELECT id FROM users WHERE id = ? AND role = 'doctor'", (doctor_id,))
    row = cursor.fetchone()
    return row[0] if row else None


def get_all_cases(doctor_id=None):
    """Retrieves cases, optionally limited to the logged-in practitioner's own cases."""
    conn = get_db_connection()
    cursor = conn.cursor()
    doctor_user_id = _resolve_doctor_user_id(cursor, doctor_id)

    if doctor_id and not doctor_user_id:
        conn.close()
        return []

    query = """
        SELECT c.*, u.full_name as doctor_name
        FROM cases c
        LEFT JOIN users u ON c.doctor_id = u.id
    """
    params = []
    if doctor_user_id:
        query += " WHERE c.doctor_id = ?"
        params.append(doctor_user_id)
    query += " ORDER BY c.id DESC;"
    cursor.execute(
        query,
        params,
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
            "doctor_id": d.get("doctor_id"),
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
    doctor_id = data.get("doctor_id")
    doctor_user_id = _resolve_doctor_user_id(cursor, doctor_id)
    if doctor_id and not doctor_user_id:
        conn.close()
        raise ValueError("The practitioner account for this case could not be found.")

    cursor.execute(
        """
        INSERT INTO cases (patient_id, doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status, case_date)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """,
        (None, doctor_user_id, p_name, age, gender, complaint, diagnosis, prakriti, status, case_date),
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
        "doctor_id": row.get("doctor_id"),
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


def sync_cases_batch(cases_list, doctor_id=None):
    """Merges a doctor's client-side cases without touching other practitioners' records."""
    if not isinstance(cases_list, list):
        return get_all_cases(doctor_id)

    conn = get_db_connection()
    cursor = conn.cursor()
    doctor_user_id = _resolve_doctor_user_id(cursor, doctor_id)
    if doctor_id and not doctor_user_id:
        conn.close()
        return []

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

        if doctor_user_id:
            cursor.execute(
                "SELECT id FROM cases WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?)) AND doctor_id = ?;",
                (p_name.strip(), doctor_user_id),
            )
        else:
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
                INSERT INTO cases (doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status, case_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
                """,
                (doctor_user_id, p_name, age, gender, complaint, diagnosis, prakriti, status, case_date),
            )

    conn.commit()
    conn.close()
    return get_all_cases(doctor_id)


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
    """Fetches patient profile, email, active prescriptions, appointments, and cases."""
    conn = get_db_connection()
    cursor = conn.cursor()

    target = str(abha_or_user_id or "").strip()
    cursor.execute(
        """
        SELECT p.*, u.username as email
        FROM patients p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.abha_id = ? 
           OR p.user_id = ? 
           OR p.id = ? 
           OR LOWER(TRIM(p.name)) = LOWER(?)
           OR p.phone = ?
        ORDER BY (p.abha_id = ?) DESC, (p.id = ?) DESC, (LOWER(TRIM(p.name)) = LOWER(?)) DESC
        LIMIT 1;
        """,
        (target, target, target, target, target, target, target, target),
    )
    patient = cursor.fetchone()

    if not patient:
        # Fallback: check appointments or cases if not in patients table yet
        cursor.execute(
            """
            SELECT patient_name as name, symptoms_notes, appointment_date, appointment_time, created_at, consultation_type
            FROM appointments
            WHERE LOWER(TRIM(patient_name)) = LOWER(?) OR patient_id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (target, target),
        )
        app_row = cursor.fetchone()

        cursor.execute(
            """
            SELECT patient_name as name, age, gender, chief_complaint, diagnosis, prakriti, created_at
            FROM cases
            WHERE LOWER(TRIM(patient_name)) = LOWER(?) OR id = ?
            ORDER BY id DESC LIMIT 1
            """,
            (target, target),
        )
        case_row = cursor.fetchone()

        if app_row or case_row:
            name = case_row["name"] if case_row else app_row["name"]
            age = case_row["age"] if (case_row and case_row["age"] is not None) else None
            gender = case_row["gender"] if (case_row and case_row["gender"]) else None
            created_at = case_row["created_at"] if case_row else app_row["created_at"]
            prakriti_val = case_row["prakriti"] if case_row else None
            
            pat_dict = {
                "id": None,
                "user_id": None,
                "abha_id": None,
                "name": name,
                "age": age,
                "gender": gender,
                "phone": None,
                "blood_group": None,
                "prakriti_primary": prakriti_val,
                "prakriti_secondary": None,
                "created_at": created_at,
                "email": None,
                "is_walkin": True,
                "prescriptions": [],
                "cases": [],
                "appointments": [],
            }
        else:
            conn.close()
            return None
    else:
        pat_dict = dict(patient)
        pat_dict["is_walkin"] = False if (pat_dict.get("blood_group") or pat_dict.get("phone") or pat_dict.get("user_id") or pat_dict.get("email")) else True

    prim = pat_dict.get("prakriti_primary")
    sec = pat_dict.get("prakriti_secondary")
    if prim and prim not in ("Not set", "None"):
        pat_dict["prakriti"] = f"{prim}-{sec}" if (sec and sec not in ("Not set", "None")) else prim
    else:
        pat_dict["prakriti"] = "Not set"

    # Fetch Prescriptions
    if pat_dict.get("id"):
        cursor.execute(
            "SELECT * FROM prescriptions WHERE patient_id = ? ORDER BY prescribed_date DESC",
            (pat_dict["id"],),
        )
        pat_dict["prescriptions"] = [dict(r) for r in cursor.fetchall()]
    else:
        pat_dict["prescriptions"] = []

    # Fetch Cases (matching by patient_id or patient name)
    pat_name = pat_dict.get("name") or target
    if pat_dict.get("id"):
        cursor.execute(
            """
            SELECT c.*, u.full_name as doctor_name
            FROM cases c
            LEFT JOIN users u ON c.doctor_id = u.id
            WHERE c.patient_id = ? OR LOWER(TRIM(c.patient_name)) = LOWER(?)
            ORDER BY c.created_at DESC
            """,
            (pat_dict["id"], pat_name),
        )
    else:
        cursor.execute(
            """
            SELECT c.*, u.full_name as doctor_name
            FROM cases c
            LEFT JOIN users u ON c.doctor_id = u.id
            WHERE LOWER(TRIM(c.patient_name)) = LOWER(?)
            ORDER BY c.created_at DESC
            """,
            (pat_name,),
        )
    pat_dict["cases"] = [dict(r) for r in cursor.fetchall()]

    # Fetch Appointments (matching by patient_id or patient name)
    if pat_dict.get("id"):
        cursor.execute(
            "SELECT * FROM appointments WHERE patient_id = ? OR LOWER(TRIM(patient_name)) = LOWER(?) ORDER BY appointment_date DESC, appointment_time DESC",
            (pat_dict["id"], pat_name),
        )
    else:
        cursor.execute(
            "SELECT * FROM appointments WHERE LOWER(TRIM(patient_name)) = LOWER(?) ORDER BY appointment_date DESC, appointment_time DESC",
            (pat_name,),
        )
    pat_dict["appointments"] = [dict(r) for r in cursor.fetchall()]

    conn.close()
    return pat_dict


def get_all_registered_patients():
    """
    Fetches all registered patients from SQLite with their associated
    user account information, demographics, emergency contact, ABHA ID,
    and live counts of clinical cases, appointments, and prescriptions.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT 
            p.id,
            p.user_id,
            p.abha_id,
            p.name,
            p.age,
            p.gender,
            p.phone,
            p.blood_group,
            p.prakriti_primary,
            p.prakriti_secondary,
            p.emergency_contact,
            p.created_at,
            u.username as email,
            u.full_name as user_full_name,
            (SELECT COUNT(*) FROM cases c WHERE c.patient_id = p.id OR LOWER(TRIM(c.patient_name)) = LOWER(TRIM(p.name))) as cases_count,
            (SELECT COUNT(*) FROM appointments a WHERE a.patient_id = p.id OR LOWER(TRIM(a.patient_name)) = LOWER(TRIM(p.name))) as appointments_count,
            (SELECT COUNT(*) FROM prescriptions rx WHERE rx.patient_id = p.id) as prescriptions_count
        FROM patients p
        LEFT JOIN users u ON p.user_id = u.id
        ORDER BY p.id DESC
        """
    )
    rows = [dict(r) for r in cursor.fetchall()]
    for r in rows:
        prim = r.get("prakriti_primary")
        sec = r.get("prakriti_secondary")
        if prim and prim not in ("Not set", "None"):
            r["prakriti"] = f"{prim}-{sec}" if (sec and sec not in ("Not set", "None")) else prim
        else:
            r["prakriti"] = "Not set"
    conn.close()
    return rows



def update_patient_profile(identifier, data):
    """
    Updates patient profile fields (name, age, blood_group, phone, prakriti, emergency_contact, abha_id).
    Strictly ignores/disallows modifications to email and gender.
    Persists changes across patients and users tables, and updates related records.
    """
    if not identifier or not data or not isinstance(data, dict):
        return None

    conn = get_db_connection()
    cursor = conn.cursor()

    target = str(identifier or "").strip()
    cursor.execute(
        """
        SELECT p.*, u.username as email, u.id as u_id
        FROM patients p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.abha_id = ? 
           OR p.user_id = ? 
           OR p.id = ? 
           OR LOWER(TRIM(p.name)) = LOWER(?)
           OR p.phone = ?
        ORDER BY (p.abha_id = ?) DESC, (p.id = ?) DESC, (LOWER(TRIM(p.name)) = LOWER(?)) DESC
        LIMIT 1;
        """,
        (target, target, target, target, target, target, target, target),
    )
    patient = cursor.fetchone()

    # Extract allowed fields (strictly ignore email and gender)
    name = (data.get("name") or data.get("full_name"))
    if name is not None:
        name = str(name).strip() or None

    age = data.get("age")
    age_val = None
    if age is not None and str(age).strip() != "":
        try:
            age_val = int(age)
        except (ValueError, TypeError):
            age_val = None

    blood_group = (data.get("blood_group") or data.get("bloodGroup"))
    if blood_group is not None:
        blood_group = str(blood_group).strip() or None

    phone = data.get("phone")
    if phone is not None:
        phone = str(phone).strip() or None

    prakriti = (data.get("prakriti") or data.get("prakriti_primary"))
    prakriti_primary = None
    prakriti_secondary = None
    if prakriti is not None and str(prakriti).strip() and str(prakriti).strip() != "Not set":
        parts = [p.strip() for p in str(prakriti).split("-") if p.strip()]
        prakriti_primary = parts[0] if len(parts) > 0 else None
        prakriti_secondary = parts[1] if len(parts) > 1 else None

    emergency_contact = (data.get("emergency_contact") or data.get("emergencyContact"))
    if emergency_contact is not None:
        emergency_contact = str(emergency_contact).strip() or None

    abha_id = (data.get("abha_id") or data.get("abhaId"))
    if abha_id is not None:
        abha_id = str(abha_id).strip() or None

    if patient:
        pat_id = patient["id"]
        user_id = patient["user_id"] or patient["u_id"]

        updates = []
        params = []
        if ("name" in data or "full_name" in data) and name:
            updates.append("name = ?")
            params.append(name)
        if "age" in data:
            updates.append("age = ?")
            params.append(age_val)
        if "blood_group" in data or "bloodGroup" in data:
            updates.append("blood_group = ?")
            params.append(blood_group)
        if "phone" in data:
            updates.append("phone = ?")
            params.append(phone)
        if "prakriti" in data or "prakriti_primary" in data:
            updates.append("prakriti_primary = ?")
            params.append(prakriti_primary)
            updates.append("prakriti_secondary = ?")
            params.append(prakriti_secondary)
        if "emergency_contact" in data or "emergencyContact" in data:
            updates.append("emergency_contact = ?")
            params.append(emergency_contact)
        if ("abha_id" in data or "abhaId" in data) and abha_id:
            updates.append("abha_id = ?")
            params.append(abha_id)

        if updates:
            params.append(pat_id)
            cursor.execute(f"UPDATE patients SET {', '.join(updates)} WHERE id = ?", tuple(params))

        user_updates = []
        user_params = []
        if ("name" in data or "full_name" in data) and name:
            user_updates.append("full_name = ?")
            user_params.append(name)
        if "phone" in data:
            user_updates.append("phone = ?")
            user_params.append(phone)
        if ("abha_id" in data or "abhaId" in data) and abha_id:
            user_updates.append("identifier = ?")
            user_params.append(abha_id)

        if user_updates and user_id:
            user_params.append(user_id)
            cursor.execute(f"UPDATE users SET {', '.join(user_updates)} WHERE id = ?", tuple(user_params))

        if ("name" in data or "full_name" in data) and name:
            cursor.execute("UPDATE cases SET patient_name = ? WHERE patient_id = ?", (name, pat_id))
            cursor.execute("UPDATE appointments SET patient_name = ? WHERE patient_id = ?", (name, pat_id))

        conn.commit()
        conn.close()
        return get_patient_data(abha_id or pat_id)

    else:
        # Check if user exists in users table
        cursor.execute(
            "SELECT * FROM users WHERE identifier = ? OR id = ? OR username = ? LIMIT 1",
            (target, target, target),
        )
        user = cursor.fetchone()
        if user:
            user_id = user["id"]
            abha_code = abha_id or user["identifier"] or f"ABHA-{user_id:04d}-0001"
            pat_name = name or user["full_name"] or "Patient"
            cursor.execute(
                """
                INSERT INTO patients (user_id, abha_id, name, age, phone, blood_group, prakriti_primary, prakriti_secondary, emergency_contact)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (user_id, abha_code, pat_name, age_val, phone or user["phone"], blood_group, prakriti_primary, prakriti_secondary, emergency_contact),
            )
            pat_id = cursor.lastrowid
            if name or phone or abha_id:
                cursor.execute(
                    "UPDATE users SET full_name = COALESCE(?, full_name), phone = COALESCE(?, phone), identifier = COALESCE(?, identifier) WHERE id = ?",
                    (name, phone, abha_id, user_id),
                )
            conn.commit()
            conn.close()
            return get_patient_data(pat_id)

    conn.close()
    return None


def delete_patient_account(identifier):
    """
    Permanently deletes a patient account and all associated records from SQLite database.
    Removes records from patients, users, user_sessions, prescriptions, appointments, cases.
    Returns dictionary with deleted user/patient details on success, or None on failure.
    """
    if not identifier:
        return None

    conn = get_db_connection()
    cursor = conn.cursor()
    target = str(identifier).strip()

    # Find patient and user details before deletion
    cursor.execute(
        """
        SELECT p.id as patient_id, p.user_id, p.abha_id, p.name as patient_name, p.phone as patient_phone,
               u.id as u_id, u.full_name as user_full_name, u.identifier, u.username, u.role
        FROM patients p
        LEFT JOIN users u ON p.user_id = u.id
        WHERE p.abha_id = ? 
           OR p.user_id = ? 
           OR p.id = ? 
           OR LOWER(TRIM(p.name)) = LOWER(TRIM(?))
           OR u.identifier = ? 
           OR u.username = ?
           OR LOWER(TRIM(u.full_name)) = LOWER(TRIM(?))
        LIMIT 1;
        """,
        (target, target, target, target, target, target, target),
    )
    row = cursor.fetchone()

    patient_id = None
    user_id = None
    deleted_info = {
        "name": "Valued Patient",
        "email": "",
        "abha_id": target,
        "phone": ""
    }

    if row:
        patient_id = row["patient_id"]
        user_id = row["user_id"] or row["u_id"]
        name_val = row["patient_name"] or row["user_full_name"] or ""
        email_val = row["identifier"] if ("@" in str(row["identifier"] or "")) else (row["username"] if ("@" in str(row["username"] or "")) else "")
        if name_val:
            deleted_info["name"] = name_val
        if email_val:
            deleted_info["email"] = email_val
        if row["abha_id"]:
            deleted_info["abha_id"] = row["abha_id"]
        if row["patient_phone"]:
            deleted_info["phone"] = row["patient_phone"]
    else:
        cursor.execute(
            "SELECT id, full_name, username, identifier, phone FROM users WHERE id = ? OR identifier = ? OR username = ? OR LOWER(TRIM(full_name)) = LOWER(TRIM(?)) LIMIT 1",
            (target, target, target, target)
        )
        user_row = cursor.fetchone()
        if user_row:
            user_id = user_row["id"]
            if user_row["full_name"]:
                deleted_info["name"] = user_row["full_name"]
            email_val = user_row["identifier"] if ("@" in str(user_row["identifier"] or "")) else (user_row["username"] if ("@" in str(user_row["username"] or "")) else "")
            if email_val:
                deleted_info["email"] = email_val
            if user_row["phone"]:
                deleted_info["phone"] = user_row["phone"]

    # Check if any orphaned appointments exist for this target name
    cursor.execute(
        "SELECT id, patient_name FROM appointments WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?)) LIMIT 1;",
        (target,)
    )
    apt_orphan_row = cursor.fetchone()
    has_orphaned_appointments = bool(apt_orphan_row)

    if not patient_id and not user_id and not has_orphaned_appointments:
        conn.close()
        return None

    if apt_orphan_row and deleted_info.get("name") == "Valued Patient":
        deleted_info["name"] = apt_orphan_row["patient_name"]

    # If email wasn't found in DB row, but target itself looks like an email:
    if not deleted_info.get("email") and "@" in target:
        deleted_info["email"] = target

    names_to_delete = {target}
    if deleted_info.get("name") and deleted_info["name"] != "Valued Patient":
        names_to_delete.add(deleted_info["name"])

    if patient_id:
        cursor.execute("DELETE FROM prescriptions WHERE patient_id = ?", (patient_id,))
        cursor.execute("DELETE FROM cases WHERE patient_id = ?", (patient_id,))
        cursor.execute("DELETE FROM patients WHERE id = ?", (patient_id,))
        cursor.execute("DELETE FROM appointments WHERE patient_id = ?", (patient_id,))

    # Also delete appointments matching patient name to prevent orphaned appointments
    for n in names_to_delete:
        if n and len(n.strip()) > 1:
            cursor.execute("DELETE FROM appointments WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?))", (n.strip(),))

    if user_id:
        cursor.execute("DELETE FROM user_sessions WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM user_preferences WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM study_progress WHERE user_id = ?", (user_id,))
        cursor.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # Synchronize app_storage cached appointments
    try:
        cursor.execute("SELECT storage_value FROM app_storage WHERE storage_key = 'ayurcase_cached_appointments';")
        st_row = cursor.fetchone()
        if st_row and st_row[0]:
            appts = json.loads(st_row[0])
            cleaned = []
            for a in appts:
                a_name = (a.get("patient_name") or "").strip().lower()
                a_pid = str(a.get("patient_id") or "")
                if patient_id and a_pid == str(patient_id):
                    continue
                if any(n.strip().lower() == a_name for n in names_to_delete if n and len(n.strip()) > 1):
                    continue
                cleaned.append(a)
            cursor.execute(
                "UPDATE app_storage SET storage_value = ?, updated_at = CURRENT_TIMESTAMP WHERE storage_key = 'ayurcase_cached_appointments';",
                (json.dumps(cleaned),)
            )
    except Exception as st_err:
        print("[STORAGE CACHE SYNC NOTICE]:", st_err)

    conn.commit()
    conn.close()

    # Dispatch account deletion confirmation email asynchronously
    if deleted_info.get("email"):
        try:
            try:
                from email_service import send_account_deletion_email_async
            except ImportError:
                from backend.email_service import send_account_deletion_email_async
            send_account_deletion_email_async(deleted_info)
        except Exception as email_dispatch_err:
            print(f"[DELETE PATIENT] Failed to dispatch account deletion email: {email_dispatch_err}")

    return deleted_info


def delete_appointment(appointment_id):
    """
    Deletes an appointment by ID and synchronizes app_storage cache.
    Returns True if deleted, False otherwise.
    """
    if not appointment_id:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT id, patient_name, doctor_name, appointment_date, appointment_time FROM appointments WHERE id = ?;",
            (appointment_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return False

        cursor.execute("DELETE FROM appointments WHERE id = ?;", (appointment_id,))
        conn.commit()

        # Safely log cancellation in audit_logs
        try:
            cursor.execute(
                """
                INSERT INTO audit_logs (action, details)
                VALUES ('APPOINTMENT_CANCELLED', ?);
                """,
                (f"Appointment #{appointment_id} for '{row['patient_name']}' with '{row['doctor_name']}' on {row['appointment_date']} was cancelled/deleted.",),
            )
            conn.commit()
        except Exception:
            pass

        # Sync app_storage cache
        try:
            cursor.execute("SELECT storage_value FROM app_storage WHERE storage_key = 'ayurcase_cached_appointments';")
            st_row = cursor.fetchone()
            if st_row and st_row[0]:
                appts = json.loads(st_row[0])
                cleaned = [a for a in appts if str(a.get("id")) != str(appointment_id)]
                cursor.execute(
                    "UPDATE app_storage SET storage_value = ?, updated_at = CURRENT_TIMESTAMP WHERE storage_key = 'ayurcase_cached_appointments';",
                    (json.dumps(cleaned),)
                )
                conn.commit()
        except Exception:
            pass

        conn.close()
        return True
    except Exception as e:
        print(f"[DELETE APPOINTMENT ERROR]: {e}")
        conn.close()
        return False


def cancel_appointment_by_patient_name(patient_name):
    """Cancels/removes scheduled appointments and active follow-up cases for a patient by name."""
    if not patient_name:
        return False
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        clean = str(patient_name).strip()
        cursor.execute(
            "SELECT id FROM appointments WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?)) ORDER BY id DESC LIMIT 1;",
            (clean,)
        )
        row = cursor.fetchone()
        conn.close()
        if row:
            return delete_appointment(row[0])
        # Also clean up any pending follow-up case
        conn2 = get_db_connection()
        cur2 = conn2.cursor()
        cur2.execute(
            "UPDATE cases SET outcome = 'Completed' WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?)) AND outcome = 'Follow-up';",
            (clean,)
        )
        conn2.commit()
        conn2.close()
        return True
    except Exception as e:
        print(f"[CANCEL APPOINTMENT BY NAME ERROR]: {e}")
        return False


def get_admin_summary():
    """Fetches summary counts for doctors, patients, cases, and logs."""
    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM doctors")
    doc_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM patients")
    pat_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM users WHERE role = 'patient'")
    portal_pat_count = cursor.fetchone()[0]
    total_pat_count = max(pat_count, portal_pat_count)

    cursor.execute("SELECT COUNT(*) FROM cases")
    case_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM appointments")
    appointment_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT d.*, u.full_name, u.username, u.identifier
        FROM doctors d
        JOIN users u ON d.user_id = u.id
        """
    )
    doctors = [dict(r) for r in cursor.fetchall()]

    # A patient is assigned to a practitioner once they have an appointment
    # or a clinical case with that practitioner.  This is deliberately based
    # on the actual records rather than the old display-only cases_count field.
    for doctor in doctors:
        cursor.execute(
            """
            SELECT COUNT(DISTINCT patient_id)
            FROM (
                SELECT patient_id FROM appointments
                WHERE doctor_id = ? AND patient_id IS NOT NULL
                UNION
                SELECT patient_id FROM cases
                WHERE doctor_id = ? AND patient_id IS NOT NULL
            )
            """,
            (doctor["id"], doctor["user_id"]),
        )
        doctor["registered_patient_count"] = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM appointments WHERE doctor_id = ?",
            (doctor["id"],),
        )
        doctor["appointment_count"] = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT a.*, u.username, u.full_name, u.role
        FROM audit_logs a
        LEFT JOIN users u ON a.user_id = u.id
        ORDER BY a.timestamp DESC
        LIMIT 200
        """
    )
    logs = [dict(r) for r in cursor.fetchall()]

    cursor.execute(
        """
        SELECT activity_type, appointment_id, doctor_id, doctor_name, patient_id, patient_name, patient_age, condition, detail, occurred_at
        FROM (
            SELECT 'Appointment booked' AS activity_type,
                   a.id AS appointment_id,
                   a.doctor_id AS doctor_id,
                   a.doctor_name AS doctor_name,
                   COALESCE(
                       a.patient_id,
                       (SELECT p.id FROM patients p WHERE LOWER(TRIM(p.name)) = LOWER(TRIM(a.patient_name)) ORDER BY (p.user_id IS NOT NULL) DESC, p.id DESC LIMIT 1)
                   ) AS patient_id,
                   a.patient_name AS patient_name,
                   (
                       SELECT p.age FROM patients p 
                       WHERE p.id = a.patient_id OR LOWER(TRIM(p.name)) = LOWER(TRIM(a.patient_name)) 
                       ORDER BY (p.age IS NOT NULL) DESC, (p.user_id IS NOT NULL) DESC, p.id DESC 
                       LIMIT 1
                   ) AS patient_age,
                   COALESCE(
                       (SELECT c.chief_complaint FROM cases c WHERE c.patient_id = a.patient_id ORDER BY c.created_at DESC LIMIT 1),
                       a.symptoms_notes,
                       'Condition not recorded'
                   ) AS condition,
                   'Appointment with ' || a.doctor_name || ' on ' || a.appointment_date || ' at ' || a.appointment_time AS detail,
                   a.created_at AS occurred_at
            FROM appointments a
            WHERE a.status != 'CANCELLED'
            UNION ALL
            SELECT CASE
                     WHEN l.action = 'PATIENT_REGISTERED' THEN 'Patient registered'
                     ELSE 'Patient signed in'
                   END AS activity_type,
                   NULL AS appointment_id,
                   NULL AS doctor_id,
                   (SELECT u2.full_name FROM cases c2 JOIN users u2 ON c2.doctor_id = u2.id WHERE c2.patient_id = p.id ORDER BY c2.created_at DESC LIMIT 1) AS doctor_name,
                   p.id AS patient_id,
                   COALESCE(p.name, u.full_name, 'Patient') AS patient_name,
                   p.age AS patient_age,
                   COALESCE((SELECT c.chief_complaint FROM cases c WHERE c.patient_id = p.id ORDER BY c.created_at DESC LIMIT 1), 'Condition not recorded') AS condition,
                   l.details AS detail,
                   l.timestamp AS occurred_at
            FROM audit_logs l
            JOIN users u ON u.id = l.user_id AND u.role = 'patient'
            LEFT JOIN patients p ON p.user_id = u.id
            WHERE l.action IN ('PATIENT_REGISTERED', 'USER_LOGIN')
        )
        ORDER BY occurred_at DESC
        LIMIT 50
        """
    )
    patient_activity = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT COUNT(*) FROM emergency_cases WHERE status != 'Discharged'")
    emergency_count = cursor.fetchone()[0]

    cursor.execute(
        """
        SELECT id, patient_name, age, gender, doctor_id, doctor_name, issue, triage_level, bed_number, status, admitted_time, created_at
        FROM emergency_cases
        WHERE status != 'Discharged'
        ORDER BY id ASC
        """
    )
    emergency_cases = [dict(r) for r in cursor.fetchall()]

    conn.close()

    return {
        "doctor_count": doc_count,
        "patient_count": total_pat_count,
        "portal_patient_count": portal_pat_count,
        "case_count": case_count,
        "appointment_count": appointment_count,
        "emergency_count": emergency_count,
        "emergency_cases": emergency_cases,
        "doctors": doctors,
        "audit_logs": logs,
        "patient_activity": patient_activity,
    }


def get_admin_doctor_patients(doctor_id):
    """Returns one practitioner's registered patients, follow-up visits, and appointment schedule for the admin console."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT d.id AS doctor_id, d.user_id, d.specialization, d.council_reg_no,
                   d.qualification, d.status, u.full_name, u.phone
            FROM doctors d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = ? OR d.user_id = ?
            LIMIT 1
            """,
            (doctor_id, doctor_id),
        )
        doctor_row = cursor.fetchone()
        if not doctor_row:
            return None
        doctor = dict(doctor_row)

        # 1. Fetch complete follow-up and appointment schedule for this doctor
        cursor.execute(
            """
            SELECT a.id, a.patient_id, a.doctor_id, a.patient_name, a.doctor_name,
                   a.appointment_date, a.appointment_time, a.consultation_type,
                   a.symptoms_notes, a.status, a.created_at,
                   COALESCE(p.age, '') AS patient_age, COALESCE(p.gender, '') AS patient_gender
            FROM appointments a
            LEFT JOIN patients p ON p.id = a.patient_id OR LOWER(TRIM(p.name)) = LOWER(TRIM(a.patient_name))
            WHERE a.doctor_id = ?
            ORDER BY a.appointment_date DESC, a.appointment_time DESC, a.id DESC
            """,
            (doctor["doctor_id"],),
        )
        follow_ups = [dict(row) for row in cursor.fetchall()]
        doctor["follow_ups"] = follow_ups
        doctor["follow_up_count"] = len(follow_ups)

        # 2. Fetch distinct patients assigned to this doctor (via appointments or cases)
        cursor.execute(
            """
            SELECT DISTINCT p.id, p.name, p.age, p.gender, p.phone, p.abha_id,
                   p.blood_group, p.prakriti_primary, p.prakriti_secondary, p.created_at
            FROM patients p
            WHERE p.id IN (
                SELECT patient_id FROM appointments WHERE doctor_id = ? AND patient_id IS NOT NULL
                UNION
                SELECT patient_id FROM cases WHERE doctor_id = ? AND patient_id IS NOT NULL
            )
            OR LOWER(TRIM(p.name)) IN (
                SELECT LOWER(TRIM(patient_name)) FROM appointments WHERE doctor_id = ?
            )
            ORDER BY p.name COLLATE NOCASE
            """,
            (doctor["doctor_id"], doctor["user_id"], doctor["doctor_id"]),
        )
        patients = [dict(row) for row in cursor.fetchall()]

        for patient in patients:
            cursor.execute(
                """
                SELECT appointment_date, appointment_time, consultation_type,
                       symptoms_notes, status
                FROM appointments
                WHERE doctor_id = ? AND (patient_id = ? OR LOWER(TRIM(patient_name)) = LOWER(TRIM(?)))
                ORDER BY appointment_date ASC, appointment_time ASC
                """,
                (doctor["doctor_id"], patient["id"], patient["name"]),
            )
            patient["appointments"] = [dict(row) for row in cursor.fetchall()]

            cursor.execute(
                "SELECT COUNT(*) FROM cases WHERE doctor_id = ? AND (patient_id = ? OR LOWER(TRIM(patient_name)) = LOWER(TRIM(?)))",
                (doctor["user_id"], patient["id"], patient["name"]),
            )
            patient["case_count"] = cursor.fetchone()[0]

        doctor["patients"] = patients
        doctor["patient_count"] = len(patients)
        return doctor
    finally:
        conn.close()


# =====================================================
# DOCTORS & APPOINTMENTS DATA HELPERS
# =====================================================

def get_doctor_dashboard(doctor_id):
    """Returns live, practitioner-scoped data for the doctor dashboard."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT d.id AS doctor_id, d.user_id, d.specialization, d.council_reg_no,
                   d.qualification, d.cases_count, d.status, u.full_name, u.username, u.identifier,
                   u.phone
            FROM doctors d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = ? OR d.user_id = ?
            LIMIT 1
            """,
            (doctor_id, doctor_id),
        )
        doctor_row = cursor.fetchone()
        if not doctor_row:
            return None
        doctor = dict(doctor_row)

        doc_name = doctor.get("full_name") or ""
        cursor.execute(
            """
            SELECT * FROM appointments
            WHERE doctor_id = ? OR doctor_id = ? OR doctor_id IN (SELECT id FROM doctors WHERE user_id = ?)
               OR (doctor_name LIKE ? OR doctor_name = ?)
            ORDER BY appointment_date ASC, appointment_time ASC, id DESC
            """,
            (doctor["doctor_id"], doctor["user_id"], doctor["user_id"], f"%{doc_name}%", doc_name),
        )
        appointments = [dict(row) for row in cursor.fetchall()]

        # Clinical cases retain the practitioner user ID as their foreign key.
        cursor.execute(
            """
            SELECT * FROM cases
            WHERE doctor_id = ? OR doctor_id = ?
            ORDER BY created_at DESC, id DESC
            """,
            (doctor["user_id"], doctor["doctor_id"]),
        )
        cases = [dict(row) for row in cursor.fetchall()]

        today = date.today().isoformat()
        follow_ups_by_patient = {}

        # 1. Appointments that are upcoming or marked as follow-up / confirmed
        for appointment in appointments:
            p_name = str(appointment.get("patient_name") or "").strip()
            if not p_name:
                continue
            status_val = str(appointment.get("status") or "").strip()
            status_clean = status_val.casefold()
            apt_date = str(appointment.get("appointment_date") or "").strip()
            is_upcoming = apt_date >= today and status_clean not in {"cancelled", "completed", "absent"}
            is_followup = "follow" in status_clean or "follow" in str(appointment.get("consultation_type") or "").casefold()

            if (is_upcoming or is_followup) and status_clean not in {"cancelled", "completed", "absent"}:
                key = p_name.casefold()
                if key not in follow_ups_by_patient:
                    follow_ups_by_patient[key] = {
                        "id": appointment.get("id"),
                        "patient_id": appointment.get("patient_id"),
                        "doctor_id": appointment.get("doctor_id"),
                        "patient_name": p_name,
                        "doctor_name": appointment.get("doctor_name") or doc_name,
                        "appointment_date": apt_date or today,
                        "appointment_time": appointment.get("appointment_time") or "Scheduled Time",
                        "consultation_type": appointment.get("consultation_type") or "Follow-up Consultation",
                        "symptoms_notes": appointment.get("symptoms_notes") or "Follow-up consultation",
                        "status": "Follow-up" if is_followup else (appointment.get("status") or "Confirmed"),
                    }

        # 2. Patients with clinical cases having status = 'Follow-up'
        for case in cases:
            p_name = str(case.get("patient_name") or "").strip()
            if not p_name:
                continue
            status_val = str(case.get("status") or "").strip()
            if "follow" in status_val.casefold() and status_val.casefold() not in {"completed", "absent", "cancelled"}:
                key = p_name.casefold()
                if key not in follow_ups_by_patient:
                    case_date = str(case.get("case_date") or case.get("created_at") or today)[:10]
                    follow_ups_by_patient[key] = {
                        "id": case.get("id"),
                        "case_id": case.get("id"),
                        "patient_id": case.get("patient_id"),
                        "doctor_id": case.get("doctor_id"),
                        "patient_name": p_name,
                        "doctor_name": doc_name,
                        "appointment_date": case_date,
                        "appointment_time": "Scheduled Follow-up",
                        "consultation_type": "Follow-up Consultation",
                        "symptoms_notes": str(case.get("chief_complaint") or case.get("diagnosis") or "Follow-up consultation"),
                        "status": "Follow-up",
                    }

        follow_ups = list(follow_ups_by_patient.values())
        follow_ups.sort(
            key=lambda item: (
                0 if str(item.get("appointment_date") or "") >= today and "Scheduled" not in str(item.get("appointment_time") or "") else 1,
                str(item.get("appointment_date") or ""),
                str(item.get("appointment_time") or "")
            )
        )
        todays_appointments = [
            appointment for appointment in appointments
            if str(appointment.get("appointment_date") or "") == today
        ]
        todays_case_records = [
            case for case in cases
            if str(case.get("case_date") or "") == today
            or str(case.get("created_at") or "").startswith(today)
        ]

        patient_names = {
            str(record.get("patient_name") or "").strip()
            for record in appointments + cases
            if str(record.get("patient_name") or "").strip()
        }

        recent_by_patient = {}

        def add_recent_patient(name, activity, detail, status):
            clean_name = str(name or "").strip()
            if not clean_name:
                return
            item = {
                "patient_name": clean_name,
                "last_activity": str(activity or ""),
                "detail": str(detail or "Clinical record updated"),
                "status": str(status or "Active"),
            }
            current = recent_by_patient.get(clean_name.casefold())
            if not current or item["last_activity"] > current["last_activity"]:
                recent_by_patient[clean_name.casefold()] = item

        for appointment in appointments:
            add_recent_patient(
                appointment.get("patient_name"),
                appointment.get("created_at") or appointment.get("appointment_date"),
                appointment.get("symptoms_notes") or appointment.get("consultation_type"),
                appointment.get("status") or "Confirmed",
            )
        for case in cases:
            add_recent_patient(
                case.get("patient_name"),
                case.get("created_at") or case.get("case_date"),
                case.get("chief_complaint") or case.get("diagnosis"),
                case.get("status") or "Active",
            )

        recent_patients = sorted(
            recent_by_patient.values(),
            key=lambda item: item["last_activity"],
            reverse=True,
        )

        return {
            "doctor": doctor,
            "stats": {
                "total_patients": len(patient_names),
                "todays_cases": len(todays_appointments) + len(todays_case_records),
                "follow_ups": len(follow_ups),
                "ai_cases_analyzed": len(cases),
            },
            "follow_ups": follow_ups,
            "recent_patients": recent_patients,
        }
    finally:
        conn.close()


def get_doctors_list():
    """Returns a list of all active AYUSH doctors with their specialization and availability."""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT d.id AS doctor_id, d.user_id, u.full_name, u.username, u.identifier, u.phone,
               d.specialization, d.council_reg_no, d.qualification, d.cases_count, d.status
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
                       patient_id=None, doctor_id=None, age=None, gender=None,
                       patient_email=None, patient_phone=None, patient_abha_id=None):
    """Creates and persists an appointment in the database and dispatches confirmation email."""
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

        if not doctor_id:
            cursor.execute("SELECT id FROM doctors LIMIT 1;")
            d1_row = cursor.fetchone()
            if d1_row:
                doctor_id = d1_row[0]
            else:
                raise ValueError("A valid attending doctor must be selected.")

        # Derive the persisted doctor name and credentials from the selected doctor account.
        cursor.execute(
            """
            SELECT d.id, u.full_name, d.specialization, d.qualification, d.council_reg_no, u.phone
            FROM doctors d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = ?
            """,
            (doctor_id,),
        )
        selected_doctor = cursor.fetchone()
        if not selected_doctor:
            raise ValueError("The selected practitioner account is not available.")
        canonical_doctor_name = selected_doctor["full_name"]
        doctor_name = canonical_doctor_name

        doctor_details = {
            "full_name": canonical_doctor_name,
            "specialization": selected_doctor["specialization"] or "Ayurvedic Internal Medicine (Kayachikitsa)",
            "qualification": selected_doctor["qualification"] or "BAMS, MD (Ayurveda)",
            "council_reg_no": selected_doctor["council_reg_no"] or "AYUSH-WB-2024-REG"
        }

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
            else:
                # Auto-create patient in patients table so demographic details are preserved
                clean_age = None
                try:
                    if age is not None and str(age).strip():
                        clean_age = int(age)
                except (ValueError, TypeError):
                    pass
                clean_gender = gender if gender and str(gender).strip() else "Other"
                auto_abha = f"ABHA-{int(time.time() * 1000)}"
                cursor.execute(
                    """
                    INSERT INTO patients (abha_id, name, age, gender, created_at)
                    VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
                    """,
                    (auto_abha, patient_name.strip(), clean_age, clean_gender),
                )
                patient_id = cursor.lastrowid

        # Resolve patient email, phone, and ABHA ID
        resolved_patient_email = (patient_email or "").strip()
        resolved_patient_phone = (patient_phone or "").strip()
        resolved_abha_id = (patient_abha_id or "").strip()

        if patient_id and (not resolved_patient_email or "@" not in resolved_patient_email or not resolved_abha_id or not resolved_patient_phone):
            try:
                cursor.execute(
                    """
                    SELECT u.username, u.phone as u_phone, p.abha_id, p.phone as p_phone
                    FROM patients p
                    LEFT JOIN users u ON p.user_id = u.id
                    WHERE p.id = ?;
                    """,
                    (patient_id,)
                )
                p_row = cursor.fetchone()
                if p_row:
                    if p_row["username"] and "@" in p_row["username"]:
                        resolved_patient_email = p_row["username"].strip()
                    if not resolved_patient_phone:
                        resolved_patient_phone = (p_row["u_phone"] or p_row["p_phone"] or "").strip()
                    if not resolved_abha_id and p_row["abha_id"]:
                        resolved_abha_id = p_row["abha_id"].strip()
            except Exception as p_err:
                print("[APPOINTMENT DB] Patient detail lookup notice:", p_err)

        if not resolved_patient_email or "@" not in resolved_patient_email:
            try:
                cursor.execute(
                    """
                    SELECT username FROM users
                    WHERE role = 'patient' AND username LIKE '%@%'
                      AND (full_name LIKE ? OR identifier = ? OR identifier LIKE ?)
                    ORDER BY id DESC LIMIT 1;
                    """,
                    (f"%{patient_name}%", resolved_abha_id, f"%{resolved_abha_id}%")
                )
                u_match = cursor.fetchone()
                if u_match and u_match["username"] and "@" in u_match["username"]:
                    resolved_patient_email = u_match["username"].strip()
            except Exception as u_err:
                print("[APPOINTMENT DB] Users fallback lookup notice:", u_err)

        # Idempotency / duplicate check: avoid duplicate appointments for same patient, doctor, date, and time
        cursor.execute(
            """
            SELECT id, patient_id, doctor_id, patient_name, doctor_name,
                   appointment_date, appointment_time, consultation_type,
                   symptoms_notes, status, created_at
            FROM appointments
            WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?))
              AND doctor_id = ?
              AND appointment_date = ?
              AND appointment_time = ?
            LIMIT 1;
            """,
            (patient_name, doctor_id, appointment_date, appointment_time),
        )
        existing_dup = cursor.fetchone()
        if existing_dup:
            dup_dict = dict(existing_dup)
            conn.close()
            return dup_dict

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

        # Dispatch automated appointment confirmation email asynchronously
        try:
            try:
                from email_service import send_appointment_confirmation_email_async
            except ImportError:
                from backend.email_service import send_appointment_confirmation_email_async

            apt_payload = dict(new_apt)
            apt_payload["patient_email"] = resolved_patient_email
            apt_payload["patient_phone"] = resolved_patient_phone
            apt_payload["patient_abha_id"] = resolved_abha_id

            send_appointment_confirmation_email_async(
                appointment_data=apt_payload,
                patient_data={
                    "name": patient_name,
                    "email": resolved_patient_email,
                    "phone": resolved_patient_phone,
                    "abha_id": resolved_abha_id,
                },
                doctor_data=doctor_details,
            )
        except Exception as email_err:
            print(f"[APPOINTMENT DB] Failed to dispatch appointment confirmation email: {email_err}")

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


# =====================================================
# NOTICES & CLINICAL ORDERS
# =====================================================

def add_notice(title, content, notice_type="General", priority="Normal", posted_by="Hospital Administration"):
    """Adds a new administrative notice/order for doctors."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO notices (title, content, notice_type, priority, posted_by)
            VALUES (?, ?, ?, ?, ?)
            """,
            (title.strip(), content.strip(), (notice_type or "General").strip(), (priority or "Normal").strip(), (posted_by or "Hospital Administration").strip())
        )
        notice_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT * FROM notices WHERE id = ?", (notice_id,))
        notice = dict(cursor.fetchone())
        notice["comments"] = []
        return notice
    finally:
        conn.close()


def get_notices(order="desc"):
    """
    Retrieves notices along with their comments.
    Defaults to DESCENDING order (newest first).
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        order_direction = "ASC" if str(order).lower() == "asc" else "DESC"
        query = f"SELECT * FROM notices ORDER BY created_at {order_direction}, id {order_direction};"
        cursor.execute(query)
        notices = [dict(row) for row in cursor.fetchall()]

        # Fetch comments for each notice
        for notice in notices:
            cursor.execute(
                "SELECT * FROM notice_comments WHERE notice_id = ? ORDER BY created_at ASC, id ASC;",
                (notice["id"],)
            )
            notice["comments"] = [dict(r) for r in cursor.fetchall()]

        return notices
    finally:
        conn.close()


def delete_notice(notice_id):
    """Deletes a notice and its associated comments."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM notices WHERE id = ?", (notice_id,))
        conn.commit()
        return True
    finally:
        conn.close()


def add_notice_comment(notice_id, doctor_id, author_name, comment_text, author_role="doctor"):
    """Adds a doctor comment/reply/acknowledgement to a notice."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO notice_comments (notice_id, doctor_id, author_name, author_role, comment_text)
            VALUES (?, ?, ?, ?, ?)
            """,
            (notice_id, doctor_id, author_name.strip(), (author_role or "doctor").strip(), comment_text.strip())
        )
        comment_id = cursor.lastrowid
        conn.commit()
        cursor.execute("SELECT * FROM notice_comments WHERE id = ?", (comment_id,))
        return dict(cursor.fetchone())
    finally:
        conn.close()


def get_notice_comments(notice_id):
    """Retrieves all comments for a notice."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            "SELECT * FROM notice_comments WHERE notice_id = ? ORDER BY created_at ASC, id ASC;",
            (notice_id,)
        )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def seed_recent_clinical_history():
    """Seeds authentic clinical consultation history with prescribed medicines and assigned doctors."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM cases;")
        if cursor.fetchone()[0] > 0:
            return

        cursor.execute("SELECT u.id, u.full_name, d.specialization FROM users u JOIN doctors d ON d.user_id = u.id;")
        doc_rows = [dict(r) for r in cursor.fetchall()]
        doc_map = {d["full_name"]: d["id"] for d in doc_rows}

        doc_sen_id = doc_map.get("Dr. Arindam Sen", 1)
        doc_rao_id = doc_map.get("Dr. Priyadarshini Rao", 2)
        doc_kapoor_id = doc_map.get("Dr. Meera Kapoor", 5)
        doc_bose_id = doc_map.get("Dr. Kunal Bose", 6)

        records = [
            {
                "patient_name": "Rohit Sharma",
                "age": 34,
                "gender": "Male",
                "doctor_id": doc_sen_id,
                "chief_complaint": "Chronic acid reflux, burning sensation in epigastrium, and nocturnal gastric distress",
                "diagnosis": "Amlapitta with Pitta-Vata Dushti",
                "prakriti": "Pitta-Vata",
                "date": "2026-09-08 10:30:00",
                "prescriptions": [
                    ("Ashwagandha Churna", "3g", "Twice daily with warm milk", "Warm Milk", "30 Days"),
                    ("Avipattikar Churna", "5g", "Twice daily before meals", "Lukewarm Water", "21 Days"),
                    ("Triphala Kwatha", "20 ml", "Bedtime", "Lukewarm Water", "15 Days"),
                    ("Brahmi Vati", "1 Tablet", "Morning post breakfast", "Water", "30 Days")
                ]
            },
            {
                "patient_name": "Ananya Roy",
                "age": 28,
                "gender": "Female",
                "doctor_id": doc_rao_id,
                "chief_complaint": "Bilateral knee joint pain, morning stiffness, and difficulty climbing stairs",
                "diagnosis": "Sandhigata Vata (Osteoarthritic joint changes)",
                "prakriti": "Vata-Kapha",
                "date": "2026-09-09 11:45:00",
                "prescriptions": [
                    ("Yograj Guggulu", "2 Tablets", "Twice daily post meals", "Warm Water", "30 Days"),
                    ("Dashamoola Kwatha", "30 ml", "Twice daily before meals", "Warm Water", "20 Days"),
                    ("Mahanarayan Taila", "Adequate qty", "Gentle local massage with hot water bag fomentation", "External", "30 Days")
                ]
            },
            {
                "patient_name": "Vikramaditya Das",
                "age": 45,
                "gender": "Male",
                "doctor_id": doc_bose_id,
                "chief_complaint": "Post-meal heaviness in abdomen, irregular bowel habits, and fatigue",
                "diagnosis": "Kaphaja Grahani with Agnimandya",
                "prakriti": "Kapha-Pitta",
                "date": "2026-09-09 16:15:00",
                "prescriptions": [
                    ("Trikatu Churna", "2g", "Twice daily with honey before meals", "Honey", "21 Days"),
                    ("Chitrakadi Vati", "1 Tablet", "Chewable twice daily after lunch & dinner", "Warm Water", "15 Days"),
                    ("Mustakarishta", "15 ml with equal water", "Twice daily after food", "Water", "30 Days")
                ]
            },
            {
                "patient_name": "Meenakshi Sundaram",
                "age": 52,
                "gender": "Female",
                "doctor_id": doc_kapoor_id,
                "chief_complaint": "Fluctuating blood pressure, generalized tension, palpitations, and poor sleep quality",
                "diagnosis": "Raktagata Vata & Manasika Udvega",
                "prakriti": "Pitta-Vata",
                "date": "2026-09-10 14:00:00",
                "prescriptions": [
                    ("Sarpagandha Ghan Vati", "1 Tablet", "Night at bedtime", "Lukewarm Water", "30 Days"),
                    ("Shankhapushpi Syrup", "10 ml", "Twice daily post breakfast and dinner", "Water", "30 Days"),
                    ("Brahmi Taila", "5 ml", "Gentle scalp application at night (Shiroabhyanga)", "External", "30 Days")
                ]
            },
            {
                "patient_name": "Kavita Patel",
                "age": 39,
                "gender": "Female",
                "doctor_id": doc_sen_id,
                "chief_complaint": "Cervical spine stiffness, pain radiating to right shoulder, and tension headache",
                "diagnosis": "Manyastambha (Cervical Spondylosis)",
                "prakriti": "Vata-Kapha",
                "date": "2026-09-11 09:30:00",
                "prescriptions": [
                    ("Trayodashanga Guggulu", "2 Tablets", "Twice daily after meals", "Warm Water", "30 Days"),
                    ("Rasnasaptak Kwatha", "20 ml", "Twice daily on empty stomach", "Lukewarm Water", "21 Days"),
                    ("Ksheerabala 101 Taila", "4 Drops", "Pratimarsha Nasya in both nostrils every morning", "Nasal drops", "15 Days")
                ]
            }
        ]

        for rec in records:
            cursor.execute(
                """
                INSERT INTO cases (doctor_id, patient_name, age, gender, chief_complaint, diagnosis, prakriti, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Completed', ?);
                """,
                (rec["doctor_id"], rec["patient_name"], rec["age"], rec["gender"], rec["chief_complaint"], rec["diagnosis"], rec["prakriti"], rec["date"])
            )
            case_id = cursor.lastrowid
            for p in rec["prescriptions"]:
                cursor.execute(
                    """
                    INSERT INTO prescriptions (case_id, medicine_name, dosage, timing, anupana, duration)
                    VALUES (?, ?, ?, ?, ?, ?);
                    """,
                    (case_id, p[0], p[1], p[2], p[3], p[4])
                )

        conn.commit()
    finally:
        conn.close()


def get_recent_history():
    """Fetches recent patient clinical consultation history."""
    seed_recent_clinical_history()
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT c.id, c.patient_name, c.age, c.gender, c.chief_complaint, c.diagnosis,
                   c.prakriti, c.status, c.created_at, u.full_name AS doctor_name, d.specialization AS doctor_specialization
            FROM cases c
            LEFT JOIN users u ON u.id = c.doctor_id
            LEFT JOIN doctors d ON d.user_id = u.id
            ORDER BY c.created_at DESC, c.id DESC;
            """
        )
        case_rows = cursor.fetchall()
        history = []
        for r in case_rows:
            case_id = r["id"]
            cursor.execute(
                """
                SELECT medicine_name, dosage, timing, anupana, duration
                FROM prescriptions
                WHERE case_id = ?
                ORDER BY id ASC;
                """,
                (case_id,)
            )
            rx_rows = cursor.fetchall()
            rx_items = []
            rx_structured = []
            for rx in rx_rows:
                detail = rx["medicine_name"]
                meta = []
                if rx["dosage"]:
                    meta.append(rx["dosage"])
                if rx["timing"]:
                    meta.append(rx["timing"])
                if rx["duration"]:
                    meta.append(rx["duration"])
                if meta:
                    detail += f" ({', '.join(meta)})"
                rx_items.append(detail)
                rx_structured.append({
                    "name": rx["medicine_name"],
                    "dosage": rx["dosage"] or "",
                    "timing": rx["timing"] or "",
                    "anupana": rx["anupana"] or "",
                    "duration": rx["duration"] or ""
                })

            issue_text = r["chief_complaint"] or "General Consultation"
            if r["diagnosis"]:
                issue_text = f"{r['diagnosis']} - {issue_text}"

            history.append({
                "id": case_id,
                "patient_name": r["patient_name"] or "Patient",
                "patient_age": r["age"] if r["age"] is not None else "Not specified",
                "gender": r["gender"] or "Not specified",
                "doctor_name": r["doctor_name"] or "Hospital Practitioner",
                "doctor_specialization": r["doctor_specialization"] or "AYUSH Specialist",
                "issue": issue_text,
                "chief_complaint": r["chief_complaint"] or "",
                "diagnosis": r["diagnosis"] or "",
                "prakriti": r["prakriti"] or "Vata-Pitta Balance",
                "status": r["status"] or "Completed",
                "prescribed_medicines": rx_items if rx_items else ["Standard lifestyle & dietary regimen (Pathya Ahar)"],
                "prescriptions_detailed": rx_structured,
                "prescribed_medicines_summary": "; ".join(rx_items) if rx_items else "Standard lifestyle & dietary regimen (Pathya Ahar)",
                "date": str(r["created_at"]) if r["created_at"] else "Recent",
            })

        return history
    finally:
        conn.close()


def get_hospital_patient_inflow(period="daily", count=14, metric="registrations"):
    """
    Computes real hospital patient registrations and footfall aggregated daily or weekly from SQLite.
    Returns structured data with live metrics and points for the admin chart according to actual data added.
    """
    import datetime
    today = datetime.date.today()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    reg_counts = {}
    appt_counts = {}
    case_counts = {}
    try:
        # 1. Real Patient Registrations from portal and patients table
        cursor.execute("""
            SELECT DATE(created_at) as d, COUNT(*) as c 
            FROM patients 
            WHERE created_at IS NOT NULL 
            GROUP BY DATE(created_at)
        """)
        for r in cursor.fetchall():
            if r["d"]:
                reg_counts[str(r["d"])] = r["c"]

        # Also account for portal patient users who registered
        cursor.execute("""
            SELECT DATE(created_at) as d, COUNT(*) as c 
            FROM users 
            WHERE role = 'patient' AND created_at IS NOT NULL 
            GROUP BY DATE(created_at)
        """)
        for r in cursor.fetchall():
            if r["d"]:
                d_key = str(r["d"])
                reg_counts[d_key] = max(reg_counts.get(d_key, 0), r["c"])

        # 2. Real Appointments
        cursor.execute("""
            SELECT DATE(COALESCE(appointment_date, created_at)) as d, COUNT(*) as c 
            FROM appointments 
            WHERE status != 'CANCELLED' 
            GROUP BY DATE(COALESCE(appointment_date, created_at))
        """)
        for r in cursor.fetchall():
            if r["d"]:
                appt_counts[str(r["d"])] = r["c"]

        # 3. Real Clinical Cases / OPD Consultations
        cursor.execute("""
            SELECT DATE(created_at) as d, COUNT(*) as c 
            FROM cases 
            WHERE created_at IS NOT NULL 
            GROUP BY DATE(created_at)
        """)
        for r in cursor.fetchall():
            if r["d"]:
                case_counts[str(r["d"])] = r["c"]
    except Exception as e:
        print(f"[PATIENT INFLOW QUERY ERROR]: {e}")
    finally:
        conn.close()

    is_registrations_metric = (metric or "registrations").lower() in ("registrations", "registration", "portal")

    if period == "weekly":
        num_weeks = count if count else 8
        items = []
        
        for i in range(num_weeks - 1, -1, -1):
            start_of_week = today - datetime.timedelta(days=today.weekday() + i * 7)
            week_label = f"Wk {start_of_week.isocalendar()[1]} ({start_of_week.strftime('%d %b')})"
            
            # Aggregate 7 days of the week
            week_regs = 0
            week_appts = 0
            week_cases = 0
            for day_offset in range(7):
                curr_d = (start_of_week + datetime.timedelta(days=day_offset)).strftime("%Y-%m-%d")
                week_regs += reg_counts.get(curr_d, 0)
                week_appts += appt_counts.get(curr_d, 0)
                week_cases += case_counts.get(curr_d, 0)

            plotted_val = week_regs if is_registrations_metric else (week_regs + week_appts + week_cases)

            items.append({
                "label": week_label,
                "date": start_of_week.strftime("%Y-%m-%d"),
                "patients": plotted_val,
                "registrations": week_regs,
                "appointments": week_appts,
                "cases": week_cases,
                "opd": week_cases,
                "followup": week_appts
            })
            
        values = [it["patients"] for it in items]
        high = max(values) if values else 0
        low = min(values) if values else 0
        avg = round(sum(values) / len(values), 1) if values else 0
        latest = values[-1] if values else 0
        prev = values[-2] if len(values) > 1 else latest
        change_pct = round(((latest - prev) / prev * 100), 1) if prev > 0 else (100.0 if latest > 0 else 0.0)
        
        return {
            "period": "weekly",
            "metric": "registrations" if is_registrations_metric else "inflow",
            "metric_name": "Patient Registrations" if is_registrations_metric else "Total Patient Inflow",
            "count": num_weeks,
            "items": items,
            "latest": latest,
            "previous": prev,
            "change_pct": change_pct,
            "high": high,
            "low": low,
            "average": avg,
            "total": sum(values),
            "total_registrations": sum(it["registrations"] for it in items),
            "total_appointments": sum(it["appointments"] for it in items),
            "total_cases": sum(it["cases"] for it in items)
        }
    else:
        # daily
        num_days = count if count else 14
        items = []
        
        for i in range(num_days - 1, -1, -1):
            d = today - datetime.timedelta(days=i)
            d_str = d.strftime("%Y-%m-%d")
            label = d.strftime("%a %d %b")
            
            day_regs = reg_counts.get(d_str, 0)
            day_appts = appt_counts.get(d_str, 0)
            day_cases = case_counts.get(d_str, 0)

            plotted_val = day_regs if is_registrations_metric else (day_regs + day_appts + day_cases)
            
            items.append({
                "label": label,
                "date": d_str,
                "patients": plotted_val,
                "registrations": day_regs,
                "appointments": day_appts,
                "cases": day_cases,
                "opd": day_cases,
                "followup": day_appts
            })
            
        values = [it["patients"] for it in items]
        high = max(values) if values else 0
        low = min(values) if values else 0
        avg = round(sum(values) / len(values), 1) if values else 0
        latest = values[-1] if values else 0
        prev = values[-2] if len(values) > 1 else latest
        change_pct = round(((latest - prev) / prev * 100), 1) if prev > 0 else (100.0 if latest > 0 else 0.0)
        
        return {
            "period": "daily",
            "metric": "registrations" if is_registrations_metric else "inflow",
            "metric_name": "Patient Registrations" if is_registrations_metric else "Total Patient Inflow",
            "count": num_days,
            "items": items,
            "latest": latest,
            "previous": prev,
            "change_pct": change_pct,
            "high": high,
            "low": low,
            "average": avg,
            "total": sum(values),
            "total_registrations": sum(it["registrations"] for it in items),
            "total_appointments": sum(it["appointments"] for it in items),
            "total_cases": sum(it["cases"] for it in items)
        }


def update_patient_case_record(case_id, data):
    """Updates patient case record details and prescriptions."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        case_row = cursor.fetchone()
        if not case_row:
            return {"success": False, "error": f"Case record #{case_id} not found."}

        patient_name = data.get("patient_name", case_row["patient_name"])
        age = data.get("age", case_row["age"])
        gender = data.get("gender", case_row["gender"])
        chief_complaint = data.get("chief_complaint", case_row["chief_complaint"])
        diagnosis = data.get("diagnosis", case_row["diagnosis"])
        prakriti = data.get("prakriti", case_row["prakriti"])
        doctor_id = data.get("doctor_id", case_row["doctor_id"])
        status = data.get("status", case_row["status"])

        cursor.execute(
            """
            UPDATE cases
            SET patient_name = ?, age = ?, gender = ?, chief_complaint = ?,
                diagnosis = ?, prakriti = ?, doctor_id = ?, status = ?
            WHERE id = ?;
            """,
            (patient_name, age, gender, chief_complaint, diagnosis, prakriti, doctor_id, status, case_id)
        )

        if "prescriptions" in data and isinstance(data["prescriptions"], list):
            cursor.execute("DELETE FROM prescriptions WHERE case_id = ?", (case_id,))
            for rx in data["prescriptions"]:
                if isinstance(rx, dict) and rx.get("name"):
                    cursor.execute(
                        """
                        INSERT INTO prescriptions (case_id, patient_id, medicine_name, dosage, timing, anupana, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?);
                        """,
                        (case_id, case_row["patient_id"], rx["name"], rx.get("dosage", ""), rx.get("timing", ""), rx.get("anupana", ""), rx.get("duration", ""))
                    )
                elif isinstance(rx, str) and rx.strip():
                    cursor.execute(
                        """
                        INSERT INTO prescriptions (case_id, patient_id, medicine_name, dosage, timing, anupana, duration)
                        VALUES (?, ?, ?, '', '', '', '');
                        """,
                        (case_id, case_row["patient_id"], rx.strip())
                    )

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            ("Patient Case Updated", f"Updated clinical details for patient '{patient_name}' (Case #{case_id})")
        )

        conn.commit()
        return {"success": True, "message": f"Patient record #{case_id} updated successfully."}
    finally:
        conn.close()


def merge_patient_records(primary_case_id, duplicate_case_id):
    """Merges duplicate patient case into primary patient case."""
    if int(primary_case_id) == int(duplicate_case_id):
        return {"success": False, "error": "Primary and duplicate accounts cannot be the same."}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM cases WHERE id = ?", (primary_case_id,))
        prim = cursor.fetchone()
        cursor.execute("SELECT * FROM cases WHERE id = ?", (duplicate_case_id,))
        dupe = cursor.fetchone()

        if not prim:
            return {"success": False, "error": f"Primary case #{primary_case_id} not found."}
        if not dupe:
            return {"success": False, "error": f"Duplicate case #{duplicate_case_id} not found."}

        # Reassign prescriptions from duplicate to primary
        cursor.execute(
            "UPDATE prescriptions SET case_id = ?, patient_id = ? WHERE case_id = ?",
            (primary_case_id, prim["patient_id"], duplicate_case_id)
        )

        # Append merged consultation notes
        new_complaint = prim["chief_complaint"] or ""
        if dupe["chief_complaint"] and dupe["chief_complaint"] not in new_complaint:
            new_complaint += f" | Merged Consultation Notes: {dupe['chief_complaint']}"
            cursor.execute("UPDATE cases SET chief_complaint = ? WHERE id = ?", (new_complaint, primary_case_id))

        # Mark duplicate as Merged (Inactive)
        cursor.execute(
            "UPDATE cases SET status = 'Merged (Inactive)' WHERE id = ?",
            (duplicate_case_id,)
        )

        # Log audit
        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            ("Patient Records Merged", f"Merged duplicate case #{duplicate_case_id} ('{dupe['patient_name']}') into primary case #{primary_case_id} ('{prim['patient_name']}')")
        )

        conn.commit()
        return {"success": True, "message": f"Successfully merged case #{duplicate_case_id} into primary case #{primary_case_id}."}
    finally:
        conn.close()


def deactivate_patient_record(case_id, action="deactivate"):
    """Toggles patient case status between 'Deactivated' and 'Active'."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM cases WHERE id = ?", (case_id,))
        row = cursor.fetchone()
        if not row:
            return {"success": False, "error": f"Case record #{case_id} not found."}

        new_status = "Deactivated" if action == "deactivate" else "Completed"
        cursor.execute("UPDATE cases SET status = ? WHERE id = ?", (new_status, case_id))

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            (f"Patient {action.capitalize()}", f"Set status of patient '{row['patient_name']}' (Case #{case_id}) to '{new_status}'")
        )

        conn.commit()
        return {"success": True, "status": new_status, "message": f"Patient account #{case_id} marked as {new_status}."}
    finally:
        conn.close()


def reassign_patient_doctor(data):
    """Reassigns a patient's appointed practitioner across their appointments and clinical cases."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        patient_name = data.get("patient_name", "").strip()
        new_doctor_id = data.get("new_doctor_id") or data.get("doctor_id")
        appointment_id = data.get("appointment_id")
        patient_id = data.get("patient_id")
        reason = data.get("reason", "").strip() or "Practitioner schedule adjustment"

        if not patient_name and not patient_id and not appointment_id:
            return {"success": False, "error": "Patient name or identifier is required."}
        if not new_doctor_id:
            return {"success": False, "error": "New practitioner ID is required."}

        # Look up new doctor details
        cursor.execute(
            """
            SELECT d.id AS doc_id, d.user_id, u.full_name, d.specialization
            FROM doctors d
            JOIN users u ON d.user_id = u.id
            WHERE d.id = ? OR d.user_id = ?
            LIMIT 1;
            """,
            (new_doctor_id, new_doctor_id)
        )
        doc_row = cursor.fetchone()
        if not doc_row:
            return {"success": False, "error": f"Practitioner #{new_doctor_id} not found."}

        new_doc_id_val = doc_row["doc_id"]
        new_doc_user_id = doc_row["user_id"]
        new_doc_name = doc_row["full_name"]

        # Update appointments
        if appointment_id:
            cursor.execute(
                "UPDATE appointments SET doctor_id = ?, doctor_name = ? WHERE id = ?;",
                (new_doc_id_val, new_doc_name, appointment_id)
            )
        if patient_name:
            cursor.execute(
                "UPDATE appointments SET doctor_id = ?, doctor_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));",
                (new_doc_id_val, new_doc_name, patient_name)
            )
            cursor.execute(
                "UPDATE cases SET doctor_id = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));",
                (new_doc_user_id, patient_name)
            )
        if patient_id:
            cursor.execute(
                "UPDATE appointments SET doctor_id = ?, doctor_name = ? WHERE patient_id = ?;",
                (new_doc_id_val, new_doc_name, patient_id)
            )
            cursor.execute(
                "UPDATE cases SET doctor_id = ? WHERE patient_id = ?;",
                (new_doc_user_id, patient_id)
            )

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            (
                "Doctor Reassigned",
                f"Patient '{patient_name or patient_id}' appointed to '{new_doc_name}' ({doc_row['specialization']}). Reason: {reason}"
            )
        )

        # Synchronize app_storage cache if present
        try:
            cursor.execute("SELECT storage_value FROM app_storage WHERE storage_key = 'ayurcase_cached_appointments';")
            st_row = cursor.fetchone()
            if st_row and st_row[0]:
                appts = json.loads(st_row[0])
                for a in appts:
                    match_appt = appointment_id and str(a.get("id")) == str(appointment_id)
                    match_pat = patient_name and str(a.get("patient_name", "")).strip().lower() == patient_name.lower()
                    if match_appt or match_pat:
                        a["doctor_id"] = new_doc_id_val
                        a["doctor_name"] = new_doc_name
                cursor.execute(
                    "UPDATE app_storage SET storage_value = ?, updated_at = CURRENT_TIMESTAMP WHERE storage_key = 'ayurcase_cached_appointments';",
                    (json.dumps(appts),)
                )
        except Exception:
            pass

        try:
            cursor.execute("SELECT storage_value FROM app_storage WHERE storage_key = 'ayurcase_recent_history';")
            rh_row = cursor.fetchone()
            if rh_row and rh_row[0]:
                rh_list = json.loads(rh_row[0])
                for rh in rh_list:
                    if patient_name and str(rh.get("patient_name", "")).strip().lower() == patient_name.lower():
                        rh["doctor_name"] = new_doc_name
                cursor.execute(
                    "UPDATE app_storage SET storage_value = ?, updated_at = CURRENT_TIMESTAMP WHERE storage_key = 'ayurcase_recent_history';",
                    (json.dumps(rh_list),)
                )
        except Exception:
            pass

        conn.commit()
        return {
            "success": True,
            "message": f"Patient '{patient_name or 'record'}' successfully appointed to {new_doc_name}.",
            "new_doctor_name": new_doc_name,
            "new_doctor_id": new_doc_id_val
        }
    finally:
        conn.close()


def add_doctor_record(data):
    """Adds a new verified AYUSH doctor with full credentials and user authentication."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        full_name = data.get("full_name", "").strip()
        if not full_name:
            return {"success": False, "error": "Doctor full name is required."}
        if not full_name.lower().startswith("dr.") and not full_name.lower().startswith("dr "):
            full_name = f"Dr. {full_name}"

        specialization = data.get("specialization", "Ayurveda General Medicine").strip()
        council_reg_no = data.get("council_reg_no", "").strip() or f"AYUR-REG-{int(datetime.now().timestamp()) % 100000}"
        qualification = data.get("qualification", "BAMS").strip()
        phone = data.get("phone", "").strip()
        if not phone:
            return {"success": False, "error": "Phone number is required."}
        
        # Unique username/email
        raw_user = data.get("username") or data.get("email")
        if not raw_user:
            slug = full_name.lower().replace("dr.", "").replace(" ", "").strip()
            raw_user = f"{slug}@ayurcase.gov.in"
        else:
            raw_user = raw_user.strip()

        # Check if username exists
        cursor.execute("SELECT id FROM users WHERE username = ?", (raw_user,))
        if cursor.fetchone():
            raw_user = f"{raw_user.split('@')[0]}_{int(datetime.now().timestamp()) % 1000}@{raw_user.split('@')[-1] if '@' in raw_user else 'ayurcase.gov.in'}"

        pwd_hash = generate_password_hash("Doctor@123")
        cursor.execute(
            """
            INSERT INTO users (username, password_hash, role, full_name, identifier, phone)
            VALUES (?, ?, 'doctor', ?, ?, ?);
            """,
            (raw_user, pwd_hash, full_name, council_reg_no, phone)
        )
        user_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO doctors (user_id, specialization, council_reg_no, qualification, cases_count, status)
            VALUES (?, ?, ?, ?, 0, 'Active');
            """,
            (user_id, specialization, council_reg_no, qualification)
        )
        doc_id = cursor.lastrowid

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            ("Doctor Enrolled", f"Enrolled new practitioner '{full_name}' ({specialization}, Reg: {council_reg_no})")
        )

        conn.commit()
        return {
            "success": True,
            "doctor": {
                "id": doc_id,
                "doctor_id": doc_id,
                "user_id": user_id,
                "full_name": full_name,
                "specialization": specialization,
                "council_reg_no": council_reg_no,
                "qualification": qualification,
                "status": "Active",
                "username": raw_user,
                "phone": phone
            },
            "message": f"Practitioner {full_name} enrolled successfully."
        }
    finally:
        conn.close()


def update_doctor_record(doctor_id, data):
    """Updates practitioner details and credentials."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM doctors WHERE id = ? OR user_id = ?", (doctor_id, doctor_id))
        doc = cursor.fetchone()
        if not doc:
            return {"success": False, "error": f"Doctor record #{doctor_id} not found."}

        full_name = data.get("full_name")
        specialization = data.get("specialization", doc["specialization"])
        qualification = data.get("qualification", doc["qualification"])
        council_reg_no = data.get("council_reg_no", doc["council_reg_no"])
        status = data.get("status", doc["status"])
        phone = data.get("phone")

        if full_name:
            cursor.execute("UPDATE users SET full_name = ? WHERE id = ?", (full_name.strip(), doc["user_id"]))
        if phone is not None:
            cursor.execute("UPDATE users SET phone = ? WHERE id = ?", (phone.strip(), doc["user_id"]))

        cursor.execute(
            """
            UPDATE doctors
            SET specialization = ?, qualification = ?, council_reg_no = ?, status = ?
            WHERE id = ?;
            """,
            (specialization, qualification, council_reg_no, status, doc["id"])
        )

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            ("Doctor Updated", f"Updated details for practitioner ID #{doc['id']}")
        )

        conn.commit()
        return {"success": True, "message": "Doctor record updated successfully."}
    finally:
        conn.close()


def remove_doctor_record(doctor_id, action="remove"):
    """Sets doctor status to 'Past Doctor' (or 'Active'), safely preserving all clinical data."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            SELECT d.id, d.user_id, u.full_name
            FROM doctors d
            JOIN users u ON d.user_id = u.id
            WHERE d.id = ? OR d.user_id = ?;
            """,
            (doctor_id, doctor_id)
        )
        doc = cursor.fetchone()
        if not doc:
            return {"success": False, "error": f"Doctor #{doctor_id} not found."}

        new_status = "Past Doctor" if action == "remove" else "Active"
        cursor.execute("UPDATE doctors SET status = ? WHERE id = ?", (new_status, doc["id"]))

        cursor.execute(
            """
            INSERT INTO audit_logs (action, details)
            VALUES (?, ?);
            """,
            ("Doctor Status Change", f"Practitioner '{doc['full_name']}' status changed to '{new_status}'. All patient consultation records and histories are preserved.")
        )

        conn.commit()
        return {
            "success": True,
            "status": new_status,
            "message": f"Practitioner '{doc['full_name']}' is now marked as {new_status}. All clinical records and histories are safely preserved."
        }
    finally:
        conn.close()


def save_followup_prescription(patient_name, doctor_id, prescription, suggestion, absent):
    """
    Saves a follow-up visit outcome for a patient.
    Creates/updates a case record for this follow-up and stores the prescription in the
    prescriptions table so that it appears in:
      - Admin Recent Patients (via get_recent_history)
      - Patient My Prescriptions (via get_patient_prescriptions)
      - Doctor Recent Patients (via get_doctor_dashboard)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        today_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Resolve patient details from patients table
        cursor.execute(
            "SELECT id, age, gender, prakriti_primary FROM patients WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) LIMIT 1",
            (patient_name,)
        )
        pat_row = cursor.fetchone()
        patient_id = pat_row["id"] if pat_row else None
        age = pat_row["age"] if pat_row and pat_row["age"] else None
        gender = pat_row["gender"] if pat_row and pat_row["gender"] else None
        prakriti = pat_row["prakriti_primary"] if pat_row and pat_row["prakriti_primary"] else "Vata-Pitta"

        # Resolve doctor user_id & name for case record
        cursor.execute(
            """
            SELECT d.id AS doctor_id, d.user_id, u.full_name
            FROM doctors d
            JOIN users u ON u.id = d.user_id
            WHERE d.id = ? OR d.user_id = ?
            LIMIT 1
            """,
            (doctor_id, doctor_id)
        )
        doc_row = cursor.fetchone()
        doctor_user_id = doc_row["user_id"] if doc_row else doctor_id
        doctor_name = doc_row["full_name"] if doc_row else "Hospital Practitioner"

        status = "Absent" if absent else "Completed"
        complaint = suggestion if suggestion else ("Patient marked absent for scheduled follow-up" if absent else "Follow-up clinical consultation")
        diagnosis_val = "Absent (Did not attend)" if absent else (prescription or "Follow-up completed")

        # Insert a case record for this follow-up visit
        cursor.execute(
            """
            INSERT INTO cases (patient_id, doctor_id, patient_name, age, gender, prakriti, chief_complaint, diagnosis, status, created_at, case_date)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, DATE('now'))
            """,
            (
                patient_id,
                doctor_user_id,
                patient_name,
                age,
                gender,
                prakriti,
                complaint,
                diagnosis_val,
                status,
                today_str,
            )
        )
        case_id = cursor.lastrowid

        # Update previous cases for this patient that were marked 'Follow-up' or 'Active'
        cursor.execute(
            """
            UPDATE cases
            SET status = ?
            WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?))
              AND id != ?
              AND (LOWER(status) LIKE '%follow%' OR LOWER(status) = 'active')
            """,
            (status, patient_name, case_id)
        )

        # Update matching active appointment to Completed / Absent
        cursor.execute(
            """
            UPDATE appointments
            SET status = ?
            WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?))
              AND status NOT IN ('Completed', 'Cancelled', 'Absent')
            """,
            ("Absent" if absent else "Completed", patient_name)
        )

        # Save individual prescription medicines if provided (not absent)
        if not absent and prescription:
            for line in prescription.split("\n"):
                line = line.strip()
                if line:
                    cursor.execute(
                        """
                        INSERT INTO prescriptions (case_id, patient_id, medicine_name, dosage, timing, prescribed_date)
                        VALUES (?, ?, ?, ?, ?, DATE('now'))
                        """,
                        (case_id, patient_id, line, "", "", )
                    )

        # Audit log
        cursor.execute(
            "INSERT INTO audit_logs (action, details) VALUES (?, ?)",
            ("FOLLOWUP_PRESCRIPTION", f"Follow-up prescription saved for {patient_name} (case #{case_id}) by Dr. {doctor_name}.")
        )

        conn.commit()
        return {
            "success": True,
            "case_id": case_id,
            "patient_name": patient_name,
            "doctor_name": doctor_name,
            "status": status,
            "prescription": prescription or "",
            "suggestion": suggestion or "",
            "date": today_str,
            "message": f"Follow-up visit recorded for {patient_name}."
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def add_emergency_case(patient_name, age, gender, doctor_id, doctor_name, issue, triage_level="Emergency", bed_number="Triage Bay", status="Under Immediate Care"):
    """
    Inserts an acute emergency case (Atyayika Chikitsa).
    Immediately updates the hospital emergency triage registry for administrative and clinical visibility.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute(
            """
            INSERT INTO emergency_cases (patient_name, age, gender, doctor_id, doctor_name, issue, triage_level, bed_number, status, admitted_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (patient_name, age, gender, doctor_id, doctor_name, issue, triage_level, bed_number, status, now_str)
        )
        case_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO audit_logs (action, details) VALUES (?, ?)",
            ("EMERGENCY_CASE_ADDED", f"Emergency triage case #{case_id} registered for '{patient_name}' by '{doctor_name}' ({triage_level}, Bed: {bed_number}).")
        )
        conn.commit()
        return {
            "success": True,
            "case_id": case_id,
            "patient_name": patient_name,
            "age": age,
            "gender": gender,
            "doctor_name": doctor_name,
            "issue": issue,
            "triage_level": triage_level,
            "bed_number": bed_number,
            "status": status,
            "admitted_time": now_str,
            "message": f"Emergency case for {patient_name} recorded and transmitted to Admin triage."
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def add_article(title, author, category, minutes=15, source="AYURCASE Clinical Faculty", excerpt="", content="", icon="fa-solid fa-file-lines", image_url=""):
    """Saves a new research or clinical article published by a practitioner."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO articles (title, author, category, minutes, source, excerpt, content, icon, image_url)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (title, author, category, minutes or 15, source, excerpt, content, icon or "fa-solid fa-file-lines", image_url or "")
        )
        article_id = cursor.lastrowid
        cursor.execute(
            "INSERT INTO audit_logs (action, details) VALUES (?, ?)",
            ("ARTICLE_PUBLISHED", f"Clinical article '{title}' published by '{author}' in category '{category}'.")
        )
        conn.commit()
        return {
            "success": True,
            "article_id": article_id,
            "title": title,
            "author": author,
            "category": category,
            "image_url": image_url or "",
            "message": "Article successfully published."
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def get_all_articles():
    """Retrieves all clinical articles published in AYURCASE."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM articles ORDER BY id DESC")
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def get_patient_prescriptions(identifier):
    """
    Returns all prescriptions for a patient by ABHA ID, user ID, patient name, or patient ID.
    Used by the patient portal 'My Prescriptions' tab.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        target = str(identifier or "").strip()

        # Resolve patient record
        cursor.execute(
            """
            SELECT p.id, p.name, p.abha_id, p.user_id, u.username AS user_email, u.full_name
            FROM patients p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE p.abha_id = ? OR p.user_id = ? OR p.id = ?
               OR LOWER(TRIM(p.name)) = LOWER(TRIM(?))
               OR LOWER(TRIM(u.username)) = LOWER(TRIM(?))
               OR LOWER(TRIM(u.full_name)) = LOWER(TRIM(?))
            LIMIT 1
            """,
            (target, target, target, target, target, target)
        )
        pat = cursor.fetchone()
        patient_id = pat["id"] if pat else None
        patient_name = pat["name"] if pat else target
        patient_email = pat["user_email"] if pat and pat["user_email"] else ""

        if not pat:
            cursor.execute(
                """
                SELECT id, username, full_name
                FROM users
                WHERE LOWER(TRIM(username)) = LOWER(TRIM(?))
                   OR LOWER(TRIM(full_name)) = LOWER(TRIM(?))
                LIMIT 1
                """,
                (target, target)
            )
            u_row = cursor.fetchone()
            if u_row:
                patient_name = u_row["full_name"] or u_row["username"]
                patient_email = u_row["username"]
                cursor.execute("SELECT id, name FROM patients WHERE user_id = ? LIMIT 1", (u_row["id"],))
                p_sub = cursor.fetchone()
                if p_sub:
                    patient_id = p_sub["id"]
                    patient_name = p_sub["name"]

        # Fetch all cases for this patient
        cursor.execute(
            """
            SELECT c.id, c.chief_complaint, c.diagnosis, c.status, c.created_at,
                   u.full_name AS doctor_name, d.specialization
            FROM cases c
            LEFT JOIN users u ON u.id = c.doctor_id
            LEFT JOIN doctors d ON d.user_id = u.id
            WHERE (c.patient_id IS NOT NULL AND c.patient_id = ?)
               OR LOWER(TRIM(c.patient_name)) = LOWER(TRIM(?))
               OR LOWER(TRIM(c.patient_name)) = LOWER(TRIM(?))
            ORDER BY c.created_at DESC, c.id DESC
            """,
            (patient_id, patient_name, target)
        )
        cases = cursor.fetchall()

        results = []
        for case in cases:
            cursor.execute(
                """
                SELECT medicine_name, dosage, timing, anupana, duration, prescribed_date
                FROM prescriptions
                WHERE case_id = ?
                ORDER BY id ASC
                """,
                (case["id"],)
            )
            meds = [dict(r) for r in cursor.fetchall()]

            if not meds and patient_id:
                cursor.execute(
                    """
                    SELECT medicine_name, dosage, timing, anupana, duration, prescribed_date
                    FROM prescriptions
                    WHERE case_id IS NULL AND patient_id = ?
                    ORDER BY id ASC
                    """,
                    (patient_id,)
                )
                meds = [dict(r) for r in cursor.fetchall()]

            results.append({
                "case_id": case["id"],
                "chief_complaint": case["chief_complaint"] or "",
                "diagnosis": case["diagnosis"] or "",
                "status": case["status"] or "Active",
                "date": str(case["created_at"] or ""),
                "doctor_name": case["doctor_name"] or "Hospital Practitioner",
                "specialization": case["specialization"] or "AYUSH Practitioner",
                "medicines": meds,
            })

        # Also reconcile lab_reports (in case any exist without an associated case)
        cursor.execute(
            """
            SELECT lr.*, u.full_name AS doc_user_name, d.specialization
            FROM lab_reports lr
            LEFT JOIN users u ON u.id = lr.doctor_id
            LEFT JOIN doctors d ON d.user_id = u.id
            WHERE (lr.patient_id IS NOT NULL AND lr.patient_id = ?)
               OR LOWER(TRIM(lr.patient_name)) = LOWER(TRIM(?))
               OR LOWER(TRIM(lr.patient_name)) = LOWER(TRIM(?))
               OR (lr.patient_email IS NOT NULL AND lr.patient_email != '' AND LOWER(TRIM(lr.patient_email)) = LOWER(TRIM(?)))
            ORDER BY lr.created_at DESC, lr.id DESC
            """,
            (patient_id, patient_name, target, patient_email or target)
        )
        l_reports = cursor.fetchall()

        existing_report_signatures = set()
        for r in results:
            complaint = (r.get("chief_complaint") or "").lower()
            if "diagnostic investigation" in complaint or "sugar:" in complaint:
                existing_report_signatures.add(complaint)

        for lr in l_reports:
            lr_sugar_sig = f"sugar: {str(lr['sugar'] or '').strip()}".lower()
            if any(lr_sugar_sig in s for s in existing_report_signatures):
                continue

            vitals_parts = []
            if lr["sugar"]:
                vitals_parts.append(f"Sugar: {lr['sugar']}")
            if lr["pressure"]:
                vitals_parts.append(f"BP: {lr['pressure']}")
            if lr["hemoglobin"]:
                vitals_parts.append(f"Hb: {lr['hemoglobin']}")
            vitals_str = ", ".join(vitals_parts) if vitals_parts else "Diagnostic Vitals verified"

            lr_meds = [{
                "medicine_name": f"Clinical Vitals: {vitals_str}",
                "dosage": "Clinical Reference Target",
                "timing": "Regular Monitoring",
                "anupana": "Pathya diet",
                "duration": "Ongoing",
                "prescribed_date": str(lr["created_at"] or "")[:10]
            }]

            notes_val = str(lr["notes"] or "").strip()
            if notes_val:
                for line in notes_val.split("\n"):
                    line = line.strip()
                    if line:
                        lr_meds.append({
                            "medicine_name": f"Pathya Regimen: {line}",
                            "dosage": "As instructed",
                            "timing": "Daily regimen",
                            "anupana": "Warm water / Herbal infusion",
                            "duration": "Follow-up",
                            "prescribed_date": str(lr["created_at"] or "")[:10]
                        })

            results.append({
                "case_id": f"lab_{lr['id']}",
                "chief_complaint": f"Diagnostic Investigation: {vitals_str}. Pathya Regimen: {notes_val or 'Maintain balanced Ayurvedic diet.'}",
                "diagnosis": "Pathology Investigation & Clinical Vitals",
                "status": "Active Prescription",
                "date": str(lr["created_at"] or ""),
                "doctor_name": lr["doctor_name"] or lr["doc_user_name"] or "Dr. Arindam Sen",
                "specialization": lr["specialization"] or "AYUSH Practitioner & Pathology",
                "medicines": lr_meds
            })

        return results
    finally:
        conn.close()


# =====================================================
# CLINICAL LAB REPORTS & DIAGNOSTIC INVESTIGATIONS
# =====================================================

def add_lab_report(
    patient_name,
    sugar,
    pressure,
    hemoglobin,
    notes=None,
    doctor_id=None,
    doctor_name=None,
    patient_email=None,
):
    """
    Saves a clinical lab investigation report for a patient into the database,
    synchronizes an active case and prescription entry for the patient's 'My Prescriptions' portal,
    and dispatches a confirmation email to the patient's registered email address.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        p_name = str(patient_name or "").strip()
        if not p_name:
            return {"success": False, "error": "Patient name is required"}

        # 1. Resolve patient ID and registered email
        cursor.execute(
            """
            SELECT p.id, p.name, p.user_id, u.username AS user_email, p.age, p.gender, p.prakriti_primary
            FROM patients p
            LEFT JOIN users u ON p.user_id = u.id
            WHERE LOWER(TRIM(p.name)) = LOWER(TRIM(?))
               OR p.id = ?
            LIMIT 1
            """,
            (p_name, p_name)
        )
        pat = cursor.fetchone()
        patient_id = pat["id"] if pat else None
        age = pat["age"] if pat and pat["age"] else None
        gender = pat["gender"] if pat and pat["gender"] else None
        prakriti = pat["prakriti_primary"] if pat and pat["prakriti_primary"] else "Vata-Pitta"
        resolved_email = (
            (patient_email or "").strip()
            or (pat["user_email"] if pat and pat["user_email"] and "@" in pat["user_email"] else "")
        )

        # Fallback user lookup if patient wasn't in patients table directly
        if not patient_id or not resolved_email:
            cursor.execute(
                """
                SELECT id, username, full_name FROM users
                WHERE (LOWER(TRIM(full_name)) = LOWER(TRIM(?))
                   OR LOWER(TRIM(username)) = LOWER(TRIM(?)))
                LIMIT 1
                """,
                (p_name, p_name)
            )
            u_row = cursor.fetchone()
            if u_row:
                if not resolved_email and u_row["username"] and "@" in u_row["username"]:
                    resolved_email = u_row["username"]
                if not patient_id:
                    cursor.execute("SELECT id, age, gender, prakriti_primary FROM patients WHERE user_id = ? LIMIT 1", (u_row["id"],))
                    p_sub = cursor.fetchone()
                    if p_sub:
                        patient_id = p_sub["id"]
                        age = p_sub["age"] or age
                        gender = p_sub["gender"] or gender
                        prakriti = p_sub["prakriti_primary"] or prakriti

        # If patient record doesn't exist yet, create one so patient has an ABHA ID and persistent record
        if not patient_id:
            try:
                import random
                dummy_abha = f"ABHA-{random.randint(1000, 9999)}-{random.randint(1000, 9999)}"
                cursor.execute(
                    """
                    INSERT INTO patients (name, abha_id, prakriti_primary, created_at)
                    VALUES (?, ?, 'Vata-Pitta', datetime('now'))
                    """,
                    (p_name, dummy_abha)
                )
                patient_id = cursor.lastrowid
            except Exception as pat_create_err:
                print(f"[DATABASE] Notice auto-creating patient: {pat_create_err}")

        # Default fallback email for local demo consistency if none found
        if not resolved_email:
            resolved_email = f"{p_name.lower().replace(' ', '.')}@example.com"

        # 2. Resolve doctor name & doctor user_id
        d_name = str(doctor_name or "").strip()
        doc_user_id = doctor_id
        if doctor_id:
            cursor.execute("SELECT id, full_name FROM users WHERE id = ? LIMIT 1", (doctor_id,))
            d_row = cursor.fetchone()
            if d_row:
                doc_user_id = d_row["id"]
                if not d_name:
                    d_name = d_row["full_name"]
        if not d_name:
            cursor.execute("SELECT id, full_name FROM users WHERE role = 'doctor' LIMIT 1")
            d_doc = cursor.fetchone()
            if d_doc:
                doc_user_id = d_doc["id"]
                d_name = d_doc["full_name"]
            else:
                d_name = "Dr. Arindam Sen"

        # 3. Insert into lab_reports
        clean_sugar = str(sugar or "").strip()
        clean_pressure = str(pressure or "").strip()
        clean_hb = str(hemoglobin or "").strip()
        clean_notes = str(notes or "").strip() or "Vital indicators evaluated. Maintain Pathya-Apathya diet."
        today_full = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            INSERT INTO lab_reports (
                patient_id, patient_name, patient_email, doctor_id, doctor_name,
                sugar, pressure, hemoglobin, notes, status, email_status, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'Completed', 'Dispatched', ?)
            """,
            (
                patient_id,
                p_name,
                resolved_email,
                doc_user_id,
                d_name,
                clean_sugar,
                clean_pressure,
                clean_hb,
                clean_notes,
                today_full,
            )
        )
        report_id = cursor.lastrowid

        # 4. Synchronize an active clinical Case & Prescription entry for patient's "My Prescriptions" portal
        vitals_summary = f"Sugar: {clean_sugar} mg/dL, BP: {clean_pressure} mmHg, Hb: {clean_hb} g/dL"
        complaint_text = f"Diagnostic Investigation: {vitals_summary}"
        if clean_notes:
            complaint_text += f" | Pathya Advice: {clean_notes}"

        diag_text = "Pathology Investigation & Clinical Vitals Assessment"

        cursor.execute(
            """
            INSERT INTO cases (
                patient_id, doctor_id, patient_name, age, gender, prakriti,
                chief_complaint, diagnosis, status, created_at, case_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'Active Prescription', ?, DATE('now'))
            """,
            (
                patient_id,
                doc_user_id,
                p_name,
                age,
                gender,
                prakriti,
                complaint_text,
                diag_text,
                today_full
            )
        )
        case_id = cursor.lastrowid

        # 5. Insert Prescriptions for this case:
        # A) Diagnostic Vitals monitoring formulation item
        cursor.execute(
            """
            INSERT INTO prescriptions (
                case_id, patient_id, medicine_name, dosage, timing, anupana, duration, prescribed_date
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'))
            """,
            (
                case_id,
                patient_id,
                f"Diagnostic Vitals ({vitals_summary})",
                "Clinical Reference Range Target",
                "Daily Monitoring",
                "Pathya diet",
                "30 Days"
            )
        )

        # B) Clinical Observations & Pathya Regimen items
        if clean_notes:
            for line in clean_notes.split("\n"):
                line = line.strip()
                if line:
                    med_label = f"Pathya Regimen: {line}" if not line.lower().startswith("pathya") else line
                    cursor.execute(
                        """
                        INSERT INTO prescriptions (
                            case_id, patient_id, medicine_name, dosage, timing, anupana, duration, prescribed_date
                        )
                        VALUES (?, ?, ?, ?, ?, ?, ?, DATE('now'))
                        """,
                        (
                            case_id,
                            patient_id,
                            med_label,
                            "As advised by attending doctor",
                            "Daily regimen",
                            "Warm water / Herbal infusion",
                            "Follow-up review"
                        )
                    )

        # 6. Update any active appointment to Completed
        cursor.execute(
            """
            UPDATE appointments
            SET status = 'Completed'
            WHERE (LOWER(TRIM(patient_name)) = LOWER(TRIM(?))
               OR (patient_id IS NOT NULL AND patient_id = ?))
               AND status NOT IN ('Completed', 'Cancelled', 'Absent')
            """,
            (p_name, patient_id)
        )

        # 7. Audit log
        cursor.execute(
            "INSERT INTO audit_logs (action, details) VALUES (?, ?)",
            ("LAB_REPORT_PRESCRIPTION", f"Clinical lab report & prescription saved for {p_name} (case #{case_id}) by Dr. {d_name}.")
        )

        conn.commit()

        # 8. Dispatch Email to patient's registered email
        report_payload = {
            "id": report_id,
            "case_id": case_id,
            "patient_name": p_name,
            "patient_email": resolved_email,
            "doctor_name": d_name,
            "sugar": clean_sugar,
            "pressure": clean_pressure,
            "hemoglobin": clean_hb,
            "notes": clean_notes,
        }

        try:
            try:
                from email_service import send_lab_report_email_async
            except ImportError:
                from backend.email_service import send_lab_report_email_async
            send_lab_report_email_async(report_payload)
        except Exception as email_err:
            print(f"[DATABASE] Lab report email dispatch error: {email_err}")

        return {
            "success": True,
            "report_id": report_id,
            "case_id": case_id,
            "lab_report": {
                **report_payload,
                "status": "Completed",
                "email_status": "Dispatched",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def get_patient_lab_reports(identifier):
    """
    Returns all clinical laboratory reports for a patient by ABHA ID, name, email, or user ID.
    Used by the patient portal to render the verified diagnostic vitals chart.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        target = str(identifier or "").strip()
        cursor.execute(
            """
            SELECT lr.*, p.abha_id
            FROM lab_reports lr
            LEFT JOIN patients p ON lr.patient_id = p.id
            WHERE LOWER(TRIM(lr.patient_name)) = LOWER(TRIM(?))
               OR lr.patient_email = ?
               OR lr.patient_id = ?
               OR (p.abha_id IS NOT NULL AND p.abha_id = ?)
            ORDER BY lr.created_at DESC, lr.id DESC
            """,
            (target, target, target, target)
        )
        reports = [dict(r) for r in cursor.fetchall()]
        return reports
    finally:
        conn.close()


def get_all_lab_reports(limit=100):
    """Returns all recorded lab reports in AYURCASE."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT * FROM lab_reports ORDER BY created_at DESC, id DESC LIMIT ?", (limit,))
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def ensure_upcoming_ai_reviews(cursor, conn):
    """Seeds initial upcoming patient queries with AI solutions for doctor evaluation."""
    try:
        cursor.execute("SELECT COUNT(*) FROM ai_reviews WHERE status = 'Upcoming';")
        count = cursor.fetchone()[0]
        if count == 0:
            samples = [
                (
                    "Aditi Sen",
                    "Experiencing intense burning sensation in the chest and stomach after meals, with sour acid regurgitation and occasional nausea in the morning.",
                    "Assessment: Urdhwaga Amlapitta (Pitta Prakopa). Recommended Protocol: Avipattikar Churna 3g BD with warm water before meals, Kamadudha Rasa (Mukta Yukta) 250mg morning & night, Sutshekhar Rasa 125mg BD with honey. Pathya: Coconut water, pomegranate, strictly avoid sour, fermented, and deep-fried foods.",
                    "Upcoming",
                    0,
                    "",
                    1,
                    "Dr. Arindam Sen"
                ),
                (
                    "Rahul Verma",
                    "Persistent stiffness and crepitus (cracking sounds) in both knees, difficulty climbing stairs and standing up after sitting. Pain increases in cold weather.",
                    "Assessment: Sandhigata Vata (Osteoarthritis / Janu Sandhigata Vata). Recommended Protocol: Yogaraj Guggulu 2 tablets BD with Dashamoolarishta (20ml with equal warm water post-meal); local Janu Basti or Abhyanga with warm Mahanarayan Taila followed by Nadi Swedana. Rasayana: Ashwagandha Lehyam 5g at bedtime.",
                    "Upcoming",
                    0,
                    "",
                    1,
                    "Dr. Arindam Sen"
                ),
                (
                    "Priya Sharma",
                    "Chronic insomnia, unable to fall asleep until 3 AM, racing thoughts, restlessness, dry skin, and irregular bowel movements.",
                    "Assessment: Anidra / Mano-vaha Sroto Dusti (Vata-Prana aggravation). Recommended Protocol: Brahmi Vati 1 tablet twice daily with Saraswatarishta (15ml post lunch and dinner); Ashwagandharishta 15ml post meals. External: Shirodhara with Ksheerabala Taila or nightly Padabhyanga (warm sesame/Ksheerabala oil on feet).",
                    "Upcoming",
                    0,
                    "",
                    1,
                    "Dr. Arindam Sen"
                ),
                (
                    "Vikram Malhotra",
                    "Heavy bloating and fullness after small meals, slow sluggish digestion, thick white coating on tongue every morning, and lethargy after lunch.",
                    "Assessment: Agnimandya with Sama Kapha-Vataja Dushti. Recommended Protocol: Chitrakadi Vati 2 tablets twice daily before food with warm water; Hingwashtak Churna 2g with first morsel of food with warm cow ghee; Trikatu Churna 1g BD with honey. Diet: Ginger-cumin tea, avoid heavy dairy.",
                    "Upcoming",
                    0,
                    "",
                    1,
                    "Dr. Arindam Sen"
                )
            ]
            cursor.executemany(
                """
                INSERT INTO ai_reviews (patient_name, patient_question, ai_answer, status, rating, comment, doctor_id, doctor_name)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?);
                """,
                samples
            )
            conn.commit()
    except Exception as exc:
        print("ensure_upcoming_ai_reviews error:", exc)


def add_upcoming_patient_ai_query(patient_name, patient_question, ai_answer, doctor_id=1, doctor_name="Dr. Arindam Sen"):
    """Queues a patient question and AI solution for doctor's upcoming review."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO ai_reviews (patient_name, patient_question, ai_answer, status, rating, comment, doctor_id, doctor_name)
            VALUES (?, ?, ?, 'Upcoming', 0, '', ?, ?);
            """,
            (patient_name or "Patient", str(patient_question).strip(), str(ai_answer).strip(), doctor_id or 1, doctor_name or "Dr. Arindam Sen")
        )
        new_id = cursor.lastrowid
        conn.commit()
        return {"success": True, "id": new_id}
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


def add_ai_review(patient_question, ai_answer, rating, comment="", doctor_id=None, doctor_name=None, review_id=None, patient_name=None):
    """
    Saves a doctor's clinical evaluation of an AI response and patient question.
    If review_id is provided, updates an existing upcoming case to Reviewed.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        doc_id = _resolve_doctor_user_id(cursor, doctor_id) if doctor_id else None
        doc_name = (doctor_name or "").strip()
        if not doc_name and doc_id:
            cursor.execute("SELECT full_name FROM users WHERE id = ?;", (doc_id,))
            row = cursor.fetchone()
            if row:
                doc_name = row[0]
        if not doc_name:
            doc_name = "Dr. Arindam Sen"

        int_rating = int(rating)
        if int_rating < 1:
            int_rating = 1
        elif int_rating > 5:
            int_rating = 5

        p_name = (patient_name or "").strip()

        if review_id:
            update_fields = ["doctor_id = ?", "doctor_name = ?", "rating = ?", "comment = ?", "status = 'Reviewed'", "reviewed_at = CURRENT_TIMESTAMP"]
            params = [doc_id, doc_name, int_rating, str(comment or "").strip()]
            if p_name:
                update_fields.append("patient_name = ?")
                params.append(p_name)
            if patient_question:
                update_fields.append("patient_question = ?")
                params.append(str(patient_question).strip())
            if ai_answer:
                update_fields.append("ai_answer = ?")
                params.append(str(ai_answer).strip())

            params.append(review_id)
            cursor.execute(f"UPDATE ai_reviews SET {', '.join(update_fields)} WHERE id = ?;", params)
            target_id = review_id
        else:
            cursor.execute(
                """
                INSERT INTO ai_reviews (doctor_id, doctor_name, patient_name, patient_question, ai_answer, rating, comment, status, reviewed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, 'Reviewed', CURRENT_TIMESTAMP);
                """,
                (doc_id, doc_name, p_name or "Patient", str(patient_question).strip(), str(ai_answer).strip(), int_rating, str(comment or "").strip())
            )
            target_id = cursor.lastrowid

        conn.commit()

        cursor.execute("SELECT * FROM ai_reviews WHERE id = ?;", (target_id,))
        created_row = cursor.fetchone()
        return {
            "success": True,
            "review_id": target_id,
            "review": dict(created_row) if created_row else {
                "id": target_id,
                "doctor_id": doc_id,
                "doctor_name": doc_name,
                "patient_name": p_name or "Patient",
                "patient_question": patient_question,
                "ai_answer": ai_answer,
                "rating": int_rating,
                "comment": comment,
                "status": "Reviewed",
                "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


save_doctor_ai_review = add_ai_review


def get_all_ai_reviews(status=None, limit=50):
    """Returns clinical AI reviews, optionally filtered by status ('Upcoming' or 'Reviewed')."""
    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        if status:
            cursor.execute(
                """
                SELECT * FROM ai_reviews
                WHERE LOWER(status) = LOWER(?)
                ORDER BY CASE WHEN status = 'Upcoming' THEN id ELSE -id END ASC, created_at DESC
                LIMIT ?;
                """,
                (status, limit)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM ai_reviews
                ORDER BY CASE WHEN status = 'Upcoming' THEN 0 ELSE 1 END, id DESC
                LIMIT ?;
                """,
                (limit,)
            )
        return [dict(r) for r in cursor.fetchall()]
    finally:
        conn.close()


def update_patient_name_everywhere(old_name, new_name, patient_id=None):
    """
    Updates a patient's name across patients, users, cases, appointments,
    prescriptions, lab_reports, and ai_reviews.
    """
    old_clean = str(old_name or "").strip()
    new_clean = str(new_name or "").strip()
    if not new_clean:
        return {"success": False, "error": "New patient name cannot be empty."}

    conn = get_db_connection()
    cursor = conn.cursor()
    try:
        # 1. Update patients table
        if patient_id:
            cursor.execute("UPDATE patients SET name = ? WHERE id = ? OR name = ?;", (new_clean, patient_id, old_clean))
        else:
            cursor.execute("UPDATE patients SET name = ? WHERE LOWER(TRIM(name)) = LOWER(TRIM(?));", (new_clean, old_clean))

        # 2. Update users table if user exists
        cursor.execute("UPDATE users SET full_name = ? WHERE LOWER(TRIM(full_name)) = LOWER(TRIM(?));", (new_clean, old_clean))

        # 3. Update cases table
        cursor.execute("UPDATE cases SET patient_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (new_clean, old_clean))

        # 4. Update appointments table
        cursor.execute("UPDATE appointments SET patient_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (new_clean, old_clean))

        # 5. Update ai_reviews table
        cursor.execute("UPDATE ai_reviews SET patient_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (new_clean, old_clean))

        # 6. Update lab_reports table if exists
        try:
            cursor.execute("UPDATE lab_reports SET patient_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (new_clean, old_clean))
        except Exception:
            pass

        # 7. Update prescriptions table if exists
        try:
            cursor.execute("UPDATE prescriptions SET patient_name = ? WHERE LOWER(TRIM(patient_name)) = LOWER(TRIM(?));", (new_clean, old_clean))
        except Exception:
            pass

        conn.commit()
        return {
            "success": True,
            "old_name": old_clean,
            "new_name": new_clean,
            "message": f"Patient name updated to '{new_clean}' successfully."
        }
    except Exception as exc:
        conn.rollback()
        return {"success": False, "error": str(exc)}
    finally:
        conn.close()


if __name__ == "__main__":
    init_db()
    print("AYURCASE Database successfully initialized at:", DB_PATH)


