/* =====================================================
   AYURCASE
   Interactive JavaScript
   HTML + CSS UNCHANGED
   ===================================================== */


/* =====================================================
   ELEMENTS
   ===================================================== */

const caseModal = document.getElementById("caseModal");

const newCaseButtons = document.querySelectorAll(
    ".new-case-btn, .case-action"
);

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

function showToast(message) {

    if (!toast || !toastMessage) return;

    toastMessage.textContent = message;

    toast.classList.add("show");

    clearTimeout(toastTimer);

    toastTimer = setTimeout(() => {

        toast.classList.remove("show");

    }, 3000);

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

newCaseButtons.forEach(button => {

    button.addEventListener("click", function () {

        openCaseModal();

    });

});


/* Close button */

if (closeModal) {

    closeModal.addEventListener(
        "click",
        closeCaseModal
    );

}


/* Cancel button */

if (cancelModal) {

    cancelModal.addEventListener(
        "click",
        closeCaseModal
    );

}


/* Click outside modal */

if (caseModal) {

    caseModal.addEventListener(
        "click",
        function (event) {

            if (event.target === caseModal) {

                closeCaseModal();

            }

        }
    );

}


/* Escape key */

document.addEventListener(
    "keydown",
    function (event) {

        if (
            event.key === "Escape" &&
            caseModal &&
            caseModal.classList.contains("show")
        ) {

            closeCaseModal();

        }

    }
);


/* =====================================================
   CASE FORM
   ===================================================== */

if (caseForm) {

    caseForm.addEventListener(
        "submit",
        function (event) {

            event.preventDefault();

            const inputs =
                caseForm.querySelectorAll(
                    "input, select, textarea"
                );


            const patientName =
                inputs[0]?.value.trim() || "";

            const age =
                inputs[1]?.value || "";

            const gender =
                inputs[2]?.value || "";

            const complaint =
                inputs[3]?.value.trim() || "";


            if (
                !patientName ||
                !age ||
                !gender ||
                !complaint
            ) {

                showToast(
                    "Please complete all patient details."
                );

                return;

            }


            const newCase = {

                id: Date.now(),

                name: patientName,

                age: age,

                gender: gender,

                complaint: complaint,

                date:
                    new Date()
                        .toLocaleDateString(),

                status: "New"

            };


            let cases =
                JSON.parse(
                    localStorage.getItem(
                        "ayurcase-cases"
                    )
                ) || [];


            cases.push(newCase);


            localStorage.setItem(
                "ayurcase-cases",
                JSON.stringify(cases)
            );


            closeCaseModal();

            caseForm.reset();


            showToast(
                `${patientName}'s case created successfully.`
            );

        }
    );

}


/* =====================================================
   THEME
   ===================================================== */

let darkMode =
    localStorage.getItem(
        "ayurcase-dark"
    ) === "true";


function updateTheme() {

    if (!themeButton) return;


    if (darkMode) {

        document.body.classList.add("dark");

        themeButton.innerHTML =
            '<i class="fa-solid fa-sun"></i>';

        themeButton.title =
            "Switch to Light Mode";

    } else {

        document.body.classList.remove("dark");

        themeButton.innerHTML =
            '<i class="fa-solid fa-moon"></i>';

        themeButton.title =
            "Switch to Dark Mode";

    }

}


updateTheme();


if (themeButton) {

    themeButton.addEventListener(
        "click",
        function () {

            darkMode = !darkMode;


            localStorage.setItem(
                "ayurcase-dark",
                darkMode
            );


            updateTheme();


            showToast(
                darkMode
                    ? "Dark mode enabled."
                    : "Light mode enabled."
            );

        }
    );

}


/* =====================================================
   MOBILE SIDEBAR
   ===================================================== */

if (mobileMenu && sidebar) {

    mobileMenu.addEventListener(
        "click",
        function () {

            sidebar.classList.toggle(
                "open"
            );

        }
    );

}


/* =====================================================
   WORKSPACE SYSTEM
   ===================================================== */

function openWorkspace(
    title,
    description,
    icon
) {

    let workspace =
        document.getElementById(
            "ayurcaseWorkspace"
        );


    if (!workspace) {

        workspace =
            document.createElement(
                "div"
            );

        workspace.id =
            "ayurcaseWorkspace";


        workspace.innerHTML = `

            <div class="workspace-inner">

                <button
                    class="workspace-close"
                    id="workspaceClose"
                >
                    <i class="fa-solid fa-xmark"></i>
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


        document.body.appendChild(
            workspace
        );


        const style =
            document.createElement(
                "style"
            );


        style.id =
            "workspaceStyles";


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

                font-size:11px;

            }


            .workspace-box span {

                display:block;

                color:var(--muted);

                font-size:9px;

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

        `;


        document.head.appendChild(
            style
        );


        document
            .getElementById(
                "workspaceClose"
            )
            .addEventListener(
                "click",
                closeWorkspace
            );

    }


    document
        .getElementById(
            "workspaceTitle"
        )
        .textContent = title;


    document
        .getElementById(
            "workspaceDescription"
        )
        .textContent = description;


    document
        .querySelector(
            ".workspace-icon i"
        )
        .className = icon;


    workspace.style.display =
        "flex";


    document.body.style.overflow =
        "hidden";


    return document.getElementById(
        "workspaceContent"
    );

}


function closeWorkspace() {

    const workspace =
        document.getElementById(
            "ayurcaseWorkspace"
        );


    if (workspace) {

        workspace.style.display =
            "none";

    }


    document.body.style.overflow =
        "";

}


/* =====================================================
   SIDEBAR NAVIGATION
   ===================================================== */

navItems.forEach(item => {

    item.addEventListener(
        "click",
        function (event) {

            event.preventDefault();


            const page =
                item.dataset.page;


            navItems.forEach(nav => {

                nav.classList.remove(
                    "active"
                );

            });


            item.classList.add(
                "active"
            );


            updateBreadcrumb(
                page
            );


            if (sidebar) {

                sidebar.classList.remove(
                    "open"
                );

            }


            if (page === "dashboard") {

                closeWorkspace();

                showToast(
                    "Dashboard selected."
                );

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


            if (page === "prakriti") {

                openPrakritiWorkspace();

                return;

            }


            if (page === "ai") {

                openAIWorkspace();

                return;

            }

        }
    );

});


/* =====================================================
   BREADCRUMB
   ===================================================== */

function updateBreadcrumb(page) {

    const breadcrumb =
        document.querySelector(
            ".breadcrumb strong"
        );


    if (!breadcrumb) return;


    const names = {

        dashboard: "Dashboard",

        patients: "Patients",

        case: "New Case",

        history: "Case History",

        prakriti: "Prakriti",

        ai: "AI Assistant",

        analytics: "Analytics",

        settings: "Settings"

    };


    breadcrumb.textContent =
        names[page] ||
        "Dashboard";

}


function updateBreadcrumbText(text) {

    const breadcrumb =
        document.querySelector(
            ".breadcrumb strong"
        );


    if (breadcrumb) {

        breadcrumb.textContent =
            text;

    }

}


/* =====================================================
   PATIENTS WORKSPACE
   ===================================================== */

function openPatientsWorkspace() {

    const content =
        openWorkspace(

            "Patients",

            "Manage and review registered patient cases.",

            "fa-solid fa-users"

        );


    const cases =
        JSON.parse(
            localStorage.getItem(
                "ayurcase-cases"
            )
        ) || [];


    if (cases.length === 0) {

        content.innerHTML = `

            <div class="workspace-box">

                <strong>
                    No newly created cases yet.
                </strong>

                <span>
                    Create a new patient case to see it here.
                </span>

                <button
                    class="workspace-action"
                    id="workspaceNewCase"
                >
                    + Create New Case
                </button>

            </div>

        `;


        document
            .getElementById(
                "workspaceNewCase"
            )
            .addEventListener(
                "click",
                function () {

                    closeWorkspace();

                    openCaseModal();

                }
            );


        return;

    }


    content.innerHTML =
        cases.map(patient => `

            <div class="workspace-box">

                <strong>
                    ${escapeHTML(
                        patient.name
                    )}
                </strong>

                <span>
                    ${escapeHTML(
                        patient.age
                    )}
                    years •
                    ${escapeHTML(
                        patient.gender
                    )}
                    •
                    ${escapeHTML(
                        patient.complaint
                    )}
                </span>

            </div>

        `).join("");

}


/* =====================================================
   CASE HISTORY
   ===================================================== */

function openHistoryWorkspace() {

    const content =
        openWorkspace(

            "Case History",

            "Review previously created patient cases.",

            "fa-solid fa-clock-rotate-left"

        );


    const cases =
        JSON.parse(
            localStorage.getItem(
                "ayurcase-cases"
            )
        ) || [];


    if (cases.length === 0) {

        content.innerHTML = `

            <div class="workspace-box">

                <strong>
                    No case history available
                </strong>

                <span>
                    Your completed patient cases will appear here.
                </span>

            </div>

        `;

        return;

    }


    content.innerHTML =
        cases
            .slice()
            .reverse()
            .map(patient => `

                <div class="workspace-box">

                    <strong>
                        ${escapeHTML(
                            patient.name
                        )}
                    </strong>

                    <span>
                        Case created on
                        ${escapeHTML(
                            patient.date
                        )}
                    </span>

                    <span>
                        Complaint:
                        ${escapeHTML(
                            patient.complaint
                        )}
                    </span>

                </div>

            `)
            .join("");

}


/* =====================================================
   PRAKRITI WORKSPACE
   ===================================================== */

function openPrakritiWorkspace() {

    const content =
        openWorkspace(

            "Prakriti Assessment",

            "Perform a basic constitutional assessment for the patient.",

            "fa-solid fa-spa"

        );


    const questions = [

        "How is the patient's body structure?",

        "How is the patient's appetite?",

        "How is the patient's sleep pattern?",

        "How is the patient's energy level?"

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


        ${questions.map(
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

            `
        ).join("")}


        <button
            class="workspace-action"
            id="calculatePrakriti"
        >
            Calculate Assessment
        </button>

    `;


    document
        .getElementById(
            "calculatePrakriti"
        )
        .addEventListener(
            "click",
            calculatePrakriti
        );

}


function calculatePrakriti() {

    const selections =
        document.querySelectorAll(
            ".prakriti-select"
        );


    let vata = 0;
    let pitta = 0;
    let kapha = 0;


    selections.forEach(select => {

        if (
            select.value.includes(
                "Vata"
            )
        ) {

            vata++;

        }


        if (
            select.value.includes(
                "Pitta"
            )
        ) {

            pitta++;

        }


        if (
            select.value.includes(
                "Kapha"
            )
        ) {

            kapha++;

        }

    });


    if (
        vata +
        pitta +
        kapha ===
        selections.length
    ) {

        const scores = {

            Vata: vata,

            Pitta: pitta,

            Kapha: kapha

        };


        const result =
            Object.keys(scores)
                .sort(
                    (a, b) =>
                        scores[b] -
                        scores[a]
                )[0];


        showToast(
            `Assessment result: ${result} dominant`
        );

    } else {

        showToast(
            "Please answer all assessment questions."
        );

    }

}


/* =====================================================
   AI ASSISTANT
   ===================================================== */

function openAIWorkspace() {

    const content =
        openWorkspace(

            "AI Assistant",

            "Intelligent clinical documentation and case analysis.",

            "fa-solid fa-wand-magic-sparkles"

        );


    content.innerHTML = `

        <div class="workspace-box">

            <strong>
                Clinical Case Analyzer
            </strong>

            <span>
                Enter clinical information to generate a structured summary.
            </span>


            <textarea
                id="aiInput"
                placeholder="Enter patient observations, symptoms, history..."
                style="
                    width:100%;
                    min-height:130px;
                    margin-top:12px;
                    padding:12px;
                    border:1px solid var(--border);
                    border-radius:10px;
                    resize:vertical;
                    outline:none;
                "
            ></textarea>


            <button
                class="workspace-action"
                id="runAI"
            >

                <i class="fa-solid fa-sparkles"></i>

                Analyze Case

            </button>

        </div>


        <div
            class="workspace-box"
            id="aiResult"
            style="display:none;"
        ></div>

    `;


    document
        .getElementById(
            "runAI"
        )
        .addEventListener(
            "click",
            function () {

                const input =
                    document
                        .getElementById(
                            "aiInput"
                        )
                        .value
                        .trim();


                if (!input) {

                    showToast(
                        "Please enter clinical information first."
                    );

                    return;

                }


                const result =
                    document.getElementById(
                        "aiResult"
                    );


                result.style.display =
                    "block";


                result.innerHTML = `

                    <strong>
                        Preliminary Structured Summary
                    </strong>

                    <span>
                        The information has been organized for practitioner review.
                    </span>

                    <span>
                        <b>Clinical Input:</b>
                        ${escapeHTML(input)}
                    </span>

                    <span>
                        <b>Next Step:</b>
                        Practitioner review and clinical assessment recommended.
                    </span>

                `;


                showToast(
                    "Case analysis completed."
                );

            }
        );

}


/* =====================================================
   AI DASHBOARD BUTTON
   ===================================================== */

const aiButton =
    document.querySelector(
        ".ai-button"
    );


if (aiButton) {

    aiButton.addEventListener(
        "click",
        function () {

            openAIWorkspace();

        }
    );

}


/* =====================================================
   QUICK ACTIONS
   ===================================================== */

const quickCards =
    document.querySelectorAll(
        ".quick-card"
    );


quickCards.forEach(card => {

    card.addEventListener(
        "click",
        function () {

            if (
                card.classList.contains(
                    "case-action"
                )
            ) {

                openCaseModal();

                return;

            }


            const title =
                card.querySelector(
                    "strong"
                )?.textContent.trim() ||
                "";


            if (
                title === "Add Patient"
            ) {

                openCaseModal();

                return;

            }


            if (
                title === "Prakriti Test"
            ) {

                openPrakritiWorkspace();

                return;

            }


            showToast(
                `${title} workspace opened.`
            );

        }
    );

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

const notificationButton =
    document.querySelector(
        ".notification-btn"
    );


function openNotificationWorkspace() {

    const content =
        openWorkspace(

            "Notifications",

            "Stay updated with important AYURCASE activities.",

            "fa-solid fa-bell"

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


    const clearButton =
        document.getElementById(
            "clearNotifications"
        );


    if (clearButton) {

        clearButton.addEventListener(
            "click",
            function () {

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


                showToast(
                    "All notifications marked as read."
                );

            }
        );

    }

}


/*
   Attach notification event
*/

if (notificationButton) {

    notificationButton.addEventListener(
        "click",
        function (event) {

            event.preventDefault();

            event.stopPropagation();

            openNotificationWorkspace();

        }
    );

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

let helpElements =
    document.querySelectorAll(
        ".help-card, .help-btn, .need-help, .help-button"
    );


/*
   If the original HTML doesn't have one of the
   expected classes, find the element by text.
*/

if (helpElements.length === 0) {

    const allElements =
        document.querySelectorAll(
            "a, button, div, span"
        );


    const detectedHelpElements = [];


    allElements.forEach(element => {

        const text =
            element.textContent
                ?.trim()
                .toLowerCase();


        if (
            text === "need help" ||
            text === "help" ||
            text.includes("need help")
        ) {

            detectedHelpElements.push(
                element
            );

        }

    });


    helpElements =
        detectedHelpElements;

}


/* Remove duplicate elements */

const uniqueHelpElements =
    [...new Set(helpElements)];


function openHelpWorkspace() {

    const content =
        openWorkspace(

            "Help & Support",

            "Get assistance with AYURCASE and learn how to use the platform.",

            "fa-solid fa-circle-question"

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


    const contactSupport =
        document.getElementById(
            "contactSupport"
        );


    if (contactSupport) {

        contactSupport.addEventListener(
            "click",
            function () {

                showToast(
                    "Support request option selected."
                );

            }
        );

    }

}


/* Attach Help events */

uniqueHelpElements.forEach(
    element => {

        element.addEventListener(
            "click",
            function (event) {

                event.preventDefault();

                event.stopPropagation();

                openHelpWorkspace();

            }
        );

    }
);


/* =====================================================
   VIEW ALL PATIENTS
   ===================================================== */

const viewAll =
    document.querySelector(
        ".text-btn"
    );


if (viewAll) {

    viewAll.addEventListener(
        "click",
        function () {

            openPatientsWorkspace();

        }
    );

}


/* =====================================================
   PATIENT ROWS
   ===================================================== */

const patientRows =
    document.querySelectorAll(
        ".patient-row"
    );


patientRows.forEach(row => {

    row.addEventListener(
        "dblclick",
        function () {

            const patient =
                row.querySelector(
                    ".patient-info strong"
                )?.textContent;


            if (patient) {

                showToast(
                    `Opening ${patient}'s case.`
                );

            }

        }
    );

});


/* =====================================================
   MORE BUTTONS
   ===================================================== */

const moreButtons =
    document.querySelectorAll(
        ".more-btn"
    );


moreButtons.forEach(button => {

    button.addEventListener(
        "click",
        function (event) {

            event.stopPropagation();


            const row =
                button.closest(
                    ".patient-row"
                );


            const patient =
                row?.querySelector(
                    ".patient-info strong"
                )?.textContent ||
                "Patient";


            showPatientMenu(
                patient,
                button
            );

        }
    );

});


function showPatientMenu(
    patient,
    button
) {

    const existing =
        document.getElementById(
            "patientActionMenu"
        );


    if (existing) {

        existing.remove();

    }


    const menu =
        document.createElement(
            "div"
        );


    menu.id =
        "patientActionMenu";


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

    `;


    menu.style.cssText = `

        position:fixed;

        background:white;

        border:1px solid #e5e9e5;

        border-radius:12px;

        padding:7px;

        width:170px;

        box-shadow:
            0 15px 35px rgba(0,0,0,.15);

        z-index:900;

    `;


    document.body.appendChild(
        menu
    );


    const rect =
        button.getBoundingClientRect();


    menu.style.top =
        `${rect.bottom + 6}px`;


    menu.style.left =
        `${Math.max(
            10,
            rect.left - 140
        )}px`;


    menu.querySelectorAll(
        "button"
    ).forEach(
        actionButton => {

            actionButton.style.cssText = `

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


            actionButton.addEventListener(
                "click",
                function () {

                    const action =
                        this.dataset.action;


                    if (
                        action === "view"
                    ) {

                        showToast(
                            `Opening ${patient}'s case.`
                        );

                    }


                    if (
                        action === "history"
                    ) {

                        openHistoryWorkspace();

                    }


                    menu.remove();

                }
            );

        }
    );


    setTimeout(
        () => {

            document.addEventListener(
                "click",
                function closeMenu(event) {

                    if (
                        !menu.contains(
                            event.target
                        ) &&
                        event.target !== button
                    ) {

                        menu.remove();

                        document.removeEventListener(
                            "click",
                            closeMenu
                        );

                    }

                }
            );

        },
        10
    );

}


/* =====================================================
   CALENDAR
   ===================================================== */

const calendarButton =
    document.querySelector(
        ".calendar-btn"
    );


if (calendarButton) {

    calendarButton.addEventListener(
        "click",
        function () {

            openCalendarWorkspace();

        }
    );

}


function openCalendarWorkspace() {

    const content =
        openWorkspace(

            "Upcoming Schedule",

            "Review your upcoming patient follow-ups.",

            "fa-regular fa-calendar"

        );


    const appointments = [

        {
            date: "31 AUG",
            patient: "Rahul Sharma",
            type: "Follow-up consultation",
            time: "10:30 AM"
        },

        {
            date: "01 SEP",
            patient: "Priya Das",
            type: "Progress assessment",
            time: "11:15 AM"
        },

        {
            date: "03 SEP",
            patient: "Sneha Mukherjee",
            type: "Case review",
            time: "04:00 PM"
        }

    ];


    content.innerHTML =
        appointments.map(
            item => `

                <div class="workspace-box">

                    <strong>
                        ${item.date}
                        —
                        ${item.patient}
                    </strong>

                    <span>
                        ${item.type}
                    </span>

                    <span>
                        Scheduled at
                        ${item.time}
                    </span>

                </div>

            `
        ).join("");

}


/* =====================================================
   ANALYTICS & SETTINGS
   ===================================================== */

const sidebarLinks =
    document.querySelectorAll(
        ".sidebar .nav-item"
    );


sidebarLinks.forEach(link => {

    const text =
        link.querySelector(
            "span"
        )?.textContent
        .trim();


    if (text === "Analytics") {

        link.addEventListener(
            "click",
            function (event) {

                event.preventDefault();


                sidebarLinks.forEach(
                    nav =>
                        nav.classList.remove(
                            "active"
                        )
                );


                link.classList.add(
                    "active"
                );


                updateBreadcrumbText(
                    "Analytics"
                );


                openAnalyticsWorkspace();

            }
        );

    }


    if (text === "Settings") {

        link.addEventListener(
            "click",
            function (event) {

                event.preventDefault();


                sidebarLinks.forEach(
                    nav =>
                        nav.classList.remove(
                            "active"
                        )
                );


                link.classList.add(
                    "active"
                );


                updateBreadcrumbText(
                    "Settings"
                );


                openSettingsWorkspace();

            }
        );

    }

});


/* =====================================================
   ANALYTICS WORKSPACE
   ===================================================== */

function openAnalyticsWorkspace() {

    const content =
        openWorkspace(

            "Analytics",

            "Overview of your clinical documentation activity.",

            "fa-solid fa-chart-line"

        );


    const cases =
        JSON.parse(
            localStorage.getItem(
                "ayurcase-cases"
            )
        ) || [];


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

    const content =
        openWorkspace(

            "Settings",

            "Manage your AYURCASE workspace preferences.",

            "fa-solid fa-gear"

        );


    content.innerHTML = `

        <div class="workspace-box">

            <strong>
                Appearance
            </strong>

            <span>
                Switch between light and dark mode.
            </span>


            <button
                class="workspace-action"
                id="settingsTheme"
            >
                Toggle Theme
            </button>

        </div>


        <div class="workspace-box">

            <strong>
                Practitioner
            </strong>

            <span>
                Dr. Arindam Sen
            </span>

        </div>


        <div class="workspace-box">

            <strong>
                Platform
            </strong>

            <span>
                AYURCASE • AYUSH Patient Case-Taking Platform
            </span>

        </div>

    `;


    const settingsTheme =
        document.getElementById(
            "settingsTheme"
        );


    if (settingsTheme) {

        settingsTheme.addEventListener(
            "click",
            function () {

                if (themeButton) {

                    themeButton.click();

                }

            }
        );

    }

}


/* =====================================================
   DOCTOR PROFILE
   ===================================================== */

const topDoctor =
    document.querySelector(
        ".top-doctor"
    );


if (topDoctor) {

    topDoctor.addEventListener(
        "click",
        function () {

            openProfileWorkspace();

        }
    );

}


function openProfileWorkspace() {

    const content =
        openWorkspace(

            "Practitioner Profile",

            "Your AYURCASE practitioner account.",

            "fa-solid fa-user-doctor"

        );


    content.innerHTML = `

        <div class="workspace-box">

            <strong>
                Dr. Arindam Sen
            </strong>

            <span>
                AYUSH Practitioner
            </span>

        </div>


        <div class="workspace-box">

            <strong>
                Account Status
            </strong>

            <span>
                Active practitioner account
            </span>

        </div>

    `;

}


/* =====================================================
   ESCAPE HTML
   ===================================================== */

function escapeHTML(value) {

    return String(value)

        .replace(
            /&/g,
            "&amp;"
        )

        .replace(
            /</g,
            "&lt;"
        )

        .replace(
            />/g,
            "&gt;"
        )

        .replace(
            /"/g,
            "&quot;"
        )

        .replace(
            /'/g,
            "&#039;"
        );

}


/* =====================================================
   SYSTEM STATUS
   ===================================================== */

console.log(
    "%c AYURCASE ",
    "background:#173b2b;color:white;padding:8px;border-radius:5px;font-weight:bold;"
);

console.log(
    "Digital AYUSH Patient Case-Taking Platform"
);

console.log(
    "System Status: ONLINE"
);