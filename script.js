/* =====================================================
   AYURCASE
   Interactive JavaScript
   HTML + CSS UNCHANGED
   ===================================================== */

/* =====================================================
   ELEMENTS
   ===================================================== */

const caseModal = document.getElementById("caseModal");

const newCaseButtons = document.querySelectorAll(".new-case-btn, .case-action");

const closeModal = document.getElementById("closeModal");
const cancelModal = document.getElementById("cancelModal");
const caseForm = document.getElementById("caseForm");

const toast = document.getElementById("toast");
const toastMessage = document.getElementById("toastMessage");

const themeButton = document.querySelector(".theme-btn");
const mobileMenu = document.querySelector(".mobile-menu");
const sidebar = document.querySelector(".sidebar");

const navItems = document.querySelectorAll(".nav-item");

/* =====================================================
   TOAST
   ===================================================== */

let toastTimer;

function showToast(message, type = "success") {
  if (!toast || !toastMessage) return;

  toastMessage.textContent = message;
  const isError = type === "error" || /failed|error|unavailable|danger|invalid/i.test(message);
  toast.classList.toggle("toast-error", isError);
  const toastTitle = toast.querySelector("strong");
  const toastIcon = toast.querySelector(".toast-icon i");
  if (toastTitle) toastTitle.textContent = isError ? "Failed" : "Success";
  if (toastIcon) toastIcon.className = isError ? "fa-solid fa-circle-xmark" : "fa-solid fa-check";

  toast.classList.add("show");

  clearTimeout(toastTimer);

  toastTimer = setTimeout(() => {
    toast.classList.remove("show");
  }, 3500);
}

/* =====================================================
   NEW CASE MODAL
   ===================================================== */

function openCaseModal() {
  if (!caseModal) return;

  caseModal.classList.add("show");

  document.body.style.overflow = "hidden";
}

function closeCaseModal() {
  if (!caseModal) return;

  caseModal.classList.remove("show");

  document.body.style.overflow = "";
}

/* New Case buttons */

newCaseButtons.forEach((button) => {
  button.addEventListener("click", function () {
    openCaseModal();
  });
});
/* Close button */

if (closeModal) {
  closeModal.addEventListener("click", closeCaseModal);
}

/* Cancel button */

if (cancelModal) {
  cancelModal.addEventListener("click", closeCaseModal);
}

/* Click outside modal */

if (caseModal) {
  caseModal.addEventListener("click", function (event) {
    if (event.target === caseModal) {
      closeCaseModal();
    }
  });
}

/* Escape key */

document.addEventListener("keydown", function (event) {
  if (
    event.key === "Escape" &&
    caseModal &&
    caseModal.classList.contains("show")
  ) {
    closeCaseModal();
  }
});

/* =====================================================
   CASE FORM
   ===================================================== */

// Cases are supplied by the signed-in practitioner's database record. Do not
// seed browser-only sample patients: that allowed unrelated histories to show
// up in another doctor's workspace.
if (localStorage.getItem("ayurcase-cases") === null) {
  localStorage.setItem("ayurcase-cases", JSON.stringify([]));
}
renderPatientsdashboard();
if (caseForm) {
  caseForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const nameInput = document.getElementById("casePatientName") || caseForm.querySelector("input[type='text']");
    const ageInput = document.getElementById("casePatientAge") || caseForm.querySelector("input[type='number']");
    const genderInput = document.getElementById("casePatientGender") || caseForm.querySelector("select");
    const complaintInput = document.getElementById("casePatientComplaint") || caseForm.querySelector("textarea");

    const patientName = (nameInput ? nameInput.value : "").trim();
    const age = (ageInput ? ageInput.value : "").trim();
    const gender = (genderInput ? genderInput.value : "").trim() || "Other";
    const complaint = (complaintInput ? complaintInput.value : "").trim() || "Follow-up consultation";

    if (!patientName) {
      if (typeof showToast === "function") showToast("Please enter patient full name.");
      if (nameInput) nameInput.focus();
      return;
    }

    let doctorId = 1;
    let doctorName = "Dr. Arindam Sen";
    try {
      if (typeof window.getActiveDoctorId === "function") doctorId = window.getActiveDoctorId();
      else if (typeof getActiveDoctorId === "function") doctorId = getActiveDoctorId();
      if (typeof window.getActiveDoctorName === "function") doctorName = window.getActiveDoctorName();
      else if (typeof getActiveDoctorName === "function") doctorName = getActiveDoctorName();
    } catch (_) {}

    const todayIso = new Date().toISOString().slice(0, 10);
    const nowTime = new Date().toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit", hour12: true });

    const followUpPayload = {
      patient_name: patientName,
      doctor_name: doctorName,
      doctor_id: doctorId,
      age: age ? Number(age) : null,
      gender: gender,
      appointment_date: todayIso,
      appointment_time: nowTime,
      consultation_type: "Follow-up Consultation",
      symptoms_notes: complaint,
      status: "Confirmed",
    };

    const submitBtn = caseForm.querySelector("button[type='submit']") || document.getElementById("caseContinueBtn");
    const origBtnHtml = submitBtn ? submitBtn.innerHTML : "";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Adding to Follow-ups...`;
    }

    let data = null;
    try {
      const api = typeof window.getApiHost === "function" ? window.getApiHost() : (typeof getApiHost === "function" ? getApiHost() : "");
      const response = await fetch(`${api}/api/appointments`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(followUpPayload),
      });

      if (response.ok) {
        data = await response.json();
      } else {
        const errJson = await response.json().catch(() => null);
        console.warn("API appointments booking notice:", errJson);
      }
    } catch (error) {
      console.warn("Network notice creating follow-up:", error);
    }

    // Immediately create new follow-up item
    const newFollowUpItem = {
      id: data?.appointment?.id || Date.now(),
      patient_id: data?.appointment?.patient_id || null,
      doctor_id: doctorId,
      patient_name: patientName,
      doctor_name: doctorName,
      appointment_date: todayIso,
      appointment_time: nowTime,
      consultation_type: "Follow-up Consultation",
      symptoms_notes: complaint,
      status: "Confirmed",
    };

    // Immediately add patient to latestDoctorDashboard follow_ups list
    if (typeof latestDoctorDashboard !== "undefined" && latestDoctorDashboard) {
      const currentFollowUps = Array.isArray(latestDoctorDashboard.follow_ups) ? latestDoctorDashboard.follow_ups : [];
      latestDoctorDashboard.follow_ups = [
        newFollowUpItem,
        ...currentFollowUps.filter(item => (item.patient_name || item.name || "").trim().toLowerCase() !== patientName.toLowerCase())
      ];
      if (!latestDoctorDashboard.stats) latestDoctorDashboard.stats = {};
      latestDoctorDashboard.stats.follow_ups = latestDoctorDashboard.follow_ups.length;

      if (typeof renderDoctorStats === "function") renderDoctorStats(latestDoctorDashboard.stats);
      if (typeof renderDoctorPracticeSummary === "function") renderDoctorPracticeSummary(latestDoctorDashboard);
      if (typeof renderDoctorFollowUps === "function") renderDoctorFollowUps(latestDoctorDashboard.follow_ups);
      if (typeof renderFollowUpsModal === "function") renderFollowUpsModal(latestDoctorDashboard.follow_ups);
    }

    // Direct DOM prepend to #doctorAppointmentsList if needed
    const apptContainer = document.getElementById("doctorAppointmentsList");
    if (apptContainer && (!latestDoctorDashboard || !latestDoctorDashboard.follow_ups || !latestDoctorDashboard.follow_ups.length)) {
      const emptyState = apptContainer.querySelector(".empty-state");
      if (emptyState) apptContainer.innerHTML = "";
      const row = document.createElement("div");
      row.className = "patient-row";
      row.innerHTML = `
        <div class="patient-avatar avatar-1">${patientName.slice(0, 2).toUpperCase()}</div>
        <div class="patient-info">
          <strong>${patientName}</strong>
          <span>Today • ${nowTime}</span>
        </div>
        <div class="patient-complaint">
          <span>Reason for visit</span>
          <strong>${complaint}</strong>
        </div>
        <span class="status Active-status">Confirmed</span>
        <i class="fa-solid fa-chevron-right more-btn" aria-hidden="true"></i>
      `;
      row.addEventListener("click", () => {
        if (typeof window.openDoctorFollowupPrescriptionModal === "function") {
          window.openDoctorFollowupPrescriptionModal(newFollowUpItem);
        }
      });
      apptContainer.prepend(row);
    }

    closeCaseModal();
    caseForm.reset();
    if (typeof showToast === "function") {
      showToast(`${patientName} added to follow-up visits.`);
    }

    if (submitBtn) {
      submitBtn.disabled = false;
      submitBtn.innerHTML = origBtnHtml;
    }

    // Background sync full dashboard from database
    try {
      if (typeof window.loadDoctorAppointments === "function") {
        await window.loadDoctorAppointments();
      } else if (typeof loadDoctorAppointments === "function") {
        await loadDoctorAppointments();
      }
    } catch (_) {}
  });
}

/* =====================================================
   THEME
   ===================================================== */

let darkMode = localStorage.getItem("ayurcase-dark") === "true";

function updateTheme() {
  if (!themeButton) return;

  if (darkMode) {
    document.body.classList.add("dark");

    themeButton.innerHTML = '<i class="fa-solid fa-sun"></i>';

    themeButton.title = "Switch to Light Mode";
  } else {
    document.body.classList.remove("dark");

    themeButton.innerHTML = '<i class="fa-solid fa-moon"></i>';

    themeButton.title = "Switch to Dark Mode";
  }
}

updateTheme();

if (themeButton) {
  themeButton.addEventListener("click", function () {
    darkMode = !darkMode;

    localStorage.setItem("ayurcase-dark", darkMode);

    updateTheme();

    showToast(darkMode ? "Dark mode enabled." : "Light mode enabled.");
  });
}

/* =====================================================
   MOBILE SIDEBAR
   ===================================================== */

if (mobileMenu && sidebar) {
  mobileMenu.addEventListener("click", function () {
    sidebar.classList.toggle("open");
  });
}

/* =====================================================
   WORKSPACE SYSTEM
   ===================================================== */

function openWorkspace(title, description, icon) {
  document.getElementById("learnWishlistView")?.remove();
  document.getElementById("learnCompletedView")?.remove();

  let workspace = document.getElementById("ayurcaseWorkspace");

  if (!workspace) {
    workspace = document.createElement("div");

    workspace.id = "ayurcaseWorkspace";

    workspace.innerHTML = `

            <div class="workspace-inner">

                <button
                    class="workspace-close"
                    id="workspaceClose"
                >
                    <i class="fa-solid fa-xmark close-btn"></i>
                </button>


                <div class="workspace-icon">

                    <i class="${icon}"></i>

                </div>


                <span class="workspace-label">
                    AYURCASE WORKSPACE
                </span>


                <h2 id="workspaceTitle">
                    ${title}
                </h2>


                <p id="workspaceDescription">
                    ${description}
                </p>


                <div
                    id="workspaceContent"
                    class="workspace-content"
                ></div>

            </div>

        `;

    workspace.addEventListener("click", (e) => {
      if (e.target.parentElement.classList.contains("cases-close-btn")) {
        const targ = e.target
          .closest(".workspace-box")
          .firstElementChild.textContent.trim();
        let patients = JSON.parse(localStorage.getItem("ayurcase-cases"));
        const updatedPatients = patients.filter((p) => p.name !== targ);
        localStorage.setItem("ayurcase-cases", JSON.stringify(updatedPatients));
        renderPatientsdashboard();
        openPatientsWorkspace();
      }
    });

    document.body.appendChild(workspace);

    const style = document.createElement("style");

    style.id = "workspaceStyles";

    style.textContent = `

            #ayurcaseWorkspace {

                position:fixed;

                inset:0;

                background:rgba(9,27,19,.62);

                backdrop-filter:blur(8px);

                z-index:700;

                display:flex;

                align-items:center;

                justify-content:center;

                padding:20px;

            }


            .workspace-inner {

                position:relative;

                width:min(900px,100%);

                max-height:90vh;

                overflow-y:auto;

                background:var(--cream);

                color:var(--text);

                border-radius:22px;

                padding:32px;

                box-shadow:
                    0 30px 100px rgba(0,0,0,.25);

            }


            .workspace-close {

                position:absolute;

                right:20px;

                top:20px;

                width:32px;

                height:32px;

                border-radius:9px;

                background:#eef1ed;

                color:#68766e;

                border:none;

                cursor:pointer;

            }


            .workspace-icon {

                width:48px;

                height:48px;

                border-radius:14px;

                background:#e4eee6;

                color:#3c7650;

                display:flex;

                align-items:center;

                justify-content:center;

                font-size:18px;

                margin-bottom:15px;

            }


            .workspace-label {

                font-size:8px;

                letter-spacing:1.5px;

                color:#91a097;

                font-weight:700;

            }


            .workspace-inner h2 {

                font-family:"Playfair Display",serif;

                font-size:28px;

                margin:5px 0 7px;

            }


            .workspace-inner > p {

                font-size:11px;

                color:var(--muted);

                margin-bottom:25px;

            }


            .workspace-content {

                display:grid;

                gap:12px;

            }


            .workspace-box {

                background:white;

                border:1px solid var(--border);

                border-radius:14px;

                position:relative;

                padding:16px;

            }


            body.dark .workspace-box {

                background:#18231d;

            }


            body.dark .workspace-close {

                background:#26332c;

                color:#a9b8ae;

            }


            .workspace-box strong {

                font-size:15px;

            }


            .workspace-box span {

                display:block;

                color:var(--muted);

                font-size:14px;

                margin-top:5px;

                line-height:1.6;

            }


            .workspace-action {

                margin-top:12px;

                padding:9px 13px;

                border-radius:9px;

                background:#286247;

                color:white;

                font-size:9px;

                font-weight:600;

                border:none;

                cursor:pointer;

            }


            .workspace-action:hover {

                opacity:.9;

            }


            .help-option {

                display:flex;

                align-items:flex-start;

                gap:12px;

            }


            .help-option-icon {

                width:36px;

                height:36px;

                min-width:36px;

                border-radius:10px;

                background:#e4eee6;

                color:#286247;

                display:flex;

                align-items:center;

                justify-content:center;

            }


            body.dark .help-option-icon {

                background:#263d31;

                color:#9bc8a8;

            }


            .help-option-content {

                flex:1;

            }


            .help-option-content strong {

                display:block;

                font-size:11px;

                margin-bottom:4px;

            }


            .help-option-content span {

                margin-top:0;

            }


            .notification-item {

                display:flex;

                gap:12px;

                padding:13px;

                border-radius:12px;

                border:1px solid var(--border);

                background:white;

            }


            body.dark .notification-item {

                background:#18231d;

            }


            .notification-dot {

                width:8px;

                height:8px;

                min-width:8px;

                border-radius:50%;

                background:#286247;

                margin-top:5px;

            }


            .notification-content strong {

                display:block;

                font-size:10px;

            }


            .notification-content span {

                display:block;

                font-size:9px;

                color:var(--muted);

                margin-top:4px;

                line-height:1.5;

            }


            .notification-time {

                font-size:8px !important;

                opacity:.7;

            }
#aiResult h1,
#aiResult h2,
#aiResult h3 {
    margin-top: 20px;
    margin-bottom: 8px;
    line-height: 1.3;
}

#aiResult h1:first-child,
#aiResult h2:first-child,
#aiResult h3:first-child {
    margin-top: 0;
}

#aiResult p {
    margin: 10px 0;
}

#aiResult ul,
#aiResult ol {
    margin: 8px 0 12px 20px;
    padding-left: 15px;
}

#aiResult li {
    margin: 5px 0;
}

#aiResult strong {
    font-weight: 700;
}

#aiResult hr {
    margin: 18px 0;
    border: 0;
    border-top: 1px solid var(--border);
}
/* From Uiverse.io by adamgiebl */ 
.dots-container {
  display: flex;
  align-items: center;
  justify-content: flex-start;
  height: 100%;
  width: 100%;
  margin: -5px 0 31px 5px;
}

.dot {
  height: 10px;
  width: 10px;
  margin-right: 5px;
  border-radius: 10px;
  background-color: #b3d4fc;
  animation: pulse 1.5s infinite ease-in-out;
}

.dot:last-child {
  margin-right: 0;
}

.dot:nth-child(1) {
  animation-delay: -0.3s;
}

.dot:nth-child(2) {
  animation-delay: -0.1s;
}

.dot:nth-child(3) {
  animation-delay: 0.1s;
}

.ai-res{
    font-size:20px !important;
    text-decoration: underline;
}

@keyframes pulse {
  0% {
    transform: scale(0.8);
    background-color: #b3d4fc;
    box-shadow: 0 0 0 0 rgba(178, 212, 252, 0.7);
  }

  50% {
    transform: scale(1.2);
    background-color: #6793fb;
    box-shadow: 0 0 0 10px rgba(178, 212, 252, 0);
  }

  100% {
    transform: scale(0.8);
    background-color: #b3d4fc;
    box-shadow: 0 0 0 0 rgba(178, 212, 252, 0.7);
  }
}

body.dark .doctor-notice-card {
  background: #18231d !important;
  border-color: #27372e !important;
}
body.dark .doctor-notice-card h3 {
  color: #f2f7f3 !important;
}
body.dark .doctor-comment-box {
  background: #202e26 !important;
  border-color: #2c3f35 !important;
}
body.dark .doctor-comment-form {
  background: #192720 !important;
  border-color: #2a3d31 !important;
}
body.dark .doctor-comment-form textarea {
  background: #1f3027 !important;
  border-color: #2f493b !important;
  color: #e8f5e9 !important;
}
        `;

    document.head.appendChild(style);

    document
      .getElementById("workspaceClose")
      .addEventListener("click", closeWorkspace);
  }

  const wsIconEl = workspace.querySelector(".workspace-icon");
  if (wsIconEl) wsIconEl.style.display = "";
  const wsLabelEl = workspace.querySelector(".workspace-label");
  if (wsLabelEl) wsLabelEl.style.display = "";
  const wsTitleEl = document.getElementById("workspaceTitle");
  if (wsTitleEl) {
    wsTitleEl.textContent = title;
    wsTitleEl.style.display = "";
  }
  const wsDescEl = document.getElementById("workspaceDescription");
  if (wsDescEl) {
    wsDescEl.textContent = description;
    wsDescEl.style.display = "";
  }

  const wsIconI = workspace.querySelector(".workspace-icon i");
  if (wsIconI) wsIconI.className = icon || "";

  workspace.style.display = "flex";

  document.body.style.overflow = "hidden";

  return document.getElementById("workspaceContent");
}

function closeWorkspace() {
  const workspace = document.getElementById("ayurcaseWorkspace");

  if (workspace) {
    workspace.style.display = "none";
  }

  document.body.style.overflow = "";
}

/* =====================================================
   SIDEBAR NAVIGATION
   ===================================================== */

navItems.forEach((item) => {
  item.addEventListener("click", function (event) {
    event.preventDefault();

    const page = item.dataset.page;

    navItems.forEach((nav) => {
      nav.classList.remove("active");
    });

    item.classList.add("active");

    updateBreadcrumb(page);

    if (sidebar) {
      sidebar.classList.remove("open");
    }

    if (page === "dashboard") {
      closeWorkspace();

      showToast("Dashboard selected.");

      return;
    }

    if (page === "case") {
      closeWorkspace();

      openCaseModal();

      return;
    }

    if (page === "patients") {
      openPatientsWorkspace();

      return;
    }

    if (page === "history") {
      openHistoryWorkspace();

      return;
    }

    if (page === "learn") {
      openLearnWorkspace();

      return;
    }

    if (page === "notices") {
      openNoticesWorkspace();

      return;
    }

    if (page === "ai-reviews") {
      if (typeof showToast === "function") {
        showToast("AI Reviews is an upcoming feature in development.");
      }
      return;
    }
  });
});

/* =====================================================
   BREADCRUMB
   ===================================================== */

function updateBreadcrumb(page) {
  const breadcrumb = document.querySelector(".breadcrumb strong");

  if (!breadcrumb) return;

  const names = {
    dashboard: "Dashboard",

    patients: "Patients",

    case: "New Case",

    history: "Case History",

    prakriti: "Prakriti",

    learn: "Learn",

    notices: "Notices & Circulars",

    "ai-reviews": "AI Reviews",

    settings: "Settings",
  };

  breadcrumb.textContent = names[page] || "Dashboard";
}

function updateBreadcrumbText(text) {
  const breadcrumb = document.querySelector(".breadcrumb strong");

  if (breadcrumb) {
    breadcrumb.textContent = text;
  }
}

/* =====================================================
   PATIENTS WORKSPACE
   ===================================================== */

function getStoredCases() {
  try {
    const cases = JSON.parse(localStorage.getItem("ayurcase-cases") || "[]");
    return Array.isArray(cases) ? cases : [];
  } catch (_) {
    return [];
  }
}

function getDoctorTodayISO() {
  return new Date().toISOString().slice(0, 10);
}

function getRecordPatientName(record) {
  return String(record?.patient_name || record?.name || "").trim();
}

function getRecordDate(record) {
  return String(
    record?.case_date ||
      record?.date ||
      record?.appointment_date ||
      record?.created_at ||
      "",
  );
}

function formatClinicalDate(value, fallback = "Date not recorded") {
  if (!value) return fallback;
  const isoDate = String(value).slice(0, 10);
  const parsed = new Date(`${isoDate}T12:00:00`);
  if (!Number.isNaN(parsed.getTime())) {
    return parsed.toLocaleDateString(undefined, {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  }
  return String(value);
}

function clinicalStatusClass(status) {
  const normalized = String(status || "").toLowerCase();
  if (normalized.includes("follow") || normalized.includes("review")) {
    return "Follow-up-status";
  }
  if (normalized.includes("new")) return "New-status";
  return "Active-status";
}

async function fetchDoctorAppointmentsForWorkspace() {
  const doctorId =
    typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;
  if (!doctorId || typeof getApiHost !== "function") return [];

  const api = getApiHost();
  const response = await fetch(
    `${api}/api/appointments?doctor_id=${encodeURIComponent(doctorId)}`,
    { cache: "no-store" },
  );
  const data = await response.json();
  if (!response.ok || !data.success || !Array.isArray(data.appointments)) {
    throw new Error(data.error || "Patient appointments could not be loaded.");
  }
  return data.appointments;
}

async function loadDoctorWorkspaceRecords() {
  const fallbackCases = getStoredCases();
  const caseRequest =
    typeof fetchDoctorCaseRecords === "function"
      ? fetchDoctorCaseRecords()
      : Promise.resolve(fallbackCases);
  const dashboardRequest =
    typeof fetchDoctorDashboard === "function"
      ? fetchDoctorDashboard()
      : Promise.resolve(null);
  const [casesResult, appointmentsResult, dashboardResult] =
    await Promise.allSettled([
      caseRequest,
      fetchDoctorAppointmentsForWorkspace(),
      dashboardRequest,
    ]);

  const cases =
    casesResult.status === "fulfilled" && Array.isArray(casesResult.value)
      ? casesResult.value
      : fallbackCases;
  const appointments =
    appointmentsResult.status === "fulfilled" &&
    Array.isArray(appointmentsResult.value)
      ? appointmentsResult.value
      : [];
  const dashboard =
    dashboardResult.status === "fulfilled" ? dashboardResult.value : null;

  return { cases, appointments, dashboard };
}

function buildPatientDirectory(cases, appointments) {
  const patients = new Map();
  const getPatient = (record) => {
    const name = getRecordPatientName(record);
    if (!name) return null;
    const key = name.toLocaleLowerCase();
    if (!patients.has(key)) {
      patients.set(key, {
        name,
        age: "",
        gender: "",
        cases: [],
        upcoming: [],
        previousAppointments: [],
      });
    }
    return patients.get(key);
  };

  cases.forEach((record) => {
    const patient = getPatient(record);
    if (!patient) return;
    patient.cases.push(record);
    patient.age = record.age || patient.age;
    patient.gender = record.gender || patient.gender;
  });

  const today = getDoctorTodayISO();
  appointments.forEach((record) => {
    const patient = getPatient(record);
    if (!patient) return;
    patient.age = patient.age || record.age || record.patient_age;
    patient.gender = patient.gender || record.gender || record.patient_gender;
    const status = String(record.status || "").toLowerCase();
    const isUpcoming =
      String(record.appointment_date || "") >= today &&
      !["cancelled", "completed"].includes(status);
    if (isUpcoming) patient.upcoming.push(record);
    else patient.previousAppointments.push(record);
  });

  return [...patients.values()]
    .map((patient) => ({
      ...patient,
      cases: patient.cases.sort((a, b) =>
        getRecordDate(b).localeCompare(getRecordDate(a)),
      ),
      upcoming: patient.upcoming.sort((a, b) =>
        String(a.appointment_date || "").localeCompare(
          String(b.appointment_date || ""),
        ),
      ),
      previousAppointments: patient.previousAppointments.sort((a, b) =>
        String(b.appointment_date || "").localeCompare(
          String(a.appointment_date || ""),
        ),
      ),
    }))
    .sort((a, b) => {
      // 1. Follow-up patients strictly at the top of the list!
      const aHasFollowUp = (a.upcoming && a.upcoming.length > 0) || (a.cases[0] && String(a.cases[0].status || "").toLowerCase().includes("follow"));
      const bHasFollowUp = (b.upcoming && b.upcoming.length > 0) || (b.cases[0] && String(b.cases[0].status || "").toLowerCase().includes("follow"));
      if (aHasFollowUp && !bHasFollowUp) return -1;
      if (!aHasFollowUp && bHasFollowUp) return 1;

      // 2. If both have follow-ups, sort by soonest scheduled follow-up
      if (aHasFollowUp && bHasFollowUp) {
        const aDate = String(a.upcoming[0]?.appointment_date || a.cases[0]?.case_date || a.cases[0]?.created_at || "") + " " + String(a.upcoming[0]?.appointment_time || "");
        const bDate = String(b.upcoming[0]?.appointment_date || b.cases[0]?.case_date || b.cases[0]?.created_at || "") + " " + String(b.upcoming[0]?.appointment_time || "");
        const cmp = aDate.localeCompare(bDate);
        if (cmp !== 0) return cmp;
      }

      // 3. Otherwise sort by most recent activity date descending
      const aDate = getRecordDate(a.cases[0] || a.previousAppointments[0]);
      const bDate = getRecordDate(b.cases[0] || b.previousAppointments[0]);
      return bDate.localeCompare(aDate);
    });
}

function renderPatientDirectoryCard(patient, index) {
  const recordsExpanded = localStorage.getItem("ayurcase-expanded-cases") !== "false";
  const demographics = [
    patient.age ? `${escapeHTML(patient.age)} years` : "Age not recorded",
    patient.gender ? escapeHTML(patient.gender) : "Gender not recorded",
  ].join(" • ");
  const latestCase = patient.cases[0];
  const hasFollowUp = (patient.upcoming.length > 0) || (latestCase && String(latestCase.status || "").toLowerCase().includes("follow"));
  const latestStatus = hasFollowUp
    ? "Follow-up"
    : (latestCase?.status ||
       patient.previousAppointments[0]?.status ||
       "Patient");

  const latestConcernText = hasFollowUp
    ? (patient.upcoming[0]?.symptoms_notes || patient.upcoming[0]?.consultation_type || latestCase?.chief_complaint || latestCase?.complaint || "Follow-up consultation scheduled.")
    : (latestCase?.chief_complaint || latestCase?.complaint || patient.previousAppointments[0]?.symptoms_notes || "Clinical record updated.");

  const upcoming = patient.upcoming.length
    ? `
      <section class="patient-record-group upcoming-records">
        <h4><i class="fa-solid fa-calendar-check"></i> Follow-up consultations <span>${patient.upcoming.length}</span></h4>
        ${patient.upcoming
          .map(
            (appointment) => `
              <div class="patient-record-line">
                <strong>${escapeHTML(formatClinicalDate(appointment.appointment_date))} · ${escapeHTML(appointment.appointment_time || "Time to be confirmed")}</strong>
                <span>${escapeHTML(appointment.consultation_type || "Follow-up Consultation")} · ${escapeHTML(appointment.symptoms_notes || "No visit note recorded")}</span>
              </div>`,
          )
          .join("")}
      </section>`
    : ((latestCase && String(latestCase.status || "").toLowerCase().includes("follow"))
        ? `
      <section class="patient-record-group upcoming-records">
        <h4><i class="fa-solid fa-calendar-check"></i> Follow-up consultations <span>1</span></h4>
        <div class="patient-record-line">
          <strong>${escapeHTML(formatClinicalDate(latestCase.case_date || latestCase.created_at))} · Scheduled Follow-up</strong>
          <span>Follow-up Consultation · ${escapeHTML(latestCase.chief_complaint || latestCase.complaint || "Clinical follow-up scheduled")}</span>
        </div>
      </section>`
        : "");

  const caseHistory = patient.cases.length
    ? `
      <details class="patient-record-group" ${recordsExpanded ? "open" : ""}>
        <summary><i class="fa-solid fa-notes-medical"></i> Previous case records <span>${patient.cases.length}</span><i class="fa-solid fa-chevron-down"></i></summary>
        ${patient.cases
          .map(
            (record) => `
              <div class="patient-record-line">
                <strong>${escapeHTML(formatClinicalDate(getRecordDate(record)))} · ${escapeHTML(record.diagnosis || "Under AYUSH evaluation")}</strong>
                <span>${escapeHTML(record.chief_complaint || record.complaint || "Clinical details not recorded")} · ${escapeHTML(record.prakriti || "Prakriti not recorded")}</span>
              </div>`,
          )
          .join("")}
      </details>`
    : "";

  const previousVisits = patient.previousAppointments.length
    ? `
      <details class="patient-record-group">
        <summary><i class="fa-solid fa-clock-rotate-left"></i> Previous appointments <span>${patient.previousAppointments.length}</span><i class="fa-solid fa-chevron-down"></i></summary>
        ${patient.previousAppointments
          .map(
            (appointment) => `
              <div class="patient-record-line">
                <strong>${escapeHTML(formatClinicalDate(appointment.appointment_date))} · ${escapeHTML(appointment.appointment_time || "Time not recorded")}</strong>
                <span>${escapeHTML(appointment.consultation_type || "Consultation")} · ${escapeHTML(appointment.symptoms_notes || appointment.status || "Visit recorded")}</span>
              </div>`,
          )
          .join("")}
      </details>`
    : "";

  return `
    <article class="patient-directory-card ${hasFollowUp ? "has-followup" : ""}" data-patient-search="${escapeHTML(patient.name.toLowerCase())}">
      <div class="patient-directory-header">
        <div class="patient-avatar avatar-${(index % 4) + 1}">${escapeHTML(getInitials(patient.name))}</div>
        <div>
          <h3>${escapeHTML(patient.name)}</h3>
          <p>${demographics}</p>
        </div>
        <span class="status ${clinicalStatusClass(latestStatus)}">${escapeHTML(latestStatus)}</span>
      </div>
      <p class="patient-directory-summary"><strong>Latest concern:</strong> ${escapeHTML(latestConcernText)}</p>
      <div class="patient-records">
        ${upcoming}
        ${caseHistory}
        ${previousVisits}
      </div>
    </article>`;
}

async function openPatientsWorkspace() {
  const content = openWorkspace(
    "Patients",
    "A complete view of every patient, including upcoming consultations and previous clinical records.",
    "fa-solid fa-users",
  );

  content.innerHTML = `
    <div class="workspace-loading">
      <i class="fa-solid fa-circle-notch fa-spin"></i>
      Loading your patient directory…
    </div>`;

  try {
    const { cases, appointments } = await loadDoctorWorkspaceRecords();
    const patients = buildPatientDirectory(cases, appointments);
    const upcomingCount = patients.reduce(
      (count, patient) => count + (patient.upcoming.length || (patient.cases[0] && String(patient.cases[0].status || "").toLowerCase().includes("follow") ? 1 : 0)),
      0,
    );
    const previousCount = patients.reduce(
      (count, patient) => count + patient.cases.length + patient.previousAppointments.length,
      0,
    );

    if (!patients.length) {
      content.innerHTML = `
        <div class="workspace-empty-state">
          <i class="fa-solid fa-user-plus"></i>
          <strong>No patient records yet</strong>
          <span>New cases and consultation bookings assigned to you will appear here.</span>
          <button class="workspace-action" id="workspaceNewCase">Create New Case</button>
        </div>`;
      document.getElementById("workspaceNewCase")?.addEventListener("click", () => {
        closeWorkspace();
        openCaseModal();
      });
      return;
    }

    content.innerHTML = `
      <div class="workspace-toolbar">
        <div class="workspace-counts">
          <span><strong>${patients.length}</strong> patients</span>
          <span><strong>${upcomingCount}</strong> follow-up${upcomingCount === 1 ? "" : "s"}</span>
          <span><strong>${previousCount}</strong> previous records</span>
        </div>
        <label class="workspace-search" for="patientDirectorySearch">
          <i class="fa-solid fa-magnifying-glass"></i>
          <input id="patientDirectorySearch" type="search" placeholder="Search patients" />
        </label>
      </div>
      <div class="patient-directory-list">
        ${patients.map(renderPatientDirectoryCard).join("")}
      </div>`;

    document
      .getElementById("patientDirectorySearch")
      ?.addEventListener("input", (event) => {
        const query = event.target.value.trim().toLowerCase();
        document.querySelectorAll(".patient-directory-card").forEach((card) => {
          card.hidden = !card.dataset.patientSearch.includes(query);
        });
      });

    document.querySelectorAll(".patient-directory-card").forEach((card, index) => {
      const patient = patients[index];
      if (patient) {
        card.addEventListener("click", (event) => {
          if (event.target.closest("details summary") || event.target.closest("summary")) return;
          if (typeof window.openDoctorPatientProfile === "function") {
            window.openDoctorPatientProfile(patient.name, patient);
          }
        });
      }
    });
  } catch (error) {
    content.innerHTML = `
      <div class="workspace-empty-state error-state">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <strong>Patient directory unavailable</strong>
        <span>${escapeHTML(error.message || "Please refresh and try again.")}</span>
      </div>`;
  }
}
function renderPatientsdashboard() {
  const cases = JSON.parse(localStorage.getItem("ayurcase-cases")) || [];
  const patientList = document.getElementById("patient-list");
  if (!patientList) return;
  patientList.innerHTML = cases
    .map(
      (patient) => `<div class="patient-row">
                      <div class="patient-avatar avatar-${Math.floor(Math.random() * 4 + 1)}">
                        ${getInitials(patient.name)}
                      </div>
        
                      <div class="patient-info">
                        <strong> ${escapeHTML(patient.name)}</strong>
                        <span>${escapeHTML(patient.age)} years • ${escapeHTML(patient.gender)}</span>
                      </div>
    
                      <div class="patient-complaint">
                        <span>Primary complaint</span>
                        <strong>${escapeHTML(patient.complaint)}</strong>
                      </div>
    
                      <div class="patient-status">
                        <span class="status ${escapeHTML(patient.status)}-status">${escapeHTML(patient.status)}</span>
                      </div>
    
                      <button class="more-btn">
                        <i class="fa-solid fa-ellipsis"></i>
                      </button>
    </div>`,
    )
    .join("");

  patientList.querySelectorAll(".patient-row").forEach((row, index) => {
    const patient = cases[index];
    if (patient) {
      row.addEventListener("click", () => {
        if (typeof window.openDoctorPatientProfile === "function") {
          window.openDoctorPatientProfile(patient.name, patient);
        }
      });
    }
  });
}
function getInitials(name) {
  let initial = "";
  name.split(" ").forEach((e) => {
    initial += e[0];
  });
  return initial;
}

/* =====================================================
   CASE HISTORY
   ===================================================== */

async function openHistoryWorkspace() {
  const content = openWorkspace(
    "Case History",

    "Every clinical case recorded under your practitioner account, arranged from most recent to earliest.",

    "fa-solid fa-clock-rotate-left",
  );

  content.innerHTML = `

    <div class="workspace-loading">
      <i class="fa-solid fa-circle-notch fa-spin"></i>
      Loading complete case history…
    </div>`;

  const doctorId =
    typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;

  // Do not fall back to browser storage or an unfiltered request here: either
  // can expose stale sample cases from another practitioner.
  if (!doctorId) {
    content.innerHTML = `
      <div class="workspace-empty-state">
        <i class="fa-solid fa-lock"></i>
        <strong>No case history available</strong>
        <span>Sign in to a practitioner account to view its case history.</span>
      </div>`;
    return;
  }

  let cases = [];
  try {
    const api = typeof getApiHost === "function" ? getApiHost() : "";
    const response = await fetch(
      `${api}/api/cases?doctor_id=${encodeURIComponent(doctorId)}`,
    );
    const data = await response.json();
    if (!response.ok || !data.success || !Array.isArray(data.cases)) {
      throw new Error(data.error || "Case history could not be loaded.");
    }
    cases = data.cases;
  } catch (error) {
    content.innerHTML = `
      <div class="workspace-empty-state error-state">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <strong>Case history unavailable</strong>
        <span>${escapeHTML(error.message || "Please refresh and try again.")}</span>
      </div>`;
    return;
  }

  if (cases.length === 0) {
    content.innerHTML = `
      <div class="workspace-empty-state">
        <i class="fa-solid fa-folder-open"></i>
        <strong>No case history available</strong>
        <span>Cases you create for your own patients will appear here.</span>
      </div>`;

    return;
  }

  const displayCases = cases.slice(0, 2);

  content.innerHTML = `
    <div class="workspace-toolbar">
      <div class="workspace-counts">
        <span><strong>${displayCases.length}</strong> recorded patient case${displayCases.length === 1 ? "" : "s"}</span>
        <span>All dates · all statuses</span>
      </div>
      <label class="workspace-search" for="caseHistorySearch">
        <i class="fa-solid fa-magnifying-glass"></i>
        <input id="caseHistorySearch" type="search" placeholder="Search name, diagnosis or concern" />
      </label>
    </div>
    <div class="case-history-list">
      ${displayCases
        .map(
          (patient, index) => `
            <article class="case-history-card" data-case-search="${escapeHTML(
              [
                patient.name,
                patient.patient_name,
                patient.diagnosis,
                patient.complaint,
                patient.chief_complaint,
              ]
                .filter(Boolean)
                .join(" ")
                .toLowerCase(),
            )}">
              <div class="case-history-card-header">
                <div class="patient-avatar avatar-${(index % 4) + 1}">${escapeHTML(getInitials(getRecordPatientName(patient)))}</div>
                <div>
                  <h3>${escapeHTML(getRecordPatientName(patient))}</h3>
                  <p>${escapeHTML(patient.age || "Age not recorded")} years · ${escapeHTML(patient.gender || "Gender not recorded")} · Recorded ${escapeHTML(formatClinicalDate(getRecordDate(patient), "date not recorded"))}</p>
                </div>
                <span class="status ${clinicalStatusClass(patient.status)}">${escapeHTML(patient.status || "Active")}</span>
              </div>
              <div class="case-history-detail-grid">
                <div><span>Chief concern</span><strong>${escapeHTML(patient.chief_complaint || patient.complaint || "Not recorded")}</strong></div>
                <div><span>Clinical assessment</span><strong>${escapeHTML(patient.diagnosis || "Under AYUSH evaluation")}</strong></div>
                <div><span>Prakriti</span><strong>${escapeHTML(patient.prakriti || "Not recorded")}</strong></div>
                <div><span>Case reference</span><strong>#${escapeHTML(patient.id || "—")}</strong></div>
              </div>
            </article>`,
        )
        .join("")}
    </div>`;

  document
    .getElementById("caseHistorySearch")
    ?.addEventListener("input", (event) => {
      const query = event.target.value.trim().toLowerCase();
      document.querySelectorAll(".case-history-card").forEach((card) => {
        card.hidden = !card.dataset.caseSearch.includes(query);
      });
    });

  document.querySelectorAll(".case-history-card").forEach((card, index) => {
    const record = cases[index];
    if (record) {
      card.addEventListener("click", () => {
        const patientName = getRecordPatientName(record);
        if (typeof window.openDoctorPatientProfile === "function") {
          window.openDoctorPatientProfile(patientName, record);
        }
      });
    }
  });
}

/* =====================================================
   PRAKRITI WORKSPACE
   ===================================================== */

function openPrakritiWorkspace() {
  const content = openWorkspace(
    "Prakriti Assessment",

    "Perform a basic constitutional assessment for the patient.",

    "fa-solid fa-spa",
  );

  const questions = [
    "How is the patient's body structure?",

    "How is the patient's appetite?",

    "How is the patient's sleep pattern?",

    "How is the patient's energy level?",
  ];

  content.innerHTML = `

        <div class="workspace-box">

            <strong>
                Prakriti Questionnaire
            </strong>

            <span>
                Select the response that best describes the patient.
            </span>

        </div>


        ${questions
          .map(
            (question, index) => `

                <div class="workspace-box">

                    <strong>
                        ${index + 1}.
                        ${question}
                    </strong>

                    <select
                        class="prakriti-select"
                        style="
                            margin-top:10px;
                            width:100%;
                            padding:9px;
                            border:1px solid var(--border);
                            border-radius:9px;
                        "
                    >

                        <option value="">
                            Select response
                        </option>

                        <option>
                            Vata tendency
                        </option>

                        <option>
                            Pitta tendency
                        </option>

                        <option>
                            Kapha tendency
                        </option>

                    </select>

                </div>

            `,
          )
          .join("")}


        <button
            class="workspace-action"
            id="calculatePrakriti"
        >
            Calculate Assessment
        </button>

    `;

  document
    .getElementById("calculatePrakriti")
    .addEventListener("click", calculatePrakriti);
}

function calculatePrakriti() {
  const selections = document.querySelectorAll(".prakriti-select");

  let vata = 0;
  let pitta = 0;
  let kapha = 0;

  selections.forEach((select) => {
    if (select.value.includes("Vata")) {
      vata++;
    }

    if (select.value.includes("Pitta")) {
      pitta++;
    }

    if (select.value.includes("Kapha")) {
      kapha++;
    }
  });

  if (vata + pitta + kapha === selections.length) {
    const scores = {
      Vata: vata,

      Pitta: pitta,

      Kapha: kapha,
    };

    const result = Object.keys(scores).sort((a, b) => scores[b] - scores[a])[0];

    showToast(`Assessment result: ${result} dominant`);
  } else {
    showToast("Please answer all assessment questions.");
  }
}

/* =====================================================
   AI ASSISTANT
   ===================================================== */

let doctorAssistantTrigger = null;
let doctorAssistantSpeechButton = null;

function openDoctorAssistant() {
  const modal = document.getElementById("doctorAssistantModal");
  if (!modal) return;

  doctorAssistantTrigger = document.activeElement;
  modal.style.display = "flex";
  document.body.style.overflow = "hidden";
  requestAnimationFrame(() =>
    document.getElementById("doctorAssistantInput")?.focus(),
  );
}

function closeDoctorAssistant() {
  const modal = document.getElementById("doctorAssistantModal");
  if (!modal) return;

  modal.style.display = "none";
  document.body.style.overflow = "";
  window.speechSynthesis?.cancel();
  resetDoctorAssistantSpeechButton();
  doctorAssistantTrigger?.focus?.();
}

function resetDoctorAssistantSpeechButton(button = doctorAssistantSpeechButton) {
  if (!button) return;

  if (doctorAssistantSpeechButton === button) {
    doctorAssistantSpeechButton = null;
  }
  button.classList.remove("is-speaking");
  button.setAttribute("aria-label", "Read this reply aloud");
  button.title = "Read aloud";
}

function appendDoctorAssistantMessage(content, role) {
  const chat = document.getElementById("doctorAssistantChat");
  if (!chat) return null;

  const message = document.createElement("div");
  message.className = `doctor-ai-message ${role}`;
  const messageText = document.createElement("span");
  messageText.className = "doctor-ai-message-text";
  if (role === "assistant") {
    messageText.innerHTML = typeof window.formatAiAssistantResponse === "function"
      ? window.formatAiAssistantResponse(content)
      : content;
  } else {
    messageText.textContent = content;
  }
  message.appendChild(messageText);

  if (role === "assistant") {
    const speakButton = document.createElement("button");
    speakButton.type = "button";
    speakButton.className = "doctor-ai-speak";
    speakButton.setAttribute("aria-label", "Read this reply aloud");
    speakButton.title = "Read aloud";
    speakButton.innerHTML = '<i class="fa-solid fa-volume-high" aria-hidden="true"></i>';
    speakButton.disabled = content === "Thinking…" || content.includes("Thinking");
    speakButton.addEventListener("click", () => speakDoctorAssistantMessage(speakButton));
    message.appendChild(speakButton);
  }

  chat.appendChild(message);
  chat.scrollTop = chat.scrollHeight;
  return message;
}

function updateDoctorAssistantMessage(message, content) {
  if (!message) return;

  const messageText = message.querySelector(".doctor-ai-message-text");
  if (messageText) {
    messageText.innerHTML = typeof window.formatAiAssistantResponse === "function"
      ? window.formatAiAssistantResponse(content)
      : content;
  }

  const speakButton = message.querySelector(".doctor-ai-speak");
  if (speakButton) {
    speakButton.disabled = content === "Thinking…" || content.includes("Thinking");
    speakButton.setAttribute("aria-label", "Read this reply aloud");
    speakButton.title = "Read aloud";
  }
}

function speakDoctorAssistantMessage(button) {
  const message = button?.closest(".doctor-ai-message.assistant");
  const text = message?.querySelector(".doctor-ai-message-text")?.textContent.trim();
  if (!button || !text || !("speechSynthesis" in window) || !("SpeechSynthesisUtterance" in window)) {
    showToast("Read-aloud is not supported in this browser.");
    return;
  }

  if (window.speechSynthesis.speaking && doctorAssistantSpeechButton === button) {
    window.speechSynthesis.cancel();
    resetDoctorAssistantSpeechButton(button);
    return;
  }

  window.speechSynthesis.cancel();
  resetDoctorAssistantSpeechButton();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = 1;
  utterance.onstart = () => {
    doctorAssistantSpeechButton = button;
    button.classList.add("is-speaking");
    button.setAttribute("aria-label", "Stop reading this reply");
    button.title = "Stop reading";
  };
  const resetSpeechButton = () => {
    if (doctorAssistantSpeechButton !== button) return;
    resetDoctorAssistantSpeechButton(button);
  };
  utterance.onend = resetSpeechButton;
  utterance.onerror = resetSpeechButton;
  window.speechSynthesis.speak(utterance);
}

function askDoctorAssistantQuestion(question) {
  const input = document.getElementById("doctorAssistantInput");
  if (!input) return;

  input.value = question;
  sendDoctorAssistantQuestion();
}

async function sendDoctorAssistantQuestion(event) {
  event?.preventDefault();

  const input = document.getElementById("doctorAssistantInput");
  const sendButton = document.getElementById("doctorAssistantSend");
  const question = input?.value.trim();
  if (!question || !sendButton) return;

  appendDoctorAssistantMessage(question, "user");
  input.value = "";
  sendButton.disabled = true;
  const originalContent = sendButton.innerHTML;
  sendButton.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i>';
  const responseMessage = appendDoctorAssistantMessage("Thinking…", "assistant");

  try {
    const response = await fetch(
      `${typeof getApiHost === "function" ? getApiHost() : ""}/api/recommend`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ problem: question, mode: "patient-assistant" }),
      },
    );
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || "The AI service could not answer right now.");
    }
    updateDoctorAssistantMessage(
      responseMessage,
      data.recommendation || "I couldn’t generate a response. Please try again.",
    );
  } catch (error) {
    updateDoctorAssistantMessage(
      responseMessage,
      typeof getAssistantFallbackResponse === "function"
        ? getAssistantFallbackResponse(question)
        : "I received your question, but the live AI service is temporarily unavailable. Please try again shortly.",
    );
  } finally {
    sendButton.disabled = false;
    sendButton.innerHTML = originalContent;
    document.getElementById("doctorAssistantChat")?.scrollTo({
      top: document.getElementById("doctorAssistantChat").scrollHeight,
      behavior: "smooth",
    });
    input?.focus();
  }
}

const doctorAssistantModalEl = document.getElementById("doctorAssistantModal");
if (doctorAssistantModalEl) {
  doctorAssistantModalEl.addEventListener("click", function (event) {
    if (event.target === this) closeDoctorAssistant();
  });
}

/* =====================================================
   LEARN LIBRARY
   ===================================================== */

function openLearnWorkspace() {
  const content = openWorkspace("", "", "");

  // Clean up any old wishlist or completed buttons if present
  document.getElementById("learnWishlistView")?.remove();
  document.getElementById("learnCompletedView")?.remove();

  // Hide all workspace chrome elements (icon, label, title, description) so ONLY the Add Article button is visible
  const workspaceEl = document.getElementById("ayurcaseWorkspace");
  if (workspaceEl) {
    const wsIcon = workspaceEl.querySelector(".workspace-icon");
    if (wsIcon) wsIcon.style.display = "none";
    const wsLabel = workspaceEl.querySelector(".workspace-label");
    if (wsLabel) wsLabel.style.display = "none";
    const wsTitle = document.getElementById("workspaceTitle");
    if (wsTitle) wsTitle.style.display = "none";
    const wsDesc = document.getElementById("workspaceDescription");
    if (wsDesc) wsDesc.style.display = "none";
  }

  content.innerHTML = `
    <div class="learn-only-container" style="display: flex; align-items: center; justify-content: center; min-height: 280px; width: 100%; padding: 40px 20px;">
      <button type="button" class="primary-btn" id="learnOnlyAddArticleBtn" onclick="if (typeof closeWorkspace === 'function') closeWorkspace(); if (typeof window.openDoctorAddArticleModal === 'function') { window.openDoctorAddArticleModal(); } else if (typeof openDoctorAddArticleModal === 'function') { openDoctorAddArticleModal(); }" style="background: linear-gradient(135deg, #0d9488, #059669); color: #ffffff; border: none; padding: 20px 48px; border-radius: 16px; font-weight: 700; font-size: 18px; cursor: pointer; display: inline-flex; align-items: center; gap: 12px; box-shadow: 0 10px 30px rgba(13, 148, 136, 0.35); transition: transform 0.15s ease, box-shadow 0.15s ease;">
        <i class="fa-solid fa-plus" style="font-size: 20px;"></i>
        <span>Add Article</span>
      </button>
    </div>
  `;
}

/* =====================================================
   QUICK ACTIONS
   ===================================================== */

const quickCards = document.querySelectorAll(".quick-card");

quickCards.forEach((card) => {
  card.addEventListener("click", function () {
    if (card.classList.contains("case-action")) {
      openCaseModal();

      return;
    }

    const title = card.querySelector("strong")?.textContent.trim() || "";

    if (title === "Add Patient") {
      openCaseModal();

      return;
    }

    showToast(`${title} workspace opened.`);
  });
});

/* =====================================================
   NOTIFICATION SYSTEM
   ===================================================== */

/*
   FIXED:
   Notification button now opens a real
   notification workspace instead of only
   displaying a toast.
*/

const notificationButton = document.querySelector(".notification-btn");

function openNotificationWorkspace() {
  const content = openWorkspace(
    "Notifications",

    "Stay updated with important AYURCASE activities.",

    "fa-solid fa-bell",
  );

  content.innerHTML = `

        <div class="notification-item">

            <div class="notification-dot"></div>

            <div class="notification-content">

                <strong>
                    New patient case activity
                </strong>

                <span>
                    Patient case management is ready for your next consultation.
                </span>

                <span class="notification-time">
                    Just now
                </span>

            </div>

        </div>


        <div class="notification-item">

            <div class="notification-dot"></div>

            <div class="notification-content">

                <strong>
                    AI Assistant available
                </strong>

                <span>
                    Clinical documentation and structured case analysis are available.
                </span>

                <span class="notification-time">
                    Today
                </span>

            </div>

        </div>


        <div class="notification-item">

            <div class="notification-dot"></div>

            <div class="notification-content">

                <strong>
                    Prakriti assessment reminder
                </strong>

                <span>
                    Complete the Prakriti assessment when creating a new patient case.
                </span>

                <span class="notification-time">
                    Today
                </span>

            </div>

        </div>


        <button
            class="workspace-action"
            id="clearNotifications"
        >

            <i class="fa-solid fa-check"></i>

            Mark All as Read

        </button>

    `;

  const clearButton = document.getElementById("clearNotifications");

  if (clearButton) {
    clearButton.addEventListener("click", function () {
      content.innerHTML = `

                    <div class="workspace-box">

                        <strong>
                            All notifications are cleared.
                        </strong>

                        <span>
                            You're all caught up. New notifications will appear here.
                        </span>

                    </div>

                `;

      showToast("All notifications marked as read.");
    });
  }
}

/*
   Attach notification event
*/

if (notificationButton) {
  notificationButton.addEventListener("click", function (event) {
    event.preventDefault();

    event.stopPropagation();

    openNotificationWorkspace();
  });
}

/* =====================================================
   HELP / NEED HELP SYSTEM
   ===================================================== */

/*
   FIXED:
   Supports:
   .help-card
   .help-btn
   .need-help
   .help-button

   Also searches for an element containing
   the text "Need Help".
*/

let helpElements = document.querySelectorAll(
  ".help-card, .help-btn, .need-help, .help-button",
);

/*
   If the original HTML doesn't have one of the
   expected classes, find the element by text.
*/

if (helpElements.length === 0) {
  const allElements = document.querySelectorAll("a, button, div, span");

  const detectedHelpElements = [];

  allElements.forEach((element) => {
    const text = element.textContent?.trim().toLowerCase();

    if (text === "need help" || text === "help" || text.includes("need help")) {
      detectedHelpElements.push(element);
    }
  });

  helpElements = detectedHelpElements;
}

/* Remove duplicate elements */

const uniqueHelpElements = [...new Set(helpElements)];

function openHelpWorkspace() {
  const content = openWorkspace(
    "Help & Support",

    "Get assistance with AYURCASE and learn how to use the platform.",

    "fa-solid fa-circle-question",
  );

  content.innerHTML = `

        <div class="workspace-box help-option">

            <div class="help-option-icon">

                <i class="fa-solid fa-book-open"></i>

            </div>


            <div class="help-option-content">

                <strong>
                    Getting Started
                </strong>

                <span>
                    Create a patient case, record clinical information,
                    review case history and use the AI Assistant
                    for structured documentation.
                </span>

            </div>

        </div>


        <div class="workspace-box help-option">

            <div class="help-option-icon">

                <i class="fa-solid fa-user-plus"></i>

            </div>


            <div class="help-option-content">

                <strong>
                    Creating a Patient Case
                </strong>

                <span>
                    Click "New Case" or "Add Patient", enter the
                    patient's basic details and submit the case.
                </span>

            </div>

        </div>


        <div class="workspace-box help-option">

            <div class="help-option-icon">

                <i class="fa-solid fa-wand-magic-sparkles"></i>

            </div>


            <div class="help-option-content">

                <strong>
                    Using AI Assistant
                </strong>

                <span>
                    Enter patient observations, symptoms and history.
                    The AI workspace will organize the information
                    into a preliminary structured summary.
                </span>

            </div>

        </div>


        <div class="workspace-box help-option">

            <div class="help-option-icon">

                <i class="fa-solid fa-spa"></i>

            </div>


            <div class="help-option-content">

                <strong>
                    Prakriti Assessment
                </strong>

                <span>
                    Select the appropriate responses for each question
                    and calculate the preliminary Prakriti assessment.
                </span>

            </div>

        </div>


        <div class="workspace-box help-option">

            <div class="help-option-icon">

                <i class="fa-solid fa-headset"></i>

            </div>


            <div class="help-option-content">

                <strong>
                    Need Further Assistance?
                </strong>

                <span>
                    If you encounter a problem while using AYURCASE,
                    contact your platform administrator or support team.
                </span>

                <button
                    class="workspace-action"
                    id="contactSupport"
                >

                    <i class="fa-solid fa-envelope"></i>

                    Contact Support

                </button>

            </div>

        </div>

    `;

  const contactSupport = document.getElementById("contactSupport");

  if (contactSupport) {
    contactSupport.addEventListener("click", function () {
      showToast("Support request option selected.");
    });
  }
}

/* Attach Help events */

uniqueHelpElements.forEach((element) => {
  element.addEventListener("click", function (event) {
    event.preventDefault();

    event.stopPropagation();

    openHelpWorkspace();
  });
});

/* =====================================================
   VIEW ALL PATIENTS
   ===================================================== */

/* =====================================================
   PATIENT ROWS
   ===================================================== */

const patientRows = document.querySelectorAll(".patient-row");

patientRows.forEach((row) => {
  row.addEventListener("dblclick", function () {
    const patient = row.querySelector(".patient-info strong")?.textContent;

    if (patient) {
      showToast(`Opening ${patient}'s case.`);
    }
  });
});

/* =====================================================
   MORE BUTTONS
   ===================================================== */

function moreButton() {
  const moreButtons = document.querySelectorAll(".more-btn");

  moreButtons.forEach((button) => {
    button.addEventListener("click", function (event) {
      event.stopPropagation();

      const row = button.closest(".patient-row");

      const patient =
        row?.querySelector(".patient-info strong")?.textContent || "Patient";

      showPatientMenu(patient, button);
    });
  });

  function showPatientMenu(patient, button) {
    const existing = document.getElementById("patientActionMenu");

    if (existing) {
      existing.remove();
    }

    const menu = document.createElement("div");

    menu.id = "patientActionMenu";

    menu.innerHTML = `
    
            <div>
    
                <strong>
                    ${escapeHTML(patient)}
                </strong>
    
            </div>
    
    
            <button data-action="view">
    
                <i class="fa-solid fa-eye"></i>
    
                View Case
    
            </button>
    
    
            <button data-action="history">
    
                <i class="fa-solid fa-clock-rotate-left"></i>
    
                Case History
    
            </button>
    
    
            <button data-action="close">
    
                <i class="fa-solid fa-xmark"></i>
    
                Close
    
            </button>
    
            <button data-action="delete" style="color: red !important">
    
                <i class="fa-solid fa-trash-can"></i>
    
                Delete
    
            </button>
    
        `;

    menu.style.cssText = `
    
            position:absolute;
    
            background:white;
    
            border:1px solid #e5e9e5;
    
            border-radius:12px;
    
            padding:7px;
    
            width:170px;
    
            box-shadow:
                0 15px 35px rgba(0,0,0,.15);
    
            z-index:49;
    
        `;

    document.body.appendChild(menu);

    const rect = button.getBoundingClientRect();
    console.log(rect);

    menu.style.top = `${window.scrollY + rect.bottom + 6}px`;

    menu.style.left = `${Math.max(10, rect.left - 140)}px`;

    menu.querySelectorAll("button").forEach((actionButton) => {
      actionButton.style.cssText += `
    
                    width:100%;
    
                    text-align:left;
    
                    padding:9px;
    
                    background:none;
    
                    border-radius:7px;
    
                    font-size:9px;
    
                    color:#45534b;
    
                    border:none;
    
                    cursor:pointer;
    
                `;

      actionButton.addEventListener("click", function () {
        const action = this.dataset.action;

        console.log(patient);
        if (action === "view") {
          showToast(`Opening ${patient}'s case.`);
        }

        if (action === "history") {
          openHistoryWorkspace();
        }

        if (action === "delete") {
          let patients = JSON.parse(localStorage.getItem("ayurcase-cases"));
          const updatedPatients = patients.filter((p) => p.name !== patient.trim());
          console.log(updatedPatients);
          localStorage.setItem(
            "ayurcase-cases",
            JSON.stringify(updatedPatients),
          );
          renderPatientsdashboard();
          showToast(`Deleted ${patient}'s case.`);
          moreButton();
        }

        menu.remove();
      });
    });

    setTimeout(() => {
      document.addEventListener("click", function closeMenu(event) {
        if (!menu.contains(event.target) && event.target !== button) {
          menu.remove();

          document.removeEventListener("click", closeMenu);
        }
      });
    }, 10);
  }
}

moreButton();

/* =====================================================
   CALENDAR
   ===================================================== */

const calendarButton = document.querySelector(".calendar-btn");

if (calendarButton) {
  calendarButton.addEventListener("click", function () {
    openCalendarWorkspace();
  });
}

async function openCalendarWorkspace() {
  const content = openWorkspace(
    "Upcoming Schedule",
    "Review your upcoming patient follow-ups.",
    "fa-regular fa-calendar",
  );

  let appointments = latestDoctorDashboard?.follow_ups || [];
  if (!appointments.length && typeof window.extractAllDoctorFollowUps === "function") {
    try {
      const { cases, appointments: rawAppts } = await loadDoctorWorkspaceRecords();
      appointments = window.extractAllDoctorFollowUps(rawAppts, cases);
    } catch (_) {}
  }

  if (!appointments.length) {
    content.innerHTML = `
      <div class="workspace-empty-state">
        <i class="fa-regular fa-calendar-xmark"></i>
        <strong>No upcoming follow-ups scheduled</strong>
        <span>Confirmed patient follow-up visits will appear here.</span>
      </div>`;
    return;
  }

  content.innerHTML = appointments
    .map(
      (item) => `
        <div class="workspace-box">
          <strong>
            ${escapeHTML(formatClinicalDate(item.appointment_date))} — ${escapeHTML(item.patient_name)}
          </strong>
          <span>
            ${escapeHTML(item.symptoms_notes || item.consultation_type || "Follow-up consultation")}
          </span>
          <span>
            Scheduled: ${escapeHTML(item.appointment_time || "Time to be confirmed")}
          </span>
        </div>`,
    )
    .join("");
}

/* =====================================================
   SETTINGS
   ===================================================== */

const sidebarLinks = document.querySelectorAll(".sidebar .nav-item");

sidebarLinks.forEach((link) => {
  const text = link.querySelector("span")?.textContent.trim();


  if (text === "Settings") {
    link.addEventListener("click", function (event) {
      event.preventDefault();

      sidebarLinks.forEach((nav) => nav.classList.remove("active"));

      link.classList.add("active");

      updateBreadcrumbText("Settings");

      openSettingsWorkspace();
    });
  }
});

/* =====================================================
   ANALYTICS WORKSPACE
   ===================================================== */

function openAnalyticsWorkspace() {
  const content = openWorkspace(
    "Analytics",

    "Overview of your clinical documentation activity.",

    "fa-solid fa-chart-line",
  );

  const cases = JSON.parse(localStorage.getItem("ayurcase-cases")) || [];

  content.innerHTML = `

        <div class="workspace-box">

            <strong>
                Total Cases Created
            </strong>

            <span style="font-size:24px;">
                ${cases.length}
            </span>

        </div>


        <div class="workspace-box">

            <strong>
                Today's Activity
            </strong>

            <span>
                Patient case management system operational.
            </span>

        </div>


        <div class="workspace-box">

            <strong>
                AI Documentation
            </strong>

            <span>
                AI-assisted clinical documentation is available.
            </span>

        </div>

    `;
}

/* =====================================================
   SETTINGS WORKSPACE
   ===================================================== */

function openSettingsWorkspace() {
  const content = openWorkspace(
    "Settings",

    "Manage the appearance, case defaults and communication preferences for your workspace.",

    "fa-solid fa-gear",
  );

  content.innerHTML = `
    <section class="settings-section">
      <div class="settings-section-heading">
        <div><i class="fa-solid fa-palette"></i></div>
        <div><h3>Appearance</h3><p>Choose how your AYURCASE workspace looks.</p></div>
      </div>
      <div class="settings-row">
        <div><strong>Colour theme</strong><span>Switch between light and dark mode.</span></div>
        <button class="workspace-action" id="settingsTheme">${darkMode ? "Use Light Mode" : "Use Dark Mode"}</button>
      </div>
      <div class="settings-row">
        <div><strong>Comfortable case view</strong><span>Keep case records expanded when you open a patient.</span></div>
        <label class="settings-switch"><input id="settingsExpandedCases" type="checkbox" ${localStorage.getItem("ayurcase-expanded-cases") !== "false" ? "checked" : ""} /><span></span></label>
      </div>
    </section>

    <section class="settings-section">
      <div class="settings-section-heading">
        <div><i class="fa-solid fa-bell"></i></div>
        <div><h3>Notifications</h3><p>Choose which clinic updates appear in your workspace.</p></div>
      </div>
      <div class="settings-row">
        <div><strong>Upcoming consultation reminders</strong><span>Show a dashboard reminder for confirmed follow-up visits.</span></div>
        <label class="settings-switch"><input id="settingsReminders" type="checkbox" ${localStorage.getItem("ayurcase-consultation-reminders") !== "false" ? "checked" : ""} /><span></span></label>
      </div>
      <div class="settings-row">
        <div><strong>Weekly activity summary</strong><span>Keep a weekly summary preference for your clinical activity.</span></div>
        <label class="settings-switch"><input id="settingsWeeklySummary" type="checkbox" ${localStorage.getItem("ayurcase-weekly-summary") === "true" ? "checked" : ""} /><span></span></label>
      </div>
    </section>

    <section class="settings-section">
      <div class="settings-section-heading">
        <div><i class="fa-solid fa-file-medical"></i></div>
        <div><h3>Case defaults</h3><p>Set the initial status used for each newly created patient case.</p></div>
      </div>
      <div class="settings-row settings-select-row">
        <div><strong>New case status</strong><span>This can still be updated while documenting the case.</span></div>
        <select id="settingsDefaultCaseStatus" aria-label="Default new case status">
          <option value="New">New</option>
          <option value="Active">Active</option>
          <option value="Follow-up">Follow-up</option>
        </select>
      </div>
    </section>

    <section class="settings-section settings-account-section">
      <div class="settings-section-heading">
        <div><i class="fa-solid fa-user-doctor"></i></div>
        <div><h3>Practitioner account</h3><p>${escapeHTML(typeof getActiveDoctorName === "function" ? getActiveDoctorName() : "AYURCASE practitioner")}</p></div>
      </div>
      <div class="settings-row">
        <div><strong>Profile and registration details</strong><span>Review your practitioner credentials and availability.</span></div>
        <button class="workspace-action" id="settingsViewProfile">View Profile</button>
      </div>
    </section>`;

  const defaultStatus = localStorage.getItem("ayurcase-default-case-status") || "New";
  const statusSelect = document.getElementById("settingsDefaultCaseStatus");
  if (statusSelect) {
    statusSelect.value = ["New", "Active", "Follow-up"].includes(defaultStatus)
      ? defaultStatus
      : "New";
    statusSelect.addEventListener("change", () => {
      localStorage.setItem("ayurcase-default-case-status", statusSelect.value);
      showToast(`New cases will be marked ${statusSelect.value}.`);
    });
  }

  const bindToggle = (id, storageKey, message) => {
    document.getElementById(id)?.addEventListener("change", (event) => {
      localStorage.setItem(storageKey, String(event.target.checked));
      showToast(message(event.target.checked));
    });
  };
  bindToggle("settingsExpandedCases", "ayurcase-expanded-cases", (enabled) =>
    enabled ? "Patient case records will open expanded." : "Patient case records will open collapsed.",
  );
  bindToggle("settingsReminders", "ayurcase-consultation-reminders", (enabled) =>
    enabled ? "Consultation reminders enabled." : "Consultation reminders paused.",
  );
  bindToggle("settingsWeeklySummary", "ayurcase-weekly-summary", (enabled) =>
    enabled ? "Weekly activity summary enabled." : "Weekly activity summary paused.",
  );

  document.getElementById("settingsTheme")?.addEventListener("click", () => {
    themeButton?.click();
    openSettingsWorkspace();
  });
  document.getElementById("settingsViewProfile")?.addEventListener("click", () => {
    openProfileWorkspace();
  });
}

/* =====================================================
   DOCTOR PROFILE
   ===================================================== */

const topDoctor = document.querySelector("[data-workspace-profile]");

if (topDoctor) {
  topDoctor.addEventListener("click", function () {
    openProfileWorkspace();
  });
}

function openProfileWorkspace() {
  const content = openWorkspace(
    "Practitioner Profile",

    "Your AYURCASE practitioner account.",

    "fa-solid fa-user-doctor",
  );

  const doctor = latestDoctorDashboard?.doctor || {};
  const stats = latestDoctorDashboard?.stats || {};
  const fullName = doctor.full_name ||
    (typeof getActiveDoctorName === "function" ? getActiveDoctorName() : "AYURCASE Practitioner");
  content.innerHTML = `
    <section class="profile-workspace-card">
      <div class="profile-workspace-hero">
        <div class="patient-avatar avatar-1">${escapeHTML(getInitials(fullName))}</div>
        <div><h3>${escapeHTML(fullName)}</h3><p>${escapeHTML(doctor.specialization || "AYUSH Practitioner")}</p></div>
        <span class="status Active-status">${escapeHTML(doctor.status || "Active")}</span>
      </div>
      <div class="profile-workspace-grid">
        <div><span>Qualification</span><strong>${escapeHTML(doctor.qualification || "Not recorded")}</strong></div>
        <div><span>Registration no.</span><strong>${escapeHTML(doctor.council_reg_no || doctor.identifier || "Not recorded")}</strong></div>
        <div><span>Contact</span><strong>${escapeHTML(doctor.phone || "Not recorded")}</strong></div>
        <div><span>Email</span><strong>${escapeHTML(doctor.username || "Not recorded")}</strong></div>
        <div><span>Patients in care</span><strong>${escapeHTML(stats.total_patients ?? 0)}</strong></div>
        <div><span>Case records</span><strong>${escapeHTML(doctor.cases_count ?? stats.ai_cases_analyzed ?? 0)}</strong></div>
      </div>
    </section>`;
}

/* =====================================================
   ESCAPE HTML
   ===================================================== */

function escapeHTML(value) {
  return String(value)
    .replace(/&/g, "&amp;")

    .replace(/</g, "&lt;")

    .replace(/>/g, "&gt;")

    .replace(/"/g, "&quot;")

    .replace(/'/g, "&#039;");
}

/* =====================================================
   SYSTEM STATUS
   ===================================================== */

console.log(
  "%c AYURCASE ",
  "background:#173b2b;color:white;padding:8px;border-radius:5px;font-weight:bold;",
);

console.log("Digital AYUSH Patient Case-Taking Platform");

console.log("System Status: ONLINE");

/* =====================================================
   PRAKRITI HELP BUTTONS
   ===================================================== */

document.querySelectorAll(".prakriti-help-btn").forEach((button) => {
  button.addEventListener("click", function () {
    const explanation = this.dataset.help;

    openWorkspace(
      "Prakriti Help",
      "Simple explanation of the Ayurvedic term.",
      "fa-solid fa-circle-question",
    );

    const helpContent = document.getElementById("workspaceContent");

    helpContent.innerHTML = `

                    <div class="workspace-box">

                        <strong>
                            What does this term mean?
                        </strong>

                        <span style="
                            font-size:13px;
                            line-height:1.7;
                            margin-top:10px;
                        ">
                            ${escapeHTML(explanation)}
                        </span>

                    </div>

                `;
  });
});

/* =====================================================
   DOCTOR NOTICES & CLINICAL ORDERS WORKSPACE
   ===================================================== */

/**
 * Safely parse a fetch Response as JSON.
 * If the server returns an HTML error page instead of JSON
 * (e.g. a 404 or 500 with <!doctype …>) this throws a
 * descriptive error instead of the cryptic
 * "Unexpected token '<' … is not valid JSON".
 */
async function safeResJson(res) {
  const ct = res.headers.get("content-type") || "";
  if (!ct.includes("application/json")) {
    const text = await res.text().catch(() => "");
    throw new Error(
      `Server returned HTTP ${res.status} with non-JSON response` +
      (text ? `: ${text.slice(0, 120)}` : ".")
    );
  }
  return res.json();
}

function formatDoctorNoticeTime(val) {
  if (!val) return "Recent";
  const dt = new Date(String(val).replace(" ", "T"));
  if (isNaN(dt.getTime())) return String(val);
  return dt.toLocaleDateString(undefined, {
    day: "numeric", month: "short", year: "numeric",
    hour: "2-digit", minute: "2-digit"
  });
}

function renderDoctorNoticeCard(notice, currentDocName) {
  const comments = Array.isArray(notice.comments) ? notice.comments : [];

  const commentsHtml = comments.length
    ? comments.map(c => `
        <div class="doctor-comment-box" style="border: 1px solid var(--border); border-radius: 8px; padding: 8px 12px; margin-bottom: 8px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 3px;">
            <strong class="doctor-comment-author" style="font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
              <i class="fa-solid fa-user-doctor" style="color: var(--green-700);"></i>
              ${escapeHTML(c.author_name)}
            </strong>
            <span class="doctor-comment-time" style="font-size: 11px; color: var(--muted);">${escapeHTML(formatDoctorNoticeTime(c.created_at))}</span>
          </div>
          <p class="doctor-comment-text" style="margin: 0; font-size: 12.5px; line-height: 1.5;">${escapeHTML(c.comment_text)}</p>
        </div>
      `).join("")
    : `<p class="doctor-notice-empty-comments" style="font-size: 12px; color: var(--muted); font-style: italic; margin: 0 0 10px;">No comments or acknowledgements posted yet. Leave your reply below.</p>`;

  return `
    <article class="doctor-notice-card" style="border: 1px solid var(--border); border-radius: 12px; padding: 20px; box-shadow: 0 2px 8px rgba(0,0,0,0.02);">
      <div style="margin-bottom: 6px;">
        <h3 class="doctor-notice-title" style="font-size: 16.5px; font-weight: 700; margin: 0 0 6px; line-height: 1.35;">
          ${escapeHTML(notice.title)}
        </h3>
        <div class="doctor-notice-meta" style="font-size: 11.5px; color: var(--muted); display: flex; align-items: center; gap: 6px; margin-bottom: 12px;">
          <i class="fa-regular fa-clock"></i> ${escapeHTML(formatDoctorNoticeTime(notice.created_at))} &bull; Posted by <strong class="doctor-notice-author">${escapeHTML(notice.posted_by || "Hospital Admin")}</strong>
        </div>
      </div>

      <div class="doctor-notice-body" style="font-size: 13.5px; line-height: 1.6; white-space: pre-line; margin-bottom: 16px;">
        ${escapeHTML(notice.content)}
      </div>

      <!-- COMMENTS SECTION -->
      <div style="border-top: 1px solid var(--border); padding-top: 12px;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px;">
          <strong class="doctor-notice-comment-heading" style="font-size: 12px; font-weight: 700; display: flex; align-items: center; gap: 6px;">
            <i class="fa-solid fa-comments"></i>
            Doctor Acknowledgements (${comments.length})
          </strong>
        </div>

        <div class="doctor-comments-list" style="margin-bottom: 12px;">
          ${commentsHtml}
        </div>

        <!-- COMMENT COMPOSER -->
        <form id="doctorCommentForm_${notice.id}" class="doctor-comment-form" style="border: 1px solid var(--border); border-radius: 10px; padding: 10px 12px;">
          <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
            <label class="doctor-comment-label" for="doctorCommentInput_${notice.id}" style="font-size: 11px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.5px; color: var(--muted);">
              Reply / Acknowledge as <strong class="doctor-comment-self-name">${escapeHTML(currentDocName)}</strong>
            </label>
          </div>
          <div style="display: flex; gap: 8px; align-items: flex-end;">
            <textarea id="doctorCommentInput_${notice.id}" class="doctor-comment-textarea" rows="2" placeholder="Write acknowledgement, meeting RSVP, or clinical inquiry..." required style="flex: 1; padding: 8px 10px; border: 1px solid var(--border); border-radius: 8px; font-family: inherit; font-size: 12.5px; resize: vertical; box-sizing: border-box;"></textarea>
            <button type="submit" id="doctorCommentSubmit_${notice.id}" class="primary-btn" style="padding: 8px 14px; font-size: 12px; white-space: nowrap; height: 38px;">
              <i class="fa-solid fa-paper-plane"></i>
              <span>Post</span>
            </button>
          </div>
        </form>
      </div>
    </article>
  `;
}

async function openNoticesWorkspace() {
  const content = openWorkspace(
    "Hospital & Clinical Notices",
    "Official orders, clinical meetings, and administrative directives from hospital leadership arranged with newest notices first.",
    "fa-solid fa-bullhorn"
  );

  content.innerHTML = `
    <div class="workspace-loading">
      <i class="fa-solid fa-circle-notch fa-spin"></i>
      Loading hospital notices…
    </div>`;

  try {
    const api = typeof getApiHost === "function" ? getApiHost() : "";
    const res = await fetch(`${api}/api/notices?order=desc`, { cache: "no-store" });
    const data = await safeResJson(res);
    if (!res.ok || !data.success) throw new Error(data.error || "Unable to load notices.");
    const notices = Array.isArray(data.notices) ? data.notices : [];

    updateDoctorNoticeBadges(notices);

    if (!notices.length) {
      content.innerHTML = `
        <div class="workspace-empty-state">
          <i class="fa-solid fa-bullhorn"></i>
          <strong>No active hospital notices</strong>
          <span>There are currently no administrative directives or meeting calls.</span>
        </div>`;
      return;
    }

    const currentDocName = typeof getActiveDoctorName === "function" ? getActiveDoctorName() : "Doctor";
    const currentDocId = typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;

    content.innerHTML = `
      <div class="workspace-toolbar" style="margin-bottom: 18px; display: flex; justify-content: space-between; align-items: center;">
        <div class="workspace-counts">
          <span><strong>${notices.length}</strong> active notice${notices.length === 1 ? "" : "s"}</span>
          <span style="color: var(--green-700); font-weight: 600; margin-left: 12px;">
            <i class="fa-solid fa-arrow-down-wide-short"></i> Newest Notices First
          </span>
        </div>
        <button type="button" class="workspace-action" id="refreshDoctorNoticesBtn" style="margin: 0; padding: 7px 14px; font-size: 11px;">
          <i class="fa-solid fa-arrows-rotate"></i> Refresh
        </button>
      </div>
      <div class="doctor-notices-feed" style="display: flex; flex-direction: column; gap: 20px;">
        ${notices.map((notice) => renderDoctorNoticeCard(notice, currentDocName)).join("")}
      </div>`;

    document.getElementById("refreshDoctorNoticesBtn")?.addEventListener("click", openNoticesWorkspace);

    // Bind comment forms for each notice
    notices.forEach((notice) => {
      const form = document.getElementById(`doctorCommentForm_${notice.id}`);
      if (form) {
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const textarea = document.getElementById(`doctorCommentInput_${notice.id}`);
          const submitBtn = document.getElementById(`doctorCommentSubmit_${notice.id}`);
          const text = textarea?.value.trim();
          if (!text) return;

          const origHtml = submitBtn.innerHTML;
          submitBtn.disabled = true;
          submitBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Posting…';

          try {
            const postRes = await fetch(`${api}/api/notices/${notice.id}/comments`, {
              method: "POST",
              headers: { "Content-Type": "application/json" },
              body: JSON.stringify({
                author_name: currentDocName,
                doctor_id: currentDocId,
                comment_text: text,
                author_role: "doctor"
              })
            });
            const postData = await safeResJson(postRes);
            if (!postRes.ok || !postData.success) throw new Error(postData.error || "Failed to post comment.");

            showToast("Comment submitted successfully.");
            openNoticesWorkspace();
          } catch (err) {
            showToast("Error: " + err.message);
            submitBtn.disabled = false;
            submitBtn.innerHTML = origHtml;
          }
        });
      }
    });

  } catch (err) {
    content.innerHTML = `
      <div class="workspace-empty-state error-state">
        <i class="fa-solid fa-triangle-exclamation"></i>
        <strong>Notices unavailable</strong>
        <span>${escapeHTML(err.message || "Please refresh and try again.")}</span>
      </div>`;
  }
}

async function updateDoctorNoticeBadges(noticesList) {
  try {
    let notices = noticesList;
    if (!notices) {
      const api = typeof getApiHost === "function" ? getApiHost() : "";
      const res = await fetch(`${api}/api/notices?order=desc`, { cache: "no-store" });
      const data = await safeResJson(res);
      notices = Array.isArray(data.notices) ? data.notices : [];
    }
    const count = notices.length;
    const badge = document.getElementById("doctorNoticeNavBadge");
    if (badge) {
      badge.textContent = count;
      badge.style.display = count ? "inline-block" : "none";
    }
    const tag = document.getElementById("doctorNoticeCountTag");
    if (tag) {
      tag.textContent = `${count} Active`;
    }
    const snippet = document.getElementById("doctorRecentNoticeSnippet");
    if (snippet) {
      if (count > 0) {
        const latestNotice = notices[0];
        snippet.textContent = `Latest: ${latestNotice.title} (${latestNotice.notice_type || "Notice"})`;
      } else {
        snippet.textContent = "No pending notices or orders at this time.";
      }
    }
  } catch (err) {
    console.error("Notice badge update error:", err);
  }
}

// Wire up notice button on doctor dashboard
document.getElementById("doctorOpenNoticesBtn")?.addEventListener("click", () => {
  openNoticesWorkspace();
});

// Update notice badges on page load
if (document.getElementById("doctorNoticePreviewPanel") || document.getElementById("doctorNavNotices")) {
  updateDoctorNoticeBadges();
}

/* =====================================================
   AI REVIEWS WORKSPACE
   ===================================================== */

async function openAiReviewsWorkspace(event) {
  if (event && event.preventDefault) event.preventDefault();
  if (typeof showToast === "function") {
    showToast("AI Reviews is an upcoming feature in active development.");
  }
  return;

  content.innerHTML = `
    <div class="workspace-loading">
      <i class="fa-solid fa-circle-notch fa-spin"></i>
      Loading patient AI queries…
    </div>`;

  try {
    const api = typeof getApiHost === "function" ? getApiHost() : "";
    const [pendingRes, reviewedRes] = await Promise.all([
      fetch(`${api}/api/doctor/ai-reviews?status=Upcoming`, { cache: "no-store" }),
      fetch(`${api}/api/doctor/ai-reviews?status=Reviewed`, { cache: "no-store" })
    ]);
    const pendingData = await safeResJson(pendingRes);
    const reviewedData = await safeResJson(reviewedRes);

    const pending = (pendingRes.ok && pendingData.success && Array.isArray(pendingData.reviews)) ? pendingData.reviews : [];
    const reviewed = (reviewedRes.ok && reviewedData.success && Array.isArray(reviewedData.reviews)) ? reviewedData.reviews : [];

    // Store in global cache so Review AI Solution button works seamlessly
    window.cachedUpcomingAiReviews = pending;
    window.cachedPendingAiReviews = pending;

    // Update nav badge without "upcoming" word
    const navBadge = document.getElementById("doctorAiReviewNavBadge");
    if (navBadge) {
      navBadge.textContent = String(pending.length);
      navBadge.style.display = pending.length > 0 ? "inline-block" : "none";
    }

    const escapeSafe = (str) => String(str || '').replace(/[&<>"']/g, m => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'})[m]);

    content.innerHTML = `
      <div class="workspace-toolbar" style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px;">
        <div class="workspace-counts" style="display: flex; align-items: center; gap: 10px;">
          <span style="background: rgba(99, 102, 241, 0.12); color: #4f46e5; border: 1px solid rgba(99, 102, 241, 0.25); font-size: 12px; font-weight: 700; padding: 4px 10px; border-radius: 12px;">
            <strong>${pending.length}</strong> Pending Review
          </span>
          <span style="font-size: 12.5px; color: var(--muted);">
            Review patient inquiry solutions and provide doctor validation
          </span>
        </div>
        <div style="display: flex; gap: 8px; align-items: center; flex-wrap: wrap;">
          <button type="button" class="workspace-action" onclick="openDoctorAiReviewModal('history')" style="margin: 0; padding: 7px 14px; font-size: 11.5px; display: inline-flex; align-items: center; gap: 6px;">
            <i class="fa-solid fa-clock-rotate-left"></i> Reviewed History (${reviewed.length})
          </button>
          <button type="button" class="primary-btn" onclick="openDoctorAiReviewModal('write')" style="background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; padding: 7px 14px; border-radius: 8px; font-size: 11.5px; font-weight: 600; cursor: pointer; display: inline-flex; align-items: center; gap: 6px; box-shadow: 0 2px 8px rgba(99, 102, 241, 0.25);">
            <i class="fa-solid fa-plus"></i> Rate Custom Case
          </button>
          <button type="button" class="workspace-action" id="refreshDoctorAiReviewsBtn" style="margin: 0; padding: 7px 14px; font-size: 11.5px;">
            <i class="fa-solid fa-arrows-rotate"></i> Refresh
          </button>
        </div>
      </div>

      <div class="ai-reviews-workspace-list" style="display: flex; flex-direction: column; gap: 16px;">
        ${pending.length === 0 ? `
          <div style="text-align: center; padding: 40px 20px; border: 1.5px dashed var(--border); border-radius: 14px; background: rgba(99, 102, 241, 0.02);">
            <div style="font-size: 34px; color: #10b981; margin-bottom: 8px;"><i class="fa-solid fa-circle-check"></i></div>
            <strong style="display: block; font-size: 16px; color: var(--text);">All Patient AI Solutions Reviewed</strong>
            <p style="font-size: 13px; color: var(--muted); margin: 6px 0 16px; max-width: 480px; margin-left: auto; margin-right: auto;">
              Every AI solution generated for patient inquiries has been evaluated and verified by a clinician.
            </p>
            <div style="display: flex; justify-content: center; gap: 10px;">
              <button type="button" onclick="openDoctorAiReviewModal('history')" class="workspace-action" style="padding: 8px 16px; font-size: 12px;">View Reviewed History</button>
              <button type="button" onclick="openDoctorAiReviewModal('write')" class="primary-btn" style="background: linear-gradient(135deg, #6366f1, #4f46e5); color: white; border: none; padding: 8px 18px; font-size: 12px; border-radius: 8px;">Rate Custom Case</button>
            </div>
          </div>
        ` : pending.map((r, idx) => {
            const patientName = r.patient_name || "Patient";
            const initials = patientName.split(" ").map(w => w[0]).join("").slice(0, 2).toUpperCase() || "PT";
            const avatarColors = ["#4f46e5", "#059669", "#d97706", "#2563eb", "#7c3aed"];
            const avatarColor = avatarColors[idx % avatarColors.length];

            return `
              <div class="patient-ai-review-card">
                <div class="patient-ai-header">
                  <div class="patient-ai-patient-info">
                    <div class="patient-ai-avatar" style="background: ${avatarColor};">
                      ${initials}
                    </div>
                    <div>
                      <strong class="patient-ai-name">${escapeSafe(patientName)}</strong>
                      <span class="patient-ai-sub"><i class="fa-regular fa-clock"></i> Patient Inquiry • Needs Doctor Evaluation</span>
                    </div>
                  </div>
                  <div>
                    <span class="patient-ai-pending-badge">
                      <i class="fa-solid fa-clock"></i> Pending Review
                    </span>
                  </div>
                </div>

                <!-- Question Asked -->
                <div class="patient-ai-question-box">
                  <strong class="patient-ai-question-title">
                    <i class="fa-solid fa-circle-question"></i> Question Asked by Patient:
                  </strong>
                  <p class="patient-ai-question-text">
                    "${escapeSafe(r.patient_question)}"
                  </p>
                </div>

                <!-- AI Solution -->
                <div class="patient-ai-solution-box">
                  <strong class="patient-ai-solution-title">
                    <i class="fa-solid fa-wand-magic-sparkles"></i> AI Solution Generated for Patient:
                  </strong>
                  <p class="patient-ai-solution-text">
                    ${escapeSafe(r.ai_answer)}
                  </p>
                </div>

                <!-- Actions Footer -->
                <div class="patient-ai-footer">
                  <span class="patient-ai-footer-text"><i class="fa-solid fa-stethoscope"></i> Rate accuracy (1-5 ⭐) &amp; adjust dosage if necessary</span>
                  <button type="button" class="primary-btn" onclick="reviewUpcomingAiCase(${r.id})" style="background: linear-gradient(135deg, #4f46e5, #6366f1); color: white; border: none; padding: 8px 18px; border-radius: 9px; font-size: 12.5px; font-weight: 700; cursor: pointer; display: inline-flex; align-items: center; gap: 7px; box-shadow: 0 3px 10px rgba(79, 70, 229, 0.25);">
                    <i class="fa-solid fa-star"></i>
                    Review AI Solution
                  </button>
                </div>
              </div>
            `;
        }).join("")}
      </div>
    `;

    document.getElementById("refreshDoctorAiReviewsBtn")?.addEventListener("click", openAiReviewsWorkspace);

  } catch (err) {
    console.error("AI Reviews workspace error:", err);
    content.innerHTML = `
      <div class="workspace-empty-state">
        <i class="fa-solid fa-triangle-exclamation" style="color: #ef4444;"></i>
        <strong>Unable to load AI Reviews</strong>
        <span>Please check your connection and try refreshing.</span>
        <button type="button" class="workspace-action" onclick="openAiReviewsWorkspace()" style="margin-top: 12px;">Retry</button>
      </div>
    `;
  }
}
window.openAiReviewsWorkspace = openAiReviewsWorkspace;


