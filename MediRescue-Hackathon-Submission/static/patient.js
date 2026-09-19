"use strict";

/* ================================
   BACKEND CONFIGURATION
================================ */

const USE_LOCAL_BACKEND = true;

const API_BASE = window.location.origin;


/* ================================
   GLOBAL VARIABLES
================================ */

let emergencyId = null;
let timerInterval = null;
let timer = null;
let pollTimer = null;
let countdown = 5;
let signupMode = false;
let patientMap = null;
let patientMarker = null;
let pollingInterval = null;
let currentGPS = null;
let pmap = null;
let pPatient = null;
let pHospital = null;
let pAmbulance = null;
let patientGpsWatchId = null;

/* ================================
   HELPER FUNCTIONS
================================ */

function $(id) {
  return document.getElementById(id);
}

function apiUrl(path) {
  return API_BASE + path;
}

function showMessage(message) {
  alert(message);
}

function safeValue(value, fallback = "") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }

  return String(value);
}

async function readJsonResponse(response) {
  const raw = await response.text();

  if (!raw) {
    return {};
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    return {
      message: raw
    };
  }
}

async function apiFetch(path, options = {}) {
  const response = await fetch(apiUrl(path), {
    credentials: "include",
    ...options
  });

  const result = await readJsonResponse(response);

  if (!response.ok) {
    throw new Error(
      result.message ||
      result.error ||
      `API Error: ${response.status}`
    );
  }

  return result;
}
async function sendPatientLocation(gps) {
  if (!emergencyId) return;

  try {
    const response = await apiFetch(
      "/api/emergency/" + emergencyId + "/patient-location",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(gps)
      }
    );

    const data = response;
    console.log("Patient location sent:", data);
  } catch (error) {
    console.error("Patient location upload error:", error);
  }
}


/* ================================
   AUTH MODAL
================================ */

function openAuth() {
  const auth = $("auth");

  if (auth) {
    auth.classList.remove("hidden");
  }
}

function closeAuth() {
  const auth = $("auth");

  if (auth) {
    auth.classList.add("hidden");
  }
}

function toggleSignup() {
  signupMode = !signupMode;

  const title = $("authTitle");
  const fields = $("authFields");

  if (!fields) return;

  if (title) {
    title.textContent = signupMode
      ? "Create Account"
      : "Login";
  }

  if (signupMode) {
    fields.innerHTML = `
      <input
        id="aName"
        type="text"
        placeholder="Full name"
        required
      >

      <input
        id="aPhone"
        type="tel"
        placeholder="Phone"
        required
      >

      <input
        id="aPass"
        type="password"
        placeholder="Password"
        autocomplete="new-password"
        required
      >

      <input
        id="aAge"
        type="number"
        min="1"
        max="120"
        placeholder="Age"
        required
      >

      <input
        id="aBlood"
        type="text"
        placeholder="Blood group"
        required
      >

      <input
        id="aAddress"
        type="text"
        placeholder="Registered address"
        required
      >

      <input
        id="cName"
        type="text"
        placeholder="Emergency contact name"
        required
      >

      <input
        id="cPhone"
        type="tel"
        placeholder="Emergency contact number"
        required
      >

      <input
        id="cRel"
        type="text"
        placeholder="Relationship"
        required
      >
    `;
  } else {
    fields.innerHTML = `
      <input
        id="aPhone"
        type="tel"
        placeholder="Phone"
        autocomplete="username"
        required
      >

      <input
        id="aPass"
        type="password"
        placeholder="Password"
        autocomplete="current-password"
        required
      >
    `;
  }
}


/* ================================
   LOGIN / SIGNUP
================================ */

async function submitAuth() {
  try {
    const phoneInput = $("aPhone");
    const passwordInput = $("aPass");

    if (!phoneInput || !passwordInput) {
      throw new Error("Login fields not found.");
    }

    const phone = phoneInput.value.trim();
    const password = passwordInput.value;

    if (!phone || !password) {
      throw new Error("Phone and password are required.");
    }

    let endpoint = "/api/login";

    let data = {
      phone,
      password
    };

    if (signupMode) {
      endpoint = "/api/signup";

      const name = $("aName")?.value.trim();
      const age = $("aAge")?.value;
      const bloodGroup = $("aBlood")?.value.trim();
      const address = $("aAddress")?.value.trim();
      const contactName = $("cName")?.value.trim();
      const contactPhone = $("cPhone")?.value.trim();
      const relationship = $("cRel")?.value.trim();

      if (
        !name ||
        !age ||
        !bloodGroup ||
        !address ||
        !contactName ||
        !contactPhone ||
        !relationship
      ) {
        throw new Error("Please fill all registration fields.");
      }

      data = {
        name,
        phone,
        password,
        age: Number(age),
        blood_group: bloodGroup,
        address,
        contact_name: contactName,
        contact_phone: contactPhone,
        relationship
      };
    }

    const result = await apiFetch(endpoint, {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify(data)
    });

    showMessage(
      result.message ||
      result.error ||
      "Request completed successfully."
    );

    if (result.success) {
      closeAuth();
    }
  } catch (error) {
    console.error("Authentication error:", error);

    showMessage(
      error.message ||
      "Login/Signup failed. Please try again."
    );
  }
}


/* ================================
   GPS FUNCTIONS
================================ */

function getPosition(options = {}) {
  return new Promise((resolve, reject) => {
    if (!("geolocation" in navigator)) {
      reject({
        code: 0,
        message: "This browser does not support GPS."
      });

      return;
    }

    navigator.geolocation.getCurrentPosition(
      resolve,
      reject,
      options
    );
  });
}

async function getGPSLocation() {
  const localHostnames = [
    "localhost",
    "127.0.0.1",
    "::1"
  ];

  const isLocal =
    localHostnames.includes(location.hostname);

  if (!window.isSecureContext && !isLocal) {
    throw new Error(
      "Phone GPS needs HTTPS. Open the website using HTTPS or localhost."
    );
  }

  try {
    const position = await getPosition({
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0
    });

    return {
      latitude: position.coords.latitude,
      longitude: position.coords.longitude,
      accuracy: position.coords.accuracy
    };
  } catch (firstError) {
    try {
      const position = await getPosition({
        enableHighAccuracy: false,
        timeout: 20000,
        maximumAge: 30000
      });

      return {
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy
      };
    } catch (secondError) {
      if (secondError.code === 1) {
        throw new Error(
          "Location permission denied. Please allow location permission."
        );
      }

      if (secondError.code === 2) {
        throw new Error(
          "Location unavailable. Turn ON GPS/Location and retry."
        );
      }

      if (secondError.code === 3) {
        throw new Error(
          "GPS timed out. Move to an open area and retry."
        );
      }

      throw new Error(
        "Location could not be obtained."
      );
    }
  }
}


function startPatientLiveGPS() {
  if (!navigator.geolocation) {
    $("locationText").textContent =
      "This browser does not support GPS.";
    return;
  }

  console.log("Patient live GPS started");

  patientGpsWatchId = navigator.geolocation.watchPosition(
    function (position) {
      const gps = {
        latitude: Number(position.coords.latitude),
        longitude: Number(position.coords.longitude),
        accuracy: Number(position.coords.accuracy || 0)
      };

      currentGPS = gps;

      console.log("LIVE PATIENT GPS:", gps);

      setLocationUI(gps);

      if (emergencyId) {
        sendPatientLocation(gps);
      }
    },
    function (error) {
      console.error("LIVE GPS ERROR:", error);

      $("locationStatus").className = "loc-status bad";
      $("locationText").textContent = gpsError(error);
    },
    {
      enableHighAccuracy: true,
      maximumAge: 0,
      timeout: 30000
    }
  );
}

function stopPatientLiveGPS() {
  if (patientGpsWatchId !== null) {
    navigator.geolocation.clearWatch(patientGpsWatchId);
    patientGpsWatchId = null;
  }
}

function stopPatientLiveGPS() {
  if (patientGpsWatchId !== null) {
    navigator.geolocation.clearWatch(patientGpsWatchId);
    patientGpsWatchId = null;
  }
}

// Page open hote hi GPS start
window.addEventListener("load", function () {
  startPatientLiveGPS();
});

function stopPatientLiveGPS() {
  if (patientGpsWatchId !== null) {
    navigator.geolocation.clearWatch(patientGpsWatchId);
    patientGpsWatchId = null;
  }
}

function updatePatientOwnMarker(latitude, longitude) {
  initPatientMap();

  if (!patientMap) return;

  const point = [
    Number(latitude),
    Number(longitude)
  ];

  if (!patientMarker) {
    patientMarker = L.marker(point)
      .addTo(patientMap)
      .bindPopup("👤 Your live location");
  } else {
    patientMarker.setLatLng(point);
  }

  patientMap.setView(point, 15);
}


/* ================================
   START SOS
================================ */

async function startSOS() {
  const button = document.getElementById("sos");

  if (!button) {
    alert("SOS button HTML mein nahi mila.");
    return;
  }

  const oldText = button.innerHTML;

  button.disabled = true;
  button.innerHTML = "📍<span>LOCATING...</span>";

  try {
    const position = await getGPSLocation();

    console.log("GPS location:", position);
    console.log("SOS API URL:", API_BASE + "/api/sos/start");

    const response = await fetch(
      API_BASE + "/api/sos/start",
      {
        method: "POST",
        mode: "cors",
        credentials: "include",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(position)
      }
    );

    const rawResponse = await response.text();

    console.log("SOS HTTP status:", response.status);
    console.log("SOS raw response:", rawResponse);

    let result = {};

    try {
      result = JSON.parse(rawResponse);
    } catch (error) {
      result = {
        message: rawResponse
      };
    }

    if (!response.ok) {
      throw new Error(
        result.message ||
        result.error ||
        `Backend error: HTTP ${response.status}`
      );
    }

    if (!result.success) {
      throw new Error(
        result.message ||
        result.error ||
        "Emergency start nahi hua."
      );
    }

   emergencyId =
  result.emergency_id ||
  result.id ||
  result.emergency?.id;

if (!emergencyId) {
  throw new Error("Emergency ID nahi mili.");
}

startPatientLiveGPS();

    if (document.getElementById("statusBox")) {
      document.getElementById("statusBox")
        .classList.remove("hidden");
    }

    if (document.getElementById("timerBox")) {
      document.getElementById("timerBox")
        .classList.remove("hidden");
    }

    if (document.getElementById("statusText")) {
      document.getElementById("statusText").textContent =
        "⚠️ Emergency detected. You have 5 seconds to cancel.";
    }

    let count = 5;

    if (document.getElementById("timer")) {
      document.getElementById("timer").textContent = count;
    }

    clearInterval(timer);

    timer = setInterval(() => {
      count--;

      if (document.getElementById("timer")) {
        document.getElementById("timer").textContent =
          Math.max(count, 0);
      }

      if (count <= 0) {
        clearInterval(timer);
        confirmSOS();
      }
    }, 1000);

  } catch (error) {
    console.error("SOS ERROR:", error);

    let message = error.message || "Unknown error";

    if (error instanceof TypeError) {
      message =
        "Backend se connection nahi ho raha.\n\n" +
        "Check:\n" +
        "1. Flask server running hai?\n" +
        "2. API_BASE correct hai?\n" +
        "3. Browser console mein CORS error hai?\n\n" +
        "API URL:\n" +
        API_BASE + "/api/sos/start";
    }

    alert(message);

    const statusText = document.getElementById("statusText");

    if (statusText) {
      statusText.textContent = "❌ " + message;
    }
  } finally {
    button.disabled = false;
    button.innerHTML = oldText;
  }
}

/* ================================
   CANCEL SOS
================================ */

async function cancelSOS() {
  if (!emergencyId) {
    showMessage("No active emergency found.");
    return;
  }

  clearInterval(timer);
  clearTimeout(pollTimer);

  try {
    const result = await apiFetch("/api/sos/cancel", {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        emergency_id: emergencyId
      })
    });

    if ($("timerBox")) {
      $("timerBox").classList.add("hidden");
    }

    if ($("statusText")) {
      $("statusText").textContent =
        "✅ Emergency cancelled before hospital notification.";
    }

    showMessage(
      result.message ||
      "Emergency cancelled."
    );
  } catch (error) {
    console.error("Cancel SOS error:", error);

    showMessage(
      error.message ||
      "Emergency cancellation failed."
    );
  }
}
stopPatientLiveGPS();

/* ================================
   CONFIRM SOS
================================ */

async function confirmSOS() {
  if (!emergencyId) {
    showMessage("Emergency ID is missing.");
    return;
  }

  if ($("timerBox")) {
    $("timerBox").classList.add("hidden");
  }

  if ($("statusBox")) {
    $("statusBox").classList.remove("hidden");
  }

  try {
    const result = await apiFetch("/api/sos/confirm", {
      method: "POST",
      mode: "cors",
      headers: {
        "Content-Type": "application/json"
      },
      body: JSON.stringify({
        emergency_id: emergencyId
      })
    });

    if (!result.success) {
      throw new Error(
        result.message ||
        result.error ||
        "SOS confirmation failed."
      );
    }

    if ($("statusText")) {
      $("statusText").textContent =
        "Emergency confirmed. Nearby hospitals have been notified.";
    }

    pollEmergency();
  } catch (error) {
    console.error("Confirm SOS error:", error);

    if ($("statusText")) {
      $("statusText").textContent =
        error.message ||
        "Emergency confirmation failed.";
    }
  }
}


/* ================================
   EMERGENCY TRACKING
================================ */

async function pollEmergency() {
  if (!emergencyId) return;

  try {
    const result = await apiFetch(
      "/api/emergency/" + emergencyId
    );

    if (!result.success) {
      console.warn(
        result.message ||
        "Emergency tracking failed."
      );

      scheduleNextPoll();
      return;
    }

    const emergency = result.emergency || {};

    let html = `
      <p>
        <b>Status:</b>
        ${String(emergency.status).toUpperCase() === "COMPLETED" ? "🏥 PATIENT REACHED AT HOSPITAL" : safeValue(emergency.status, "Unknown")}
      </p>
    `;

    if (emergency.hospital_name) {
      html += `
        <p>
          🏥 <b>Hospital:</b>
          ${safeValue(emergency.hospital_name)}
        </p>
      `;
    }

    if (emergency.driver_name) {
      html += `
        <p>
          🚑 <b>Driver:</b>
          ${safeValue(emergency.driver_name)}
          &nbsp;
          <b>Ambulance:</b>
          ${safeValue(
            emergency.ambulance_number,
            "Not assigned"
          )}
        </p>
      `;
    }

    if (
      emergency.ambulance_latitude !== null &&
      emergency.ambulance_latitude !== undefined &&
      emergency.ambulance_longitude !== null &&
      emergency.ambulance_longitude !== undefined
    ) {
      html += `
        <p>
          📍 Ambulance GPS:
          ${Number(
            emergency.ambulance_latitude
          ).toFixed(6)},
          ${Number(
            emergency.ambulance_longitude
          ).toFixed(6)}
        </p>
      `;
    }

    if ($("tracking")) {
      $("tracking").innerHTML = html;
    }

    updatePatientMap(emergency);

    await loadETA();
    await loadTimeline();

    const finalStatuses = [
      "COMPLETED",
      "CANCELLED",
      "DECLINED",
      "CLOSED"
    ];

    if (
  finalStatuses.includes(
    String(emergency.status).toUpperCase()
  )
) {
  stopPatientLiveGPS();
  return;
}

    scheduleNextPoll();
  } catch (error) {
    console.error("Emergency polling error:", error);

    scheduleNextPoll();
  }
}

function scheduleNextPoll() {
  clearTimeout(pollTimer);

  pollTimer = setTimeout(() => {
    pollEmergency();
  }, 3000);
}


/* ================================
   ETA
================================ */

async function loadETA() {
  if (!emergencyId) return;

  try {
    const result = await apiFetch(
      "/api/emergency/" + emergencyId + "/eta"
    );

    const etaBox = $("etaBox");

    if (!etaBox) return;

    if (
      result.to_patient &&
      result.to_patient.distance_km !== undefined
    ) {
      etaBox.classList.remove("hidden");

      etaBox.innerHTML = `
        <b>🚑 Ambulance ETA</b>
        <p>
          ${safeValue(
            result.to_patient.distance_km,
            "—"
          )}
          km away
          • approx
          ${safeValue(
            result.to_patient.eta_minutes,
            "—"
          )}
          min
        </p>
      `;
    } else {
      etaBox.classList.add("hidden");
    }
  } catch (error) {
    console.warn("ETA unavailable:", error);
  }
}


/* ================================
   RESPONSE TIMELINE
================================ */

async function loadTimeline() {
  if (!emergencyId) return;

  try {
    const result = await apiFetch(
      "/api/emergency/" + emergencyId + "/timeline"
    );

    const timelineBox = $("timelineBox");

    if (!timelineBox || !result.timeline) {
      return;
    }

    timelineBox.innerHTML = `
      <div
        style="
          font-weight:800;
          font-size:12px;
          margin-bottom:8px;
        "
      >
        Response Timeline
      </div>

      ${result.timeline
        .map((item) => {
          const eventName = safeValue(
            item.event_type,
            "EVENT"
          ).replaceAll("_", " ");

          return `
            <div class="timeline-item">
              <span class="dot">●</span>

              <div>
                <b>${eventName}</b>

                <div
                  style="
                    color:#718096;
                    margin-top:2px;
                  "
                >
                  ${safeValue(item.message)}
                </div>

                <small style="color:#93a0af">
                  ${safeValue(item.created_at)}
                </small>
              </div>
            </div>
          `;
        })
        .join("")}
    `;
  } catch (error) {
    console.warn("Timeline unavailable:", error);
  }
}


/* ================================
   PATIENT MAP
================================ */

function initPatientMap() {
  if (!window.L) {
    console.warn(
      "Leaflet is not loaded. Add Leaflet JS before this file."
    );

    return;
  }

  const mapElement = $("pmap");

  if (!mapElement) {
    return;
  }

  if (!patientMap) {
    patientMap = L.map("pmap").setView(
      [22.9734, 78.6569],
      5
    );

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution: "© OpenStreetMap"
      }
    ).addTo(patientMap);
  }
}

function isValidCoordinate(latitude, longitude) {
  return (
    latitude !== null &&
    latitude !== undefined &&
    longitude !== null &&
    longitude !== undefined &&
    Number.isFinite(Number(latitude)) &&
    Number.isFinite(Number(longitude))
  );
}

function updatePatientMap(emergency) {
  initPatientMap();

  if (!patientMap || !emergency) {
    return;
  }

  const points = [];

  const patientLat = Number(emergency.latitude);
  const patientLon = Number(emergency.longitude);

  const hospitalLat = Number(
    emergency.hospital_latitude
  );

  const hospitalLon = Number(
    emergency.hospital_longitude
  );

  const ambulanceLat = Number(
    emergency.ambulance_latitude
  );

  const ambulanceLon = Number(
    emergency.ambulance_longitude
  );

  if (
    isValidCoordinate(
      emergency.latitude,
      emergency.longitude
    )
  ) {
    if (patientMarker) {
      patientMarker.setLatLng([
        patientLat,
        patientLon
      ]);
    } else {
      patientMarker = L.marker([
        patientLat,
        patientLon
      ])
        .addTo(patientMap)
        .bindPopup("👤 Your SOS location");
    }

    points.push([
      patientLat,
      patientLon
    ]);
  }

  if (
    isValidCoordinate(
      emergency.hospital_latitude,
      emergency.hospital_longitude
    )
  ) {
    if (hospitalMarker) {
      hospitalMarker.setLatLng([
        hospitalLat,
        hospitalLon
      ]);
    } else {
      hospitalMarker = L.marker([
        hospitalLat,
        hospitalLon
      ])
        .addTo(patientMap)
        .bindPopup("🏥 Hospital");
    }

    points.push([
      hospitalLat,
      hospitalLon
    ]);
  }

  if (
    isValidCoordinate(
      emergency.ambulance_latitude,
      emergency.ambulance_longitude
    )
  ) {
    if (ambulanceMarker) {
      ambulanceMarker.setLatLng([
        ambulanceLat,
        ambulanceLon
      ]);
    } else {
      ambulanceMarker = L.marker([
        ambulanceLat,
        ambulanceLon
      ])
        .addTo(patientMap)
        .bindPopup("🚑 Ambulance");
    }

    points.push([
      ambulanceLat,
      ambulanceLon
    ]);
  }

  if (points.length > 1) {
    patientMap.fitBounds(points, {
      padding: [35, 35]
    });
  } else if (points.length === 1) {
    patientMap.setView(points[0], 14);
  }
}


/* ================================
   PAGE INITIALIZATION
================================ */

document.addEventListener("DOMContentLoaded", () => {
  const auth = $("auth");

  if (auth) {
    auth.classList.add("hidden");
  }

  initPatientMap();
});
window.addEventListener("load", function () {
  loadMe();
  startPatientLiveGPS();
});


/* ================================
   OPTIONAL GLOBAL EXPORTS
   Required if HTML uses onclick=""
================================ */

window.openAuth = openAuth;
window.closeAuth = closeAuth;
window.toggleSignup = toggleSignup;
window.submitAuth = submitAuth;

window.startSOS = startSOS;
window.cancelSOS = cancelSOS;
window.confirmSOS = confirmSOS;

window.pollEmergency = pollEmergency;
window.getGPSLocation = getGPSLocation;