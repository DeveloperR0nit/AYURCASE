/* =====================================================
   AYURCASE - DATABASE-FIRST CLINICAL & AUTH RUNTIME
   All data (Cases, Appointments, Theme, Progress, Sessions)
   persisted in SQLite Database (backend/ayurcase.db).
   ===================================================== */

// Helper to determine API Host URL
function getApiHost() {
    if (typeof window !== "undefined" && window.location.protocol.startsWith("http")) {
        // When the Flask app serves the frontend, keep API traffic on the same
        // origin.  The previous implementation sent every non-5000 deployment
        // to the visitor's own localhost, which breaks hosted deployments.
        const isLocalHost = ["localhost", "127.0.0.1"].includes(window.location.hostname);
        return isLocalHost && window.location.port !== "5000" ? "http://127.0.0.1:5000" : "";
    }
    return "http://127.0.0.1:5000";
}

// This mirrors the server-side fallback so an interrupted deployment, proxy,
// or network connection still leaves the user with a useful assistant reply.
function getAssistantFallbackResponse(question) {
    const normalized = String(question || "").toLowerCase();

    if (["chest pain", "difficulty breathing", "suicid", "unconscious", "severe bleeding"].some(term => normalized.includes(term))) {
        return "Your message may describe an emergency. Please contact local emergency services or seek urgent medical care now.";
    }

    if (["appointment", "book", "consultation"].some(term => normalized.includes(term))) {
        return "I received your appointment question. Open the appointment section, select an available practitioner, choose a date and time, then confirm the booking. Please try the AI again shortly for more specific help.";
    }

    if (normalized.includes("abha") || normalized.includes("profile")) {
        return "I received your profile question. You can review your Digital ABHA Health Card and profile from the patient dashboard. Please try the AI again shortly for more specific help.";
    }

    return "I received your question, but the live AI service is temporarily unavailable. Please try again shortly. For urgent health concerns, contact a qualified clinician or local emergency services.";
}

function escapeHtml(value) {
    return String(value ?? "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

// In-Memory Database Fallback Store
var memoryStore = {};
var isSyncingToDb = false;

/* Safe storage wrapper with immediate SQLite write-through */
var safeStorage = {
    getItem: function(key) {
        try {
            if (typeof window !== "undefined" && window.localStorage) {
                const val = window.localStorage.getItem(key);
                if (val !== null) return val;
            }
            return memoryStore[key] || null;
        } catch (_) {
            return memoryStore[key] || null;
        }
    },
    setItem: function(key, val) {
        const strVal = String(val);
        memoryStore[key] = strVal;
        isSyncingToDb = true;
        try {
            if (typeof window !== "undefined" && window.localStorage) {
                window.localStorage.setItem(key, strVal);
            }
        } catch (_) {}
        isSyncingToDb = false;
        syncKeyToDatabase(key, strVal);
    },
    removeItem: function(key) {
        delete memoryStore[key];
        try {
            if (typeof window !== "undefined" && window.localStorage) {
                window.localStorage.removeItem(key);
            }
        } catch (_) {}
        syncKeyDeletionToDatabase(key);
    }
};

/* =====================================================
   0. TRANSPARENT DATABASE STORAGE INTERCEPTOR
   Intercepts script.js localStorage operations and writes to SQLite
   ===================================================== */

(function setupStorageInterceptor() {
    if (typeof window === "undefined") return;

    try {
        const rawStorage = window.localStorage;
        if (!rawStorage) return;

        const nativeSetItem = rawStorage.setItem.bind(rawStorage);
        const nativeRemoveItem = rawStorage.removeItem.bind(rawStorage);

        rawStorage.setItem = function(key, val) {
            const strVal = String(val);
            memoryStore[key] = strVal;
            try {
                nativeSetItem(key, strVal);
            } catch (_) {}

            if (!isSyncingToDb) {
                syncKeyToDatabase(key, strVal);
            }
        };

        rawStorage.removeItem = function(key) {
            delete memoryStore[key];
            try {
                nativeRemoveItem(key);
            } catch (_) {}

            if (!isSyncingToDb) {
                syncKeyDeletionToDatabase(key);
            }
        };
    } catch (e) {
        console.warn("Storage interceptor initialized with safe fallback:", e);
    }
})();

async function syncKeyToDatabase(key, value) {
    const api = getApiHost();
    try {
        // 1. If clinical cases updated, sync to SQLite cases table
        if (key === "ayurcase-cases") {
            try {
                const casesList = typeof value === "string" ? JSON.parse(value) : value;
                if (Array.isArray(casesList)) {
                    const doctorId = typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;
                    fetch(`${api}/api/cases/sync`, {
                        method: "POST",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ cases: casesList, doctor_id: doctorId })
                    }).catch(() => {});
                }
            } catch (_) {}
        }

        // 2. If theme updated, sync to SQLite user_preferences
        if (key === "ayurcase-dark" || key === "ayurcase_theme") {
            const isDark = (value === "true" || value === "dark");
            fetch(`${api}/api/user/preferences`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: 1, key: "theme", value: isDark ? "dark" : "light" })
            }).catch(() => {});
        }

        // 3. If study progress/wishlist/completed updated, sync to SQLite study_progress
        if (key === "ayurcase-progress" || key === "ayurcase-wishlist" || key === "ayurcase-completed") {
            fetch(`${api}/api/study/progress`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ user_id: 1, module_key: key, progress_data: value })
            }).catch(() => {});
        }

        // 4. Universal app storage persistence in SQLite
        fetch(`${api}/api/storage/${encodeURIComponent(key)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ value: value })
        }).catch(() => {});
    } catch (_) {}
}

async function syncKeyDeletionToDatabase(key) {
    const api = getApiHost();
    try {
        fetch(`${api}/api/storage/${encodeURIComponent(key)}`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ value: null })
        }).catch(() => {});
    } catch (_) {}
}

/* =====================================================
   INITIAL DATABASE LOAD & AUTO-MIGRATION
   Pushes existing local storage to SQLite and hydrates from SQLite
   ===================================================== */

async function initDatabaseStorage() {
    const api = getApiHost();

    // Initial load is strictly read-only to avoid triggering file watchers / reloads.

    // 2. Fetch authoritative cases from SQLite database
    try {
        const doctorId = typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;
        const caseQuery = doctorId ? `?doctor_id=${encodeURIComponent(doctorId)}` : "";
        const res = await fetch(`${api}/api/cases${caseQuery}`);
        const data = await res.json();
        if (data.success && Array.isArray(data.cases)) {
            isSyncingToDb = true;
            try {
                if (window.localStorage) {
                    window.localStorage.setItem("ayurcase-cases", JSON.stringify(data.cases));
                }
            } catch (_) {}
            memoryStore["ayurcase-cases"] = JSON.stringify(data.cases);
            isSyncingToDb = false;

            // Trigger script.js re-render if present on page
            if (typeof renderPatientsdashboard === "function") {
                try { renderPatientsdashboard(); } catch (_) {}
            }
            if (typeof moreButton === "function") {
                try { moreButton(); } catch (_) {}
            }
        }
    } catch (e) {
        console.warn("Could not fetch cases from SQLite:", e);
    }

    // 3. Fetch all key-value app state from SQLite database
    try {
        const res = await fetch(`${api}/api/storage/all`);
        const data = await res.json();
        if (data.success && data.storage) {
            isSyncingToDb = true;
            for (const [k, v] of Object.entries(data.storage)) {
                const strVal = typeof v === "string" ? v : JSON.stringify(v);
                memoryStore[k] = strVal;
                try {
                    if (window.localStorage) window.localStorage.setItem(k, strVal);
                } catch (_) {}
            }
            isSyncingToDb = false;

            // Apply theme preference from database
            if (data.storage["ayurcase-dark"] !== undefined || data.storage["ayurcase_theme"] !== undefined) {
                const dbDark = data.storage["ayurcase-dark"] === "true" || data.storage["ayurcase_theme"] === "dark";
                applyTheme(dbDark, false);
            }
        }
    } catch (e) {
        console.warn("Could not fetch storage from SQLite:", e);
    }

    // 4. Attach DOM synchronization hooks for Case Add & Case Delete
    initCaseTakingDomHooks();
}

function initCaseTakingDomHooks() {
    // script.js writes the complete case collection to localStorage. The
    // storage interceptor above already synchronizes that write through
    // /api/cases/sync; posting the newest case here as well created duplicates.

    // Intercept Case Deletion in Doctor Workspace
    document.addEventListener("click", function(e) {
        if (e.target && e.target.parentElement && e.target.parentElement.classList.contains("cases-close-btn")) {
            const card = e.target.closest(".workspace-box");
            const patientName = card ? card.firstElementChild?.textContent?.trim() : null;
            if (patientName) {
                fetch(`${getApiHost()}/api/cases/${encodeURIComponent(patientName)}`, {
                    method: "DELETE"
                }).catch(() => {});
            }
        }
    });
}


/* =====================================================
   1. THEME HANDLING (SQLite Synchronized)
   ===================================================== */

function isDarkMode() {
    try {
        const darkSetting = safeStorage.getItem("ayurcase-dark");
        if (darkSetting !== null) {
            return darkSetting === "true";
        }
        return safeStorage.getItem("ayurcase_theme") === "dark";
    } catch (_) {
        return false;
    }
}

function updateThemeIcons(isDark) {
    const themeToggleBtns = document.querySelectorAll(".theme-btn, #themeToggle");
    themeToggleBtns.forEach(btn => {
        const icon = btn.querySelector("i");
        if (icon) {
            icon.className = isDark ? "fa-solid fa-sun" : "fa-solid fa-moon";
        }
        btn.title = isDark ? "Switch to Light Mode" : "Switch to Dark Mode";
        btn.setAttribute("aria-label", isDark ? "Switch to Light Mode" : "Switch to Dark Mode");
    });
}

function applyTheme(isDark, persist = false) {
    if (isDark) {
        document.documentElement.classList.add("dark");
        if (document.body) document.body.classList.add("dark");
    } else {
        document.documentElement.classList.remove("dark");
        if (document.body) document.body.classList.remove("dark");
    }

    if (persist) {
        safeStorage.setItem("ayurcase-dark", isDark ? "true" : "false");
        safeStorage.setItem("ayurcase_theme", isDark ? "dark" : "light");
    }

    updateThemeIcons(isDark);
}

window.toggleTheme = function() {
    const nextDark = !isDarkMode();
    applyTheme(nextDark, true);
    if (typeof showToastNotice === "function") {
        showToastNotice(nextDark ? "Dark mode enabled." : "Light mode enabled.");
    } else if (typeof showToast === "function") {
        showToast(nextDark ? "Dark mode enabled." : "Light mode enabled.");
    }
};

function initTheme() {
    applyTheme(isDarkMode(), false);

    const themeToggleBtns = document.querySelectorAll(".theme-btn, #themeToggle");
    themeToggleBtns.forEach(btn => {
        btn.onclick = (e) => {
            e.preventDefault();
            window.toggleTheme();
        };
    });

    window.addEventListener("storage", (e) => {
        if (e.key === "ayurcase-dark" || e.key === "ayurcase_theme") {
            applyTheme(isDarkMode(), false);
        }
        if (e.key === "ayurcase_appointments_updated") {
            loadPatientAppointments();
            loadDoctorAppointments();
        }
    });

    if (window.MutationObserver && document.body) {
        let isSyncing = false;
        const observer = new MutationObserver(() => {
            if (isSyncing) return;
            const bodyDark = document.body.classList.contains("dark");
            if (bodyDark !== isDarkMode()) {
                isSyncing = true;
                observer.disconnect();
                applyTheme(bodyDark, false);
                observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
                isSyncing = false;
            }
        });
        observer.observe(document.body, { attributes: true, attributeFilter: ["class"] });
    }
}


/* =====================================================
   2. PASSWORD VISIBILITY
   ===================================================== */

function initPasswordToggles() {
    const toggleButtons = document.querySelectorAll(".password-toggle-btn");
    toggleButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const targetId = btn.getAttribute("data-target") || "password";
            const input = document.getElementById(targetId);
            const icon = btn.querySelector("i");
            if (!input) return;

            if (input.type === "password") {
                input.type = "text";
                if (icon) icon.className = "fa-regular fa-eye-slash";
                btn.setAttribute("aria-label", "Hide password");
            } else {
                input.type = "password";
                if (icon) icon.className = "fa-regular fa-eye";
                btn.setAttribute("aria-label", "Show password");
            }
        });
    });
}

function generateAbhaId() {
    const r1 = Math.floor(1000 + Math.random() * 9000);
    const r2 = Math.floor(1000 + Math.random() * 9000);
    const id = `ABHA-${r1}-${r2}`;
    const abhaInput = document.getElementById("signupAbhaId");
    if (abhaInput) {
        abhaInput.value = id;
        showToastNotice(`Generated new ABHA ID: ${id}`);
    }
    return id;
}

function fillDemoSignup() {
    const nameInput = document.getElementById("signupFullName");
    const emailInput = document.getElementById("signupEmail");
    const phoneInput = document.getElementById("signupPhone");
    const abhaInput = document.getElementById("signupAbhaId");
    const ageInput = document.getElementById("signupAge");
    const genderInput = document.getElementById("signupGender");
    const bgInput = document.getElementById("signupBloodGroup");
    const prakritiInput = document.getElementById("signupPrakriti");
    const passInput = document.getElementById("signupPassword");
    const confirmInput = document.getElementById("signupConfirmPassword");

    const rNum = Math.floor(1000 + Math.random() * 9000);
    if (nameInput) nameInput.value = "Aditi Sen";
    if (emailInput) emailInput.value = `aditi.sen${rNum}@ayurcase.com`;
    if (phoneInput) phoneInput.value = "+91 98312 44550";
    if (abhaInput) abhaInput.value = `ABHA-${rNum}-8810`;
    if (ageInput) ageInput.value = "29";
    if (genderInput) genderInput.value = "Female";
    if (bgInput) bgInput.value = "B+";
    if (prakritiInput) prakritiInput.value = "Pitta-Kapha";
    if (passInput) passInput.value = "aditi123";
    if (confirmInput) confirmInput.value = "aditi123";

    showToastNotice("Demo patient profile populated (Aditi Sen)");
}

async function handlePatientSignup(event) {
    if (event) {
        if (typeof event.preventDefault === "function") event.preventDefault();
        if (typeof event.stopPropagation === "function") event.stopPropagation();
    }

    const submitBtn = document.getElementById("signupSubmitBtn");
    const origBtnText = submitBtn ? submitBtn.innerHTML : "Create Health Account";

    const name = document.getElementById("signupFullName")?.value.trim() || "";
    const email = document.getElementById("signupEmail")?.value.trim() || "";
    let abhaId = document.getElementById("signupAbhaId")?.value.trim() || "";
    const phone = document.getElementById("signupPhone")?.value.trim() || "";
    const ageValue = document.getElementById("signupAge")?.value || "";
    const age = parseInt(ageValue, 10);
    const gender = document.getElementById("signupGender")?.value || "";
    const bloodGroup = document.getElementById("signupBloodGroup")?.value || "B+";
    const prakriti = document.getElementById("signupPrakriti")?.value || "Pitta";
    const password = document.getElementById("signupPassword")?.value || "";
    const confirmPassword = document.getElementById("signupConfirmPassword")?.value || "";

    if (!name) {
        showToastNotice("Registration failed: please enter your full name.", "error");
        return false;
    }
    if (!email) {
        showToastNotice("Registration failed: please enter your email address.", "error");
        return false;
    }
    if (!password || password.length < 6) {
        showToastNotice("Registration failed: password must be at least 6 characters.", "error");
        return false;
    }
    if (password !== confirmPassword) {
        showToastNotice("Registration failed: passwords do not match.", "error");
        return false;
    }
    if (!Number.isInteger(age) || age < 1 || age > 120) {
        showToastNotice("Registration failed: enter a valid age between 1 and 120.", "error");
        return false;
    }
    if (!gender) {
        showToastNotice("Registration failed: please select your gender.", "error");
        return false;
    }

    if (!abhaId) {
        abhaId = generateAbhaId();
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Creating Account...`;
    }

    const payload = {
        name: name,
        email: email,
        username: email,
        password: password,
        abha_id: abhaId,
        phone: phone,
        age: age,
        gender: gender,
        blood_group: bloodGroup,
        prakriti_primary: prakriti
    };

    const api = getApiHost();

    try {
        const res = await fetch(`${api}/api/auth/register-patient`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        const data = await res.json();

        if (res.ok && data.success) {
            // Registration creates an account only. A fresh sign-in is required
            // before the patient can access their health dashboard.
            showToastNotice("Account created. Please sign in to continue.");

            setTimeout(() => {
                try {
                    window.location.replace(`login-patient.html?abhaId=${encodeURIComponent(abhaId)}`);
                } catch (_) {
                    window.location.href = `login-patient.html?abhaId=${encodeURIComponent(abhaId)}`;
                }
            }, 700);
            return false;
        } else {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = origBtnText;
            }
            showToastNotice(data.error || "Registration failed. Please check your details.", "error");
            return false;
        }
    } catch (err) {
        console.warn("Backend registration error, using local fallback:", err);
        // Keep the offline fallback on the same sign-in path: it must not
        // create a local authenticated session after registration.
        showToastNotice(`Account created! Please sign in, ${name}.`);
        setTimeout(() => {
            window.location.href = `login-patient.html?abhaId=${encodeURIComponent(abhaId)}`;
        }, 700);
        return false;
    }
}

/* =====================================================
   3. ROLE AUTHENTICATION & SECURE REDIRECTION
   ===================================================== */

function checkUrlParamsAndClean() {
    try {
        if (!window.location.search) return;
        const params = new URLSearchParams(window.location.search);
        const abha = params.get("abhaId");
        const user = params.get("username") || params.get("adminId") || params.get("email");

        const abhaEl = document.getElementById("abhaId");
        const userEl = document.getElementById("username") || document.getElementById("adminId") || document.getElementById("email");

        if (abhaEl && abha && !abhaEl.value) abhaEl.value = abha;
        if (userEl && user && !userEl.value) userEl.value = user;

        // Never read passwords from URLs. URLs can end up in browser history,
        // server logs, referrer headers, and screenshots.
        if (window.history && window.history.replaceState) {
            const cleanUrl = window.location.pathname;
            window.history.replaceState({}, document.title, cleanUrl);
        }
    } catch (_) {}
}

async function handleDoctorLogin(event) {
    if (event) {
        if (typeof event.preventDefault === "function") event.preventDefault();
        if (typeof event.stopPropagation === "function") event.stopPropagation();
    }
    const username = (document.getElementById("username") || document.getElementById("email"))?.value.trim() || "";
    const password = document.getElementById("password")?.value || "";
    const accountSelect = document.getElementById("doctorAccount");
    const selectedAccount = accountSelect?.value.trim() || "";
    const selectedCouncil = accountSelect?.selectedOptions?.[0]?.dataset?.council || "";
    const normalizedUsername = username.toLowerCase();

    if (!selectedAccount) {
        showToastNotice("Sign-in failed: select the practitioner account first.", "error");
        return false;
    }
    if (normalizedUsername !== selectedAccount.toLowerCase() && normalizedUsername !== selectedCouncil.toLowerCase()) {
        showToastNotice("Sign-in failed: the registration ID must match the selected practitioner.", "error");
        return false;
    }

    return authenticateUser("doctor", username, password, "doctor-dashboard.html", selectedAccount);
}

function handlePatientLogin(event) {
    if (event) {
        if (typeof event.preventDefault === "function") event.preventDefault();
        if (typeof event.stopPropagation === "function") event.stopPropagation();
    }
    const abhaId = (document.getElementById("abhaId") || document.getElementById("email") || document.getElementById("username"))?.value.trim() || "";
    const password = document.getElementById("password")?.value || "";
    authenticateUser("patient", abhaId, password, "patient-dashboard.html");
    return false;
}

function handleAdminLogin(event) {
    if (event) {
        if (typeof event.preventDefault === "function") event.preventDefault();
        if (typeof event.stopPropagation === "function") event.stopPropagation();
    }
    const adminId = (document.getElementById("adminId") || document.getElementById("email") || document.getElementById("username"))?.value.trim() || "";
    const password = document.getElementById("password")?.value || "";
    authenticateUser("admin", adminId, password, "admin-dashboard.html");
    return false;
}

function initLoginForms() {
    checkUrlParamsAndClean();

    const forms = [
        { id: "doctorLoginForm", handler: handleDoctorLogin },
        { id: "patientLoginForm", handler: handlePatientLogin },
        { id: "adminLoginForm", handler: handleAdminLogin },
        { id: "patientSignupForm", handler: handlePatientSignup }
    ];

    forms.forEach(({ id, handler }) => {
        const form = document.getElementById(id);
        if (!form) return;

        form.onsubmit = function(e) {
            if (e && typeof e.preventDefault === "function") e.preventDefault();
            if (e && typeof e.stopPropagation === "function") e.stopPropagation();
            handler(e);
            return false;
        };

        form.addEventListener("submit", function(e) {
            e.preventDefault();
            e.stopPropagation();
            handler(e);
            return false;
        });

        const submitBtn = form.querySelector(".auth-submit-btn");
        if (submitBtn) {
            submitBtn.type = "button";
            submitBtn.onclick = function(e) {
                if (e && typeof e.preventDefault === "function") e.preventDefault();
                if (e && typeof e.stopPropagation === "function") e.stopPropagation();
                handler(e);
                return false;
            };
        }

        const inputs = form.querySelectorAll("input");
        inputs.forEach(inp => {
            inp.addEventListener("keydown", function(e) {
                if (e.key === "Enter") {
                    e.preventDefault();
                    e.stopPropagation();
                    handler(e);
                    return false;
                }
            });
        });
    });
}

async function authenticateUser(role, username, password, targetUrl, selectedDoctorUsername = "") {
    const submitBtn = document.querySelector(".auth-submit-btn");
    const originalContent = submitBtn ? submitBtn.innerHTML : "Sign In";

    if (!username || !password) {
        showToastNotice("Sign-in failed: enter both your practitioner ID and password.", "error");
        return false;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Verifying credentials...`;
    }

    const apiHost = getApiHost();
    let authenticated = false;
    let displayName = username;
    let userObj = null;

    try {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 10000);

        const response = await fetch(`${apiHost}/api/auth/login`, {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                username: username,
                password: password,
                role: role,
                selected_doctor_username: selectedDoctorUsername
            }),
            signal: controller.signal
        });

        clearTimeout(timeoutId);
        const data = await response.json();

        if (response.ok && data.success && data.user) {
            authenticated = true;
            userObj = data.user;
            displayName = data.user.full_name || username;
        } else {
            if (submitBtn) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = originalContent;
            }
            showToastNotice(data.error || "Sign-in failed: invalid credentials. Please verify your details.", "error");
            return false;
        }
    } catch (err) {
        console.warn("Backend API unreachable:", err);
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalContent;
        }
        showToastNotice("Sign-in failed: unable to reach the sign-in service. Please try again shortly.", "error");
        return false;
    }

    if (authenticated) {
        const sessionToken = "ayur_sess_" + Date.now() + "_" + Math.random().toString(36).substring(2, 9);
        let userConstitution = "Pitta-Kapha";
        if (userObj && userObj.details) {
            if (userObj.details.prakriti_primary) {
                userConstitution = userObj.details.prakriti_secondary
                    ? `${userObj.details.prakriti_primary}-${userObj.details.prakriti_secondary}`
                    : userObj.details.prakriti_primary;
            }
        }
        const sessionPayload = {
            role: role,
            username: username,
            fullName: displayName,
            userId: userObj ? userObj.id : 1,
            identifier: userObj ? (userObj.identifier || "") : (role === "patient" ? "ABHA-9182-4410" : ""),
            doctorId: role === "doctor" && userObj?.details?.id ? userObj.details.id : null,
            constitution: userConstitution,
            token: sessionToken,
            loggedInAt: new Date().toISOString()
        };

        safeStorage.setItem("ayurcase_user", JSON.stringify(userObj || { role: role, username: username, full_name: displayName, identifier: sessionPayload.identifier }));
        safeStorage.setItem("ayurcase_session", JSON.stringify(sessionPayload));

        // Persist session into SQLite user_sessions table
        fetch(`${apiHost}/api/auth/session`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                token: sessionToken,
                user_id: userObj ? userObj.id : 1,
                role: role,
                user_data: sessionPayload
            })
        }).catch(() => {});

        try {
            showToastNotice(`Welcome, ${displayName}! Redirecting...`, "success");
        } catch (_) {}

        setTimeout(() => {
            try {
                window.location.replace(targetUrl);
            } catch (_) {
                window.location.href = targetUrl;
            }
        }, 150);
        return false;
    } else {
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalContent;
        }
        showToastNotice("Sign-in failed: invalid credentials. Please verify your details.", "error");
    }
    return false;
}

window.handleDoctorLogin = handleDoctorLogin;
window.handlePatientLogin = handlePatientLogin;
window.handleAdminLogin = handleAdminLogin;
window.handlePatientSignup = handlePatientSignup;
window.generateAbhaId = generateAbhaId;
window.fillDemoSignup = fillDemoSignup;
window.authenticateUser = authenticateUser;
window.checkUrlParamsAndClean = checkUrlParamsAndClean;


/* =====================================================
   4. APPOINTMENT BOOKING & DOCTOR DIRECTORY
   Directly reading and persisting to SQLite
   ===================================================== */

var DEFAULT_DOCTORS = window.DEFAULT_DOCTORS || [
    {
        doctor_id: 1,
        full_name: "Dr. Arindam Sen",
        specialization: "Kayachikitsa (Internal Medicine)",
        qualification: "BAMS, MD (Ayu)",
        status: "Active Online",
        cases_count: 142,
        council_reg_no: "AYUSH-WB-2018-0941",
        phone: "+91 98301 23456",
        username: "dr.sen@ayurcase.com",
        avatar: "AS"
    },
    {
        doctor_id: 2,
        full_name: "Dr. Priyadarshini Rao",
        specialization: "Panchakarma Specialist",
        qualification: "BAMS, MS (Ayu)",
        status: "In Consultation",
        cases_count: 98,
        council_reg_no: "AYUSH-KA-2019-1120",
        phone: "+91 98450 78901",
        username: "dr.rao@ayurcase.com",
        avatar: "PR"
    },
    {
        doctor_id: 3,
        full_name: "Dr. Meera Kapoor",
        specialization: "Dravyaguna & Lifestyle Medicine",
        qualification: "BAMS, MD (Dravyaguna)",
        status: "Active Online",
        cases_count: 116,
        council_reg_no: "AYUSH-DL-2020-1846",
        phone: "+91 98110 45218",
        username: "dr.kapoor@ayurcase.com",
        avatar: "MK"
    },
    {
        doctor_id: 4,
        full_name: "Dr. Kunal Bose",
        specialization: "Shalya Tantra Specialist",
        qualification: "BAMS, MS (Shalya)",
        status: "Active Online",
        cases_count: 87,
        council_reg_no: "AYUSH-WB-2021-0673",
        phone: "+91 99031 67104",
        username: "dr.bose@ayurcase.com",
        avatar: "KB"
    }
];

window.openAppointmentModal = function() {
    const modal = document.getElementById("appointmentModal");
    if (!modal) return;

    modal.style.display = "flex";
    document.body.style.overflow = "hidden";

    const dateInput = document.getElementById("appointmentDate");
    if (dateInput) {
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        dateInput.min = today.toISOString().split("T")[0];
        if (!dateInput.value) {
            dateInput.value = tomorrow.toISOString().split("T")[0];
        }
    }

    loadAvailableDoctors();
};

window.closeAppointmentModal = function() {
    const modal = document.getElementById("appointmentModal");
    if (!modal) return;
    modal.style.display = "none";
    document.body.style.overflow = "auto";
};

window.updateModeChips = function(radio) {
    document.querySelectorAll(".mode-chip").forEach(chip => chip.classList.remove("active"));
    if (radio && radio.parentElement) {
        radio.parentElement.classList.add("active");
    }
};

window.selectDoctor = function(doctorId, doctorName) {
    const nameInput = document.getElementById("selectedDoctorName");
    const idInput = document.getElementById("selectedDoctorId");
    if (nameInput) nameInput.value = doctorName;
    if (idInput) idInput.value = doctorId;

    document.querySelectorAll(".doctor-card-select").forEach(card => {
        if (card.getAttribute("data-doc-id") == doctorId) {
            card.classList.add("selected");
        } else {
            card.classList.remove("selected");
        }
    });
};

async function loadAvailableDoctors() {
    const container = document.getElementById("doctorSelectGrid");
    if (!container) return;

    let doctors = DEFAULT_DOCTORS;

    try {
        const res = await fetch(`${getApiHost()}/api/doctors`);
        const data = await res.json();
        if (data.success && data.doctors && data.doctors.length > 0) {
            const returned = data.doctors;
            const returnedNames = new Set(returned.map(doc => String(doc.full_name || "").toLowerCase()));
            doctors = [...returned, ...DEFAULT_DOCTORS.filter(doc => !returnedNames.has(doc.full_name.toLowerCase()))];
        }
    } catch (e) {
        console.warn("Using offline doctor list fallback:", e);
    }

    const currentDocName = document.getElementById("selectedDoctorName")?.value || "";

    container.innerHTML = doctors.map((doc, idx) => {
        const doctorName = String(doc.full_name || "AYUSH Doctor");
        const doctorId = Number.parseInt(doc.doctor_id, 10);
        const initials = doctorName.replace("Dr. ", "").split(" ").map(w => w[0]).join("").substring(0, 2);
        const isSelected = doctorName === currentDocName;
        return `
            <div class="doctor-card-select ${isSelected ? 'selected' : ''}" 
                 data-doc-id="${Number.isFinite(doctorId) ? doctorId : ''}"
                 data-doc-name="${escapeHtml(doctorName)}"
                 onclick="selectDoctor(this.dataset.docId, this.dataset.docName)">
                <div class="doctor-card-avatar">${escapeHtml(initials)}</div>
                <div class="doctor-card-body">
                    <div class="doctor-card-name">
                        <strong>${escapeHtml(doctorName)}</strong>
                        <span class="doctor-card-status">${escapeHtml(doc.status || 'Available')}</span>
                    </div>
                    <div class="doctor-card-spec">${escapeHtml(doc.specialization || 'AYUSH Practitioner')}</div>
                    <small class="doctor-card-qual">${escapeHtml(doc.qualification || 'AYUSH Practitioner')}</small>
                </div>
                <div class="doctor-card-check">
                    <i class="fa-solid fa-circle-check"></i>
                </div>
            </div>
        `;
    }).join("");
}

function getActivePatientSession() {
    let sess = {};
    let user = {};
    try {
        sess = JSON.parse(safeStorage.getItem("ayurcase_session") || "{}");
    } catch (_) {}
    try {
        user = JSON.parse(safeStorage.getItem("ayurcase_user") || "{}");
    } catch (_) {}

    const fullName = sess.fullName || sess.full_name || sess.name || user.full_name || user.name || "Rohit Sharma";
    const identifier = sess.identifier || user.identifier || user.abha_id || (user.details && user.details.abha_id) || "ABHA-9182-4410";
    const userId = sess.userId || sess.id || user.id || 1;
    let constitution = sess.constitution;
    if (!constitution && user.details && user.details.prakriti_primary) {
        constitution = user.details.prakriti_secondary 
            ? `${user.details.prakriti_primary}-${user.details.prakriti_secondary}`
            : user.details.prakriti_primary;
    }
    if (!constitution) constitution = "Pitta-Kapha";

    return { fullName, identifier, userId, constitution };
}

function getActiveDoctorName() {
    let sess = {};
    let user = {};
    try { sess = JSON.parse(safeStorage.getItem("ayurcase_session") || "{}"); } catch (_) {}
    try { user = JSON.parse(safeStorage.getItem("ayurcase_user") || "{}"); } catch (_) {}

    if (sess.role === "doctor" || user.role === "doctor") {
        return sess.fullName || sess.full_name || user.full_name || user.name || "Dr. Arindam Sen";
    }
    return "Dr. Arindam Sen";
}

function getActiveDoctorId() {
    let sess = {};
    let user = {};
    try { sess = JSON.parse(safeStorage.getItem("ayurcase_session") || "{}"); } catch (_) {}
    try { user = JSON.parse(safeStorage.getItem("ayurcase_user") || "{}"); } catch (_) {}

    if (sess.role !== "doctor" && user.role !== "doctor") return null;
    const doctorId = sess.doctorId || sess.doctor_id || user?.details?.id || user?.details?.doctor_id || sess.userId || sess.id || user.id;
    return doctorId ? String(doctorId) : null;
}

function renderDoctorDashboardProfile() {
    const session = (() => {
        try { return JSON.parse(safeStorage.getItem("ayurcase_session") || "{}"); }
        catch (_) { return {}; }
    })();
    if (session.role !== "doctor") return;

    const user = (() => {
        try { return JSON.parse(safeStorage.getItem("ayurcase_user") || "{}"); }
        catch (_) { return {}; }
    })();
    const details = user.details || {};

    const name = getActiveDoctorName();
    const initials = name.replace(/^Dr\.\s*/i, "").split(" ").filter(Boolean).map(word => word[0]).join("").slice(0, 2).toUpperCase();
    document.querySelectorAll("[data-doctor-name]").forEach(el => { el.textContent = name; });
    document.querySelectorAll("[data-doctor-initials]").forEach(el => { el.textContent = initials; });
    document.querySelectorAll("[data-doctor-specialization]").forEach(el => {
        el.textContent = details.specialization || "AYUSH Practitioner";
    });
    const greeting = document.getElementById("doctorGreeting");
    if (greeting) greeting.innerHTML = `Hello, <span>${escapeHtml(name)}.</span>`;

    renderDoctorAccountDetails({
        full_name: name,
        specialization: details.specialization,
        qualification: details.qualification,
        council_reg_no: details.council_reg_no || user.identifier,
        phone: user.phone,
        username: user.username,
        cases_count: details.cases_count,
        status: details.status,
    });
}

function renderDoctorAccountDetails(doctor) {
    if (!doctor) return;
    const profile = typeof resolveDoctorDirectoryProfile === "function"
        ? resolveDoctorDirectoryProfile(doctor)
        : doctor;
    const setDetail = (id, value, fallback = "—") => {
        const element = document.getElementById(id);
        if (element) element.textContent = value || fallback;
    };
    const dashboardStats = latestDoctorDashboard?.stats || {};
    const caseRecords = profile.cases_count ?? dashboardStats.ai_cases_analyzed;
    const patientsInCare = dashboardStats.total_patients;

    document.querySelectorAll("[data-doctor-specialization]").forEach(element => {
        element.textContent = profile.specialization || "AYUSH Practitioner";
    });
    setDetail("doctorProfileName", profile.full_name, "Practitioner profile");
    setDetail("doctorProfileSpecialization", profile.specialization, "AYUSH Practitioner");
    setDetail("doctorProfileQualification", profile.qualification);
    setDetail("doctorProfileCouncil", profile.council_reg_no || profile.identifier);
    setDetail("doctorProfilePhone", profile.phone);
    setDetail("doctorProfileEmail", profile.username || profile.email);
    setDetail("doctorProfilePatients", patientsInCare, "0");
    setDetail("doctorProfileCases", caseRecords, "0");
    setDetail("doctorProfileAvailability", profile.status, "Available");
    setDetail("doctorProfileStatus", profile.status, "Active");
}

function renderPatientProfile() {
    const session = getActivePatientSession();
    const fullName = session.fullName;
    const identifier = session.identifier;
    const constitution = session.constitution;

    // Sidebar initials
    const avatarEl = document.getElementById("patientSidebarAvatar");
    if (avatarEl) {
        const initials = fullName.split(" ").filter(Boolean).map(w => w[0]).join("").substring(0, 2).toUpperCase();
        avatarEl.textContent = initials || "PT";
    }

    // Sidebar full name
    const nameEl = document.getElementById("patientSidebarName");
    if (nameEl) {
        nameEl.textContent = fullName;
    }

    // Sidebar ABHA identifier
    const abhaEl = document.getElementById("patientSidebarAbha");
    if (abhaEl) {
        abhaEl.textContent = identifier;
    }

    // Welcome banner greeting
    const welcomeEl = document.getElementById("patientWelcomeName");
    if (welcomeEl) {
        welcomeEl.textContent = `Namaste, ${fullName}`;
    }

    // Constitution badge
    const constBadge = document.getElementById("patientConstitutionBadge");
    if (constBadge) {
        constBadge.innerHTML = `<i class="fa-solid fa-spa"></i> ${constitution}`;
    }

    // Prakriti score card if present
    const prakritiScoreEl = document.getElementById("patientPrakritiScore");
    if (prakritiScoreEl) {
        prakritiScoreEl.textContent = constitution;
    }
}

window.handleAppointmentBooking = async function(event) {
    if (event) event.preventDefault();

    const submitBtn = document.getElementById("submitAppointmentBtn");
    const originalText = submitBtn ? submitBtn.innerHTML : "Confirm & Schedule";

    const doctorName = document.getElementById("selectedDoctorName")?.value.trim() || "";
    const doctorId = document.getElementById("selectedDoctorId")?.value || "";
    const appointmentDate = document.getElementById("appointmentDate")?.value;
    const appointmentTime = document.getElementById("appointmentTime")?.value || "11:30 AM";
    const consultationType = document.querySelector('input[name="consultation_type"]:checked')?.value || "In-Clinic Consultation";
    const notes = document.getElementById("appointmentNotes")?.value.trim() || "";

    const session = getActivePatientSession();
    const patientName = session.fullName || "Rohit Sharma";
    const patientId = session.userId || 1;

    if (!appointmentDate) {
        showToastNotice("Booking failed: please select an appointment date.", "error");
        return false;
    }

    if (!doctorName || !doctorId) {
        showToastNotice("Booking failed: please select an attending doctor.", "error");
        return false;
    }

    if (!notes) {
        showToastNotice("Booking failed: please describe the reason for your visit.", "error");
        return false;
    }

    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Scheduling...`;
    }

    const newAppointment = {
        patient_name: patientName,
        doctor_name: doctorName,
        appointment_date: appointmentDate,
        appointment_time: appointmentTime,
        consultation_type: consultationType,
        symptoms_notes: notes,
        patient_id: patientId,
        doctor_id: parseInt(doctorId),
        status: "Confirmed",
        created_at: new Date().toISOString()
    };

    try {
        const res = await fetch(`${getApiHost()}/api/appointments`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(newAppointment)
        });
        const data = await res.json();
        if (res.ok && data.success) {
            newAppointment.id = data.appointment?.id || Date.now();
        } else {
            throw new Error(data.error || "The appointment could not be saved.");
        }
    } catch (e) {
        console.warn("Appointment booking failed:", e);
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.innerHTML = originalText;
        }
        showToastNotice("Booking failed: unable to confirm the appointment. Please try again.", "error");
        return false;
    }

    safeStorage.setItem("ayurcase_appointments_updated", Date.now().toString());

    if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalText;
    }

    closeAppointmentModal();
    const form = document.getElementById("appointmentForm");
    if (form) form.reset();

    showToastNotice(`Appointment confirmed with ${doctorName} on ${formatDisplayDate(appointmentDate)}!`);

    loadPatientAppointments();
    loadDoctorAppointments();
    return false;
};

function formatDisplayDate(dateStr) {
    if (!dateStr) return "";
    try {
        const parts = dateStr.split("-");
        if (parts.length === 3) {
            const months = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"];
            const year = parts[0];
            const monthIndex = parseInt(parts[1], 10) - 1;
            const day = parts[2];
            return `${day} ${months[monthIndex] || parts[1]} ${year}`;
        }
    } catch (_) {}
    return dateStr;
}


/* =====================================================
   5. CROSS-DASHBOARD DATABASE APPOINTMENT LOADING
   Directly reads from SQLite appointments table
   ===================================================== */

async function loadPatientAppointments() {
    const tableBody = document.getElementById("patientAppointmentsTableBody") || document.getElementById("patientAppointmentsBody");
    if (!tableBody) return;

    const session = getActivePatientSession();
    const currentName = (session.fullName || "").trim().toLowerCase();
    const currentId = session.userId;

    let appointments = [];

    try {
        const res = await fetch(`${getApiHost()}/api/appointments`);
        const data = await res.json();
        if (data.success && Array.isArray(data.appointments)) {
            appointments = data.appointments;
        }
    } catch (e) {
        console.warn("Using offline cached appointments:", e);
    }

    const patientApts = appointments.filter(a => {
        const aName = (a.patient_name || "").trim().toLowerCase();
        if (aName && currentName && (aName === currentName || aName.includes(currentName) || currentName.includes(aName))) {
            return true;
        }
        if (currentId && a.patient_id && Number(a.patient_id) === Number(currentId)) {
            return true;
        }
        if ((currentName.includes("rohit") || currentName.includes("rahul")) && 
            (a.patient_id === 1 || aName.includes("rohit") || aName.includes("rahul"))) {
            return true;
        }
        return false;
    });

    // Update Follow-up stat card if elements exist
    const nextStat = document.getElementById("patientNextAppointmentStat");
    const nextStatSub = document.getElementById("patientNextAppointmentStatSub");
    if (nextStat) {
        if (patientApts.length > 0) {
            const nextApt = patientApts[0];
            nextStat.textContent = formatDisplayDate(nextApt.appointment_date);
            if (nextStatSub) {
                nextStatSub.textContent = `${nextApt.appointment_time} • ${nextApt.doctor_name || "Doctor"}`;
            }
        } else {
            nextStat.textContent = "None Scheduled";
            if (nextStatSub) {
                nextStatSub.textContent = "Book your consultation";
            }
        }
    }

    if (patientApts.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="5" style="text-align: center; padding: 32px 16px; color: var(--muted);">
                    <i class="fa-regular fa-calendar-xmark" style="font-size: 28px; display: block; margin-bottom: 10px; opacity: 0.6; color: var(--green-700);"></i>
                    <strong style="display: block; font-size: 14px; margin-bottom: 4px; color: var(--text);">No Scheduled Consultations</strong>
                    <span style="display: block; font-size: 12px; margin-bottom: 14px; color: var(--muted);">You don't have any upcoming consultations with AYUSH doctors yet.</span>
                    <button class="primary-btn" onclick="openAppointmentModal()" style="padding: 9px 18px; font-size: 12px; border-radius: 8px; display: inline-flex; align-items: center; gap: 6px; margin: 0 auto; cursor: pointer;">
                        <i class="fa-solid fa-calendar-plus"></i>
                        <span>Book Consultation Now</span>
                    </button>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = patientApts.map(apt => {
        const isTele = (apt.consultation_type || "").includes("Tele");
        const docInitials = (apt.doctor_name || "Dr. Arindam Sen").replace("Dr. ", "").split(" ").map(w => w[0]).join("");
        return `
            <tr style="border-bottom: 1px solid var(--border);">
                <td style="padding: 12px; font-weight: 600;">
                    <div style="display: flex; align-items: center; gap: 8px;">
                        <div class="doctor-avatar small" style="width: 28px; height: 28px; font-size: 11px; background: linear-gradient(135deg, #2d7350, #1b4b34); border-radius: 50%; color: white; display: flex; align-items: center; justify-content: center; font-weight: 700;">
                            ${escapeHtml(docInitials)}
                        </div>
                        <span>${escapeHtml(apt.doctor_name || "Dr. Arindam Sen")}</span>
                    </div>
                </td>
                <td style="padding: 12px; color: var(--text);">
                    <div style="font-weight: 600;">${escapeHtml(formatDisplayDate(apt.appointment_date))}</div>
                    <small style="color: var(--muted);">${escapeHtml(apt.appointment_time)}</small>
                </td>
                <td style="padding: 12px;">
                    <span class="mode-badge ${isTele ? 'tele' : 'clinic'}" style="display: inline-flex; align-items: center; gap: 5px; font-size: 11px; padding: 4px 10px; border-radius: 12px; background: ${isTele ? '#e8f0fe' : '#eaf4ee'}; color: ${isTele ? '#1a73e8' : '#236142'}; font-weight: 600;">
                        <i class="fa-solid ${isTele ? 'fa-video' : 'fa-hospital-user'}"></i>
                        ${escapeHtml(apt.consultation_type || 'In-Clinic')}
                    </span>
                </td>
                <td style="padding: 12px; color: var(--muted); max-width: 260px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;">
                    ${escapeHtml(apt.symptoms_notes || 'Consultation follow-up')}
                </td>
                <td style="padding: 12px;">
                    <span class="status-badge-confirmed" style="background: #eaf7ee; color: #1e6b37; border: 1px solid #bde3c7; font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; display: inline-flex; align-items: center; gap: 5px;">
                        <i class="fa-solid fa-circle-check"></i> ${escapeHtml(apt.status || 'Confirmed')}
                    </span>
                </td>
            </tr>
        `;
    }).join("");
}

let latestDoctorDashboard = null;

async function fetchDoctorDashboard() {
    const doctorId = getActiveDoctorId();
    if (!doctorId) throw new Error("No active practitioner account.");

    const query = new URLSearchParams({ doctor_id: doctorId });
    try {
        const response = await fetch(`${getApiHost()}/api/doctor-dashboard?${query}`, { cache: "no-store" });
        const data = await response.json();
        if (!response.ok || !data.success || !data.dashboard) {
            throw new Error(data.error || "Unable to load practitioner dashboard data.");
        }
        return data.dashboard;
    } catch (primaryError) {
        // A dashboard page should still work while a deployment is catching up
        // with the consolidated endpoint. These two scoped APIs also power Case
        // History and appointment booking, so they are a reliable live fallback.
        console.warn("Using practitioner dashboard fallback:", primaryError);
        return fetchDoctorDashboardFallback(doctorId, primaryError);
    }
}

function getDoctorToday() {
    return new Date().toISOString().slice(0, 10);
}

function toRecentPatient(record) {
    const patientName = String(record?.patient_name || record?.name || "").trim();
    if (!patientName) return null;

    return {
        patient_name: patientName,
        last_activity: String(record.last_activity || record.created_at || record.case_date || record.date || record.appointment_date || ""),
        detail: String(record.detail || record.complaint || record.chief_complaint || record.symptoms_notes || record.diagnosis || record.consultation_type || "Clinical record updated."),
        status: String(record.status || "Active"),
    };
}

function mergeRecentPatients(...collections) {
    const byPatient = new Map();
    collections.flat().forEach(record => {
        const patient = toRecentPatient(record);
        if (!patient) return;
        const key = patient.patient_name.toLocaleLowerCase();
        const current = byPatient.get(key);
        if (!current || patient.last_activity > current.last_activity) {
            byPatient.set(key, patient);
        }
    });

    return [...byPatient.values()].sort((left, right) =>
        String(right.last_activity).localeCompare(String(left.last_activity))
    );
}

async function fetchDoctorCaseRecords(doctorId = getActiveDoctorId()) {
    if (!doctorId) return [];
    const query = new URLSearchParams({ doctor_id: doctorId });
    const response = await fetch(`${getApiHost()}/api/cases?${query}`, { cache: "no-store" });
    const data = await response.json();
    if (!response.ok || !data.success || !Array.isArray(data.cases)) {
        throw new Error(data.error || "Unable to load practitioner case records.");
    }
    return data.cases;
}

async function fetchDoctorDashboardFallback(doctorId, primaryError) {
    const query = new URLSearchParams({ doctor_id: doctorId });
    const [appointmentsResult, casesResult] = await Promise.allSettled([
        fetch(`${getApiHost()}/api/appointments?${query}`, { cache: "no-store" })
            .then(async response => {
                const data = await response.json();
                if (!response.ok || !data.success || !Array.isArray(data.appointments)) {
                    throw new Error(data.error || "Unable to load practitioner appointments.");
                }
                return data.appointments;
            }),
        fetchDoctorCaseRecords(doctorId),
    ]);

    if (appointmentsResult.status === "rejected" && casesResult.status === "rejected") {
        throw primaryError;
    }

    const appointments = appointmentsResult.status === "fulfilled" ? appointmentsResult.value : [];
    const cases = casesResult.status === "fulfilled" ? casesResult.value : [];
    const today = getDoctorToday();
    const followUps = appointments.filter(appointment =>
        String(appointment.appointment_date || "") >= today
        && !["cancelled", "completed"].includes(String(appointment.status || "").toLowerCase())
    );
    const patientNames = new Set(
        [...appointments, ...cases]
            .map(record => record.patient_name || record.name)
            .filter(Boolean)
            .map(name => String(name).trim().toLocaleLowerCase())
    );
    const todaysCases = appointments.filter(appointment => appointment.appointment_date === today).length
        + cases.filter(record => String(record.case_date || record.date || record.created_at || "").startsWith(today)).length;

    return {
        doctor: { full_name: getActiveDoctorName() },
        stats: {
            total_patients: patientNames.size,
            todays_cases: todaysCases,
            follow_ups: followUps.length,
            ai_cases_analyzed: cases.length,
        },
        follow_ups: followUps,
        recent_patients: mergeRecentPatients(appointments, cases),
    };
}

function doctorInitials(name) {
    return String(name || "Patient")
        .replace(/^Dr\.\s*/i, "")
        .split(" ")
        .filter(Boolean)
        .map(word => word[0])
        .join("")
        .slice(0, 2)
        .toUpperCase();
}

function doctorEmptyState(message, icon = "fa-calendar-xmark") {
    return `
        <div class="doctor-activity-empty">
            <i class="fa-regular ${icon}"></i>
            ${escapeHtml(message)}
        </div>
    `;
}

function renderDoctorStats(stats) {
    const setText = (id, value) => {
        const element = document.getElementById(id);
        if (element) element.textContent = String(value);
    };
    setText("doctorTotalPatients", stats.total_patients || 0);
    setText("doctorTodayCases", stats.todays_cases || 0);
    setText("doctorFollowUpsStat", stats.follow_ups || 0);
    setText("doctorAiCases", stats.ai_cases_analyzed || 0);
    setText("doctorTotalPatientsSub", `${stats.total_patients || 0} unique patient${stats.total_patients === 1 ? "" : "s"} in your care`);
    setText("doctorTodayCasesSub", `${stats.todays_cases || 0} appointment${stats.todays_cases === 1 ? "" : "s"} or cases today`);
    setText("doctorFollowUpsSub", `${stats.follow_ups || 0} upcoming confirmed consultation${stats.follow_ups === 1 ? "" : "s"}`);
    setText("doctorAiCasesSub", `${stats.ai_cases_analyzed || 0} clinical record${stats.ai_cases_analyzed === 1 ? "" : "s"} available`);
}

function renderDoctorFollowUps(appointments) {
    const container = document.getElementById("doctorAppointmentsList");
    if (!container) return;
    if (!appointments.length) {
        container.innerHTML = doctorEmptyState("No upcoming follow-up visits. New patient bookings will appear here.");
        return;
    }

    container.innerHTML = appointments.slice(0, 4).map((appointment, index) => `
        <div class="patient-row">
            <div class="patient-avatar avatar-${(index % 4) + 1}">${escapeHtml(doctorInitials(appointment.patient_name))}</div>
            <div class="patient-info">
                <strong>${escapeHtml(appointment.patient_name)}</strong>
                <span>${escapeHtml(formatDisplayDate(appointment.appointment_date))} • ${escapeHtml(appointment.appointment_time || "Time to be confirmed")}</span>
            </div>
            <div class="patient-complaint">
                <span>Reason for visit</span>
                <strong>${escapeHtml(appointment.symptoms_notes || appointment.consultation_type || "Follow-up consultation")}</strong>
            </div>
            <span class="status Active-status">${escapeHtml(appointment.status || "Confirmed")}</span>
            <i class="fa-solid fa-chevron-right more-btn" aria-hidden="true"></i>
        </div>
    `).join("");
}

const RECENT_PATIENT_DEMOS = [
    {
        patient_name: "Aditi Sen",
        detail: "Demo profile — follow-up after a 7-day sleep and digestion routine; morning energy is improving.",
        status: "Follow-up",
        last_activity: "Demo activity",
        is_demo: true,
    },
    {
        patient_name: "Nikhil Banerjee",
        detail: "Demo profile — dietary review completed for post-meal heaviness; a gentle Agni-support plan was discussed.",
        status: "Review",
        last_activity: "Demo activity",
        is_demo: true,
    },
    {
        patient_name: "Rhea Mukherjee",
        detail: "Demo profile — tele-consultation request logged for skin sensitivity and stress-related sleep disruption.",
        status: "New",
        last_activity: "Demo activity",
        is_demo: true,
    },
];

function resolveDoctorDirectoryProfile(doctor = {}) {
    const activeDoctorId = typeof getActiveDoctorId === "function" ? getActiveDoctorId() : null;
    const requestedId = String(doctor.doctor_id || doctor.id || activeDoctorId || "");
    const requestedName = String(doctor.full_name || getActiveDoctorName?.() || "").toLowerCase();
    const defaultProfile = DEFAULT_DOCTORS.find(candidate =>
        String(candidate.doctor_id) === requestedId ||
        String(candidate.full_name).toLowerCase() === requestedName
    ) || {};

    const merged = { ...defaultProfile };
    Object.entries(doctor).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") merged[key] = value;
    });
    return merged;
}

function formatRecentActivity(activity, isDemo) {
    if (isDemo) return "Sample activity";
    if (!activity) return "Recent activity";
    const parsed = new Date(activity);
    if (!Number.isNaN(parsed.getTime())) {
        return `Updated ${parsed.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`;
    }
    return `Updated ${activity}`;
}

function renderRecentPatients(patients = []) {
    const container = document.getElementById("doctorRecentPatientsList");
    if (!container) return;

    const livePatients = mergeRecentPatients(Array.isArray(patients) ? patients : [])
        .map(patient => ({ ...patient, is_demo: false }));
    const liveNames = new Set(livePatients.map(patient => patient.patient_name.toLocaleLowerCase()));
    const demos = RECENT_PATIENT_DEMOS.filter(patient => !liveNames.has(patient.patient_name.toLocaleLowerCase()));
    const visiblePatients = [...livePatients, ...demos].slice(0, 4);

    container.innerHTML = visiblePatients.map((patient, index) => `
        <article class="recent-patient-card ${patient.is_demo ? "is-demo" : ""}">
            <div class="recent-patient-heading">
                <div class="patient-avatar avatar-${(index % 4) + 1}">${escapeHtml(doctorInitials(patient.patient_name))}</div>
                <div>
                    <strong>${escapeHtml(patient.patient_name)}</strong>
                    <span>${patient.is_demo ? "Demo patient profile" : "Patient in your care"}</span>
                </div>
                <span class="status ${String(patient.status || "").toLowerCase().includes("follow") ? "Follow-up-status" : "Active-status"}">${escapeHtml(patient.status || "Active")}</span>
            </div>
            <p>${escapeHtml(patient.detail || "Clinical record updated.")}</p>
            <div class="recent-patient-meta">
                <span><i class="fa-regular fa-clock"></i>${escapeHtml(formatRecentActivity(patient.last_activity, patient.is_demo))}</span>
                <span><i class="fa-solid fa-notes-medical"></i>${patient.is_demo ? "Demo record only" : "Live clinical activity"}</span>
            </div>
        </article>
    `).join("");
}

async function loadDoctorAppointments() {
    const followUpContainer = document.getElementById("doctorAppointmentsList");
    const recentContainer = document.getElementById("doctorRecentPatientsList");
    if (!followUpContainer && !recentContainer) return;

    // Do not leave the panel blank while the live records are loading.
    renderRecentPatients();

    try {
        latestDoctorDashboard = await fetchDoctorDashboard();
        let caseRecords = [];
        try {
            caseRecords = await fetchDoctorCaseRecords();
        } catch (caseError) {
            console.warn("Unable to supplement recent patients from case history:", caseError);
        }
        renderDoctorStats(latestDoctorDashboard.stats || {});
        renderDoctorFollowUps(latestDoctorDashboard.follow_ups || []);
        // Cases and appointments are merged by patient name. This guarantees a
        // patient shown in Case History also appears in Recent Patients.
        renderRecentPatients(mergeRecentPatients(latestDoctorDashboard.recent_patients || [], caseRecords));
        renderDoctorAccountDetails(latestDoctorDashboard.doctor);
    } catch (error) {
        console.warn("Unable to load practitioner dashboard:", error);
        if (followUpContainer) {
            followUpContainer.innerHTML = doctorEmptyState("Follow-up visits could not be loaded. Please refresh and try again.");
        }
        // The labelled samples remain visible instead of an empty panel when
        // the server is temporarily unavailable.
        if (recentContainer) renderRecentPatients();
    }
}

function renderFollowUpsModal(appointments) {
    const container = document.getElementById("doctorFollowUpsModalList");
    if (!container) return;
    container.innerHTML = appointments.length ? appointments.map(appointment => `
        <article class="follow-up-modal-item">
            <div class="date-box">
                <strong>${escapeHtml((appointment.appointment_date || "").split("-")[2] || "—")}</strong>
                <span>${escapeHtml(formatDisplayDate(appointment.appointment_date || "").split(" ")[1] || "DATE")}</span>
            </div>
            <div>
                <strong>${escapeHtml(appointment.patient_name)}</strong>
                <span>${escapeHtml(appointment.appointment_time || "Time to be confirmed")} · ${escapeHtml(appointment.consultation_type || "Consultation")}</span>
                <p>${escapeHtml(appointment.symptoms_notes || "Follow-up consultation")}</p>
            </div>
            <span class="status Active-status">${escapeHtml(appointment.status || "Confirmed")}</span>
        </article>
    `).join("") : doctorEmptyState("No upcoming follow-up visits. New bookings with you will appear here.");
}

window.openDoctorFollowUps = async function(event) {
    if (event) event.preventDefault();
    const modal = document.getElementById("doctorFollowUpsModal");
    const intro = document.getElementById("doctorFollowUpsIntro");
    const container = document.getElementById("doctorFollowUpsModalList");
    if (!modal || !container) return;

    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    document.body.style.overflow = "hidden";
    if (intro) intro.textContent = "Loading your confirmed follow-up visits…";
    container.innerHTML = doctorEmptyState("Loading visits…", "fa-calendar-days");

    try {
        const dashboard = await fetchDoctorDashboard();
        latestDoctorDashboard = dashboard;
        const appointments = dashboard.follow_ups || [];
        if (intro) {
            intro.textContent = `${appointments.length} confirmed follow-up visit${appointments.length === 1 ? "" : "s"} for ${dashboard.doctor?.full_name || "this practitioner"}.`;
        }
        renderFollowUpsModal(appointments);
    } catch (error) {
        if (intro) intro.textContent = "We could not load follow-up visits right now.";
        container.innerHTML = doctorEmptyState(error.message || "Please refresh and try again.");
    }
};

window.closeDoctorFollowUps = function() {
    const modal = document.getElementById("doctorFollowUpsModal");
    if (!modal) return;
    modal.classList.remove("show");
    modal.setAttribute("aria-hidden", "true");
    document.body.style.overflow = "";
};

function initDoctorFollowUpsModal() {
    const modal = document.getElementById("doctorFollowUpsModal");
    const closeButton = document.getElementById("closeDoctorFollowUpsModal");
    if (!modal || !closeButton) return;
    closeButton.addEventListener("click", window.closeDoctorFollowUps);
    modal.addEventListener("click", event => {
        if (event.target === modal) window.closeDoctorFollowUps();
    });
}

function initDoctorAccountMenu() {
    const trigger = document.getElementById("doctorProfileTrigger");
    const menu = document.getElementById("doctorAccountMenu");
    const logoutButton = document.getElementById("doctorLogoutButton");
    if (!trigger || !menu || !logoutButton) return;

    const closeMenu = () => {
        menu.hidden = true;
        trigger.setAttribute("aria-expanded", "false");
    };
    trigger.addEventListener("click", event => {
        event.stopPropagation();
        const willOpen = menu.hidden;
        menu.hidden = !willOpen;
        trigger.setAttribute("aria-expanded", String(willOpen));
    });
    trigger.addEventListener("keydown", event => {
        if (event.key === "Escape") closeMenu();
    });
    document.addEventListener("click", event => {
        if (!menu.hidden && !menu.contains(event.target) && !trigger.contains(event.target)) closeMenu();
    });
    logoutButton.addEventListener("click", window.logoutDoctor);
}

window.logoutDoctor = async function() {
    let session = {};
    try { session = JSON.parse(safeStorage.getItem("ayurcase_session") || "{}"); } catch (_) {}

    try {
        await fetch(`${getApiHost()}/api/auth/logout`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ token: session.token || "" })
        });
    } catch (_) {
        // Local session data is still cleared when the network is unavailable.
    }

    safeStorage.removeItem("ayurcase_session");
    safeStorage.removeItem("ayurcase_user");
    window.location.replace("login-doctor.html");
};


/* =====================================================
   6. TOAST NOTIFICATION HELPER
   ===================================================== */

function showToastNotice(message, type = "success") {
    let toast = document.getElementById("toast");
    let toastMessage = document.getElementById("toastMessage");

    if (!toast) {
        toast = document.createElement("div");
        toast.id = "toast";
        toast.className = "toast";
        toast.innerHTML = `
            <div class="toast-icon">
                <i class="fa-solid fa-circle-check"></i>
            </div>
            <div>
                <strong>AYURCASE</strong>
                <span id="toastMessage"></span>
            </div>
        `;
        document.body.appendChild(toast);
        toastMessage = document.getElementById("toastMessage");
    }
    if (toastMessage) {
        toastMessage.textContent = message;
    }

    toast.classList.toggle("toast-error", type === "error");
    const toastTitle = toast.querySelector("strong");
    const toastIcon = toast.querySelector(".toast-icon i");
    if (toastTitle) toastTitle.textContent = type === "error" ? "Failed" : "Success";
    if (toastIcon) toastIcon.className = type === "error" ? "fa-solid fa-circle-xmark" : "fa-solid fa-circle-check";

    toast.classList.add("show");
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3500);
}


/* =====================================================
   7. INITIALIZATION
   ===================================================== */

function initApp() {
    initTheme();
    initPasswordToggles();
    initLoginForms();
    initDatabaseStorage();
    renderPatientProfile();
    renderDoctorDashboardProfile();
    initDoctorAccountMenu();
    initDoctorFollowUpsModal();
    loadPatientAppointments();
    loadDoctorAppointments();
}

window.getActivePatientSession = getActivePatientSession;
window.renderPatientProfile = renderPatientProfile;
window.renderDoctorDashboardProfile = renderDoctorDashboardProfile;
window.loadPatientAppointments = loadPatientAppointments;

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initApp);
} else {
    initApp();
}
