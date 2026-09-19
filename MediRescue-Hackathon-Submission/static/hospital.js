const USE_LOCAL_BACKEND = true;

const API_BASE = window.location.origin;

let mode = "login";
let map = null;
let markers = [];
let hospitalMarker = null;

const $ = (id) => document.getElementById(id);

function apiUrl(path) {
  return API_BASE + path;
}

function safeText(value, fallback = "") {
  return value === null || value === undefined || value === ""
    ? fallback
    : String(value);
}

function showError(message) {
  console.error(message);
  alert(message);
}

function openAuth(selectedMode = "login") {
  mode = selectedMode;

  const auth = $("auth");
  if (!auth) return;

  auth.classList.remove("hidden");
  renderAuth();
}

function closeAuth() {
  const auth = $("auth");
  if (auth) auth.classList.add("hidden");
}

function renderAuth() {
  const title = $("authTitle");
  const fields = $("authFields");

  if (!title || !fields) return;

  title.textContent =
    mode === "login" ? "Hospital Login" : "Register Hospital";

  if (mode === "login") {
    fields.innerHTML = `
      <input
        id="u"
        type="text"
        placeholder="Hospital username"
        autocomplete="username"
        required
      >

      <input
        id="p"
        type="password"
        placeholder="Password"
        autocomplete="current-password"
        required
      >
    `;
    return;
  }

  fields.innerHTML = `
    <input
      id="name"
      type="text"
      placeholder="Hospital name"
      required
    >

    <input
      id="phone"
      type="tel"
      placeholder="Phone"
      required
    >

    <input
      id="emergency_phone"
      type="tel"
      placeholder="Emergency phone"
      required
    >

    <input
      id="address"
      type="text"
      placeholder="Address"
      required
    >

    <div class="two">
      <input
        id="lat"
        type="number"
        step="any"
        placeholder="Latitude"
        required
      >

      <input
        id="lon"
        type="number"
        step="any"
        placeholder="Longitude"
        required
      >
    </div>

    <button
      type="button"
      class="dark wide"
      onclick="useHospitalGPS()"
    >
      📍 Use My Current Location
    </button>

    <p id="gpsMsg" class="muted">
      Recommended: use current GPS so the hospital appears at its real location.
    </p>

    <input
      id="capacity"
      type="number"
      min="0"
      placeholder="Beds/capacity"
      value="20"
      required
    >

    <input
      id="u"
      type="text"
      placeholder="Username"
      autocomplete="username"
      required
    >

    <input
      id="p"
      type="password"
      placeholder="Password"
      autocomplete="new-password"
      required
    >

    <p class="muted">
      Registration goes to admin for verification.
    </p>
  `;
}

function useHospitalGPS() {
  const gpsMsg = $("gpsMsg");

  if (!navigator.geolocation) {
    if (gpsMsg) {
      gpsMsg.textContent = "GPS is not supported by this browser.";
    }
    return;
  }

  if (gpsMsg) {
    gpsMsg.textContent = "📍 Getting current location...";
  }

  navigator.geolocation.getCurrentPosition(
    (position) => {
      const latitude = position.coords.latitude;
      const longitude = position.coords.longitude;
      const accuracy = position.coords.accuracy;

      if ($("lat")) $("lat").value = latitude.toFixed(7);
      if ($("lon")) $("lon").value = longitude.toFixed(7);

      if (gpsMsg) {
        gpsMsg.textContent =
          `✅ Location captured. Accuracy ~${Math.round(accuracy)} meters`;
      }

      showHospitalMarker(
        latitude,
        longitude,
        "Your hospital location"
      );
    },
    (error) => {
      let message =
        "❌ Could not get GPS. Turn on Location/GPS and retry.";

      if (error.code === 1) {
        message =
          "❌ Location permission denied. Please allow location permission.";
      }

      if (gpsMsg) gpsMsg.textContent = message;
    },
    {
      enableHighAccuracy: true,
      timeout: 15000,
      maximumAge: 0
    }
  );
}

async function submitAuth() {
  try {
    const username = $("u")?.value.trim();
    const password = $("p")?.value;

    if (!username || !password) {
      showError("Username and password required.");
      return;
    }

    let url = "/api/hospital/login";

    const data = {
      username,
      password
    };

    if (mode === "register") {
      url = "/api/hospital/register";

      const name = $("name")?.value.trim();
      const phone = $("phone")?.value.trim();
      const emergencyPhone = $("emergency_phone")?.value.trim();
      const address = $("address")?.value.trim();
      const latitude = $("lat")?.value.trim();
      const longitude = $("lon")?.value.trim();
      const capacity = $("capacity")?.value;

      if (
        !name ||
        !phone ||
        !emergencyPhone ||
        !address ||
        !latitude ||
        !longitude ||
        capacity === ""
      ) {
        showError("Please fill all hospital registration fields.");
        return;
      }

      Object.assign(data, {
        name,
        phone,
        emergency_phone: emergencyPhone,
        address,
        latitude: Number(latitude),
        longitude: Number(longitude),
        capacity: Number(capacity)
      });
    }

    const response = await fetch(apiUrl(url), {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify(data)
    });

    const result = await response.json();

    if (!response.ok || !result.success) {
      showError(result.message || "Request failed.");
      return;
    }

    alert(result.message || "Done");

    if (mode === "login") {
      closeAuth();

      const logoutButton = $("logoutBtn");
      if (logoutButton) {
        logoutButton.style.display = "inline-block";
      }
    }

    await load();
  } catch (error) {
    console.error("Authentication error:", error);
    showError(
      "Backend se connection nahi ho raha. Check karo Flask server running hai ya nahi."
    );
  }
}

async function load() {
  try {
    const meResponse = await fetch(apiUrl("/api/hospital/me"), {
      credentials: "include"
    });

    const me = await meResponse.json();

    if (!me.success) {
      const logoutButton = $("logoutBtn");
      if (logoutButton) logoutButton.style.display = "none";

      const auth = $("auth");

      if (auth && auth.classList.contains("hidden")) {
        openAuth("login");
      }

      return;
    }

    const hospital = me.hospital || {};

    if ($("capacity")) {
      $("capacity").textContent = safeText(hospital.capacity, "—");
    }

    if ($("occupied")) {
      $("occupied").textContent = safeText(hospital.occupied, "—");
    }

    if ($("available")) {
      $("available").textContent =
        hospital.emergency_available ? "YES" : "NO";
    }

    if ($("profile")) {
      $("profile").classList.remove("hidden");

      const latitude = Number(hospital.latitude);
      const longitude = Number(hospital.longitude);

      $("profile").innerHTML = `
        <b>🏥 ${safeText(hospital.name, "Hospital")}</b>
        <br>
        ${safeText(hospital.address, "")}
        <br>
        📍 ${
          Number.isFinite(latitude) ? latitude.toFixed(6) : "N/A"
        },
        ${
          Number.isFinite(longitude) ? longitude.toFixed(6) : "N/A"
        }
        <br>
        Verification: VERIFIED

        <button
          class="dark"
          type="button"
          onclick="centerHospital()"
        >
          📍 Center My Hospital
        </button>
      `;

      if (
        Number.isFinite(latitude) &&
        Number.isFinite(longitude)
      ) {
        showHospitalMarker(
          latitude,
          longitude,
          safeText(hospital.name, "Hospital")
        );
      }
    }

    const emergencyResponse = await fetch(
      apiUrl("/api/hospital/emergencies"),
      {
        credentials: "include"
      }
    );

    const emergencyResult = await emergencyResponse.json();

    if (!emergencyResult.success) {
      if ($("count")) $("count").textContent = "—";
      return;
    }

    const emergencies = emergencyResult.emergencies || [];

    if ($("count")) {
      $("count").textContent = emergencies.length;
    }

    if ($("list")) {
      $("list").innerHTML = emergencies.length
        ? emergencies
            .map((emergency) => {
              const latitude = Number(emergency.latitude);
              const longitude = Number(emergency.longitude);

              return `
                <div class="request card">
                  <div class="tag">
                    🚨 EMERGENCY #MR${emergency.id}
                    &nbsp; • &nbsp; PRIORITY #${safeText(emergency.priority_rank, "1")}
                  </div>

                  <p><b>📍 Smart Match:</b> ${safeText(emergency.distance_km, "N/A")} km away</p>

                  <h2>
                    ${safeText(
                      emergency.patient_name,
                      "Emergency User"
                    )}
                  </h2>

                  <p>
                    📞 ${safeText(
                      emergency.patient_phone,
                      "Not provided"
                    )}
                    &nbsp;
                    🩸 ${safeText(emergency.patient_blood, "N/A")}
                    &nbsp;
                    Age: ${safeText(emergency.patient_age, "N/A")}
                  </p>

                  <p>
                    📍 SOS:
                    ${
                      Number.isFinite(latitude)
                        ? latitude.toFixed(6)
                        : "N/A"
                    },
                    ${
                      Number.isFinite(longitude)
                        ? longitude.toFixed(6)
                        : "N/A"
                    }
                  </p>

                  <button
                    type="button"
                    onclick="respond(${emergency.id}, 'ACCEPT')"
                  >
                    ACCEPT EMERGENCY
                  </button>

                  <button
                    type="button"
                    class="dark"
                    onclick="respond(${emergency.id}, 'DECLINE')"
                  >
                    DECLINE
                  </button>
                </div>
              `;
            })
            .join("")
        : `
          <div class="card">
            <p>No pending emergency notifications.</p>
          </div>
        `;
    }

    draw(emergencies);
  } catch (error) {
    console.error("Hospital load error:", error);
  }
}

async function respond(id, action) {
  try {
    const response = await fetch(
      apiUrl("/api/hospital/respond"),
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify({
          emergency_id: id,
          action
        })
      }
    );

    const result = await response.json();

    alert(result.message || "Done");

    await load();
  } catch (error) {
    console.error("Respond error:", error);
    showError("Emergency response submit nahi ho paya.");
  }
}

function initMap() {
  if (!window.L) {
    console.warn("Leaflet library is not loaded.");
    return;
  }

  if (!map) {
    map = L.map("hmap").setView(
      [22.9734, 78.6569],
      5
    );

    L.tileLayer(
      "https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png",
      {
        attribution: "© OpenStreetMap"
      }
    ).addTo(map);
  }
}

function showHospitalMarker(latitude, longitude, name) {
  initMap();

  if (!map) return;

  const lat = Number(latitude);
  const lon = Number(longitude);

  if (!Number.isFinite(lat) || !Number.isFinite(lon)) {
    return;
  }

  if (hospitalMarker) {
    hospitalMarker.remove();
  }

  hospitalMarker = L.marker([lat, lon])
    .addTo(map)
    .bindPopup("🏥 " + safeText(name, "Hospital"));

  map.setView([lat, lon], 13);
}

function centerHospital() {
  if (hospitalMarker && map) {
    map.setView(
      hospitalMarker.getLatLng(),
      14
    );

    hospitalMarker.openPopup();
  }
}

function draw(emergencies) {
  initMap();

  if (!map) return;

  markers.forEach((marker) => marker.remove());
  markers = [];

  markers = emergencies
    .map((emergency) => {
      const latitude = Number(emergency.latitude);
      const longitude = Number(emergency.longitude);

      if (
        !Number.isFinite(latitude) ||
        !Number.isFinite(longitude)
      ) {
        return null;
      }

      return L.marker([latitude, longitude])
        .addTo(map)
        .bindPopup(`🚨 SOS #MR${emergency.id}`);
    })
    .filter(Boolean);
}

async function enableNotifications() {
  try {
    if (
      "Notification" in window &&
      Notification.permission === "default"
    ) {
      await Notification.requestPermission();
    }
  } catch (error) {
    console.warn("Notification permission error:", error);
  }
}

document.addEventListener(
  "click",
  enableNotifications,
  { once: true }
);

let knownDispatches = new Map();
let firstDispatchLoad = true;


async function markReached(id) {
  const confirmed = window.confirm(
    "Confirm that the ambulance and patient have reached the hospital?\n\nThis will close the emergency, stop patient/ambulance live tracking for this emergency, and make the ambulance available again."
  );
  if (!confirmed) return;

  try {
    const response = await fetch(apiUrl("/api/hospital/reached"), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ emergency_id: id })
    });
    const result = await response.json();
    if (!response.ok || !result.success) {
      throw new Error(result.message || `HTTP ${response.status}`);
    }
    alert("🏥 Patient reached at hospital. Emergency closed and ambulance is AVAILABLE.");
    await loadDispatches();
    await loadEmergencies();
  } catch (error) {
    console.error("Hospital reached update error:", error);
    alert(error.message || "Unable to mark ambulance as reached.");
  }
}

async function loadDispatches() {
  try {
    const response = await fetch(
      apiUrl("/api/hospital/dispatches"),
      {
        credentials: "include"
      }
    );

    const result = await response.json();

    if (!result.success) return;

    const dispatches = result.dispatches || [];

    if ($("dispatchList")) {
      $("dispatchList").innerHTML = dispatches.length
        ? dispatches
            .map((dispatch) => {
              const driverLatitude =
                dispatch.driver_latitude != null
                  ? Number(dispatch.driver_latitude)
                  : null;

              const driverLongitude =
                dispatch.driver_longitude != null
                  ? Number(dispatch.driver_longitude)
                  : null;

              const driverGps =
                Number.isFinite(driverLatitude) &&
                Number.isFinite(driverLongitude)
                  ? `
                    <br>
                    📍 Driver GPS:
                    ${driverLatitude.toFixed(6)},
                    ${driverLongitude.toFixed(6)}
                  `
                  : "";

              return `
                <div class="request card">
                  <div class="tag">
                    🚑 ${safeText(dispatch.status, "UNKNOWN")}
                  </div>

                  <h2>
                    Emergency #MR${dispatch.id}
                  </h2>

                  <p>
                    👤 ${safeText(
                      dispatch.patient_name,
                      "Emergency User"
                    )}
                    &nbsp;
                    📞 ${safeText(
                      dispatch.patient_phone,
                      "Not provided"
                    )}
                  </p>

                  <div
                    class="notice"
                    style="margin:10px 0 0"
                  >
                    <b>🚑 Ambulance Assignment</b>
                    <br>
                    Driver:
                    <b>
                      ${safeText(
                        dispatch.driver_name,
                        "Waiting for driver acceptance"
                      )}
                    </b>

                    <br>
                    Driver Phone:
                    <b>
                      ${safeText(
                        dispatch.driver_phone,
                        "Not available yet"
                      )}
                    </b>

                    <br>
                    Ambulance:
                    <b>
                      ${safeText(
                        dispatch.ambulance_number,
                        "Not assigned yet"
                      )}
                    </b>

                    <br>
                    Driver status:
                    <b>
                      ${safeText(
                        dispatch.driver_status,
                        "Waiting"
                      )}
                    </b>

                    ${driverGps}
                  </div>

                  <div class="actions" style="margin-top:12px;display:flex;gap:8px;flex-wrap:wrap">
                    ${
                      (dispatch.status === "DISPATCHED" || dispatch.status === "PICKED_UP")
                        ? `<button type="button" class="dark" onclick="markReached(${dispatch.id})">🏥 AMBULANCE REACHED HOSPITAL</button>`
                        : ""
                    }
                  </div>
                </div>
              `;
            })
            .join("")
        : `
          <div class="card">
            <p>No ambulance dispatch yet.</p>
          </div>
        `;
    }

    const currentDispatches = new Map(
      dispatches.map((dispatch) => [
        String(dispatch.id),
        dispatch.status
      ])
    );

    if (!firstDispatchLoad) {
      for (const [id, status] of currentDispatches) {
        const oldStatus = knownDispatches.get(id);

        if (
          oldStatus !== status &&
          status === "DISPATCHED"
        ) {
          const dispatch = dispatches.find(
            (item) => String(item.id) === id
          );

          if (!dispatch) continue;

          const message =
            `🚑 Driver ${
              dispatch.driver_name || ""
            } accepted Emergency #MR${id}. ` +
            `Ambulance ${
              dispatch.ambulance_number || ""
            } is dispatched.`;

          if ($("hospitalNotice")) {
            $("hospitalNotice").classList.remove("hidden");
            $("hospitalNotice").textContent = message;
          }

          if (
            "Notification" in window &&
            Notification.permission === "granted"
          ) {
            new Notification(
              "🚑 Ambulance Accepted",
              { body: message }
            );
          }

          try {
            const audio = new Audio(
              "data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEARKwAAIhYAQACABAAZGF0YQAAAAA="
            );

            audio.play().catch(() => {});
          } catch (error) {
            console.warn("Audio notification failed:", error);
          }
        }
      }
    }

    knownDispatches = currentDispatches;
    firstDispatchLoad = false;
  } catch (error) {
    console.error("Dispatch load error:", error);
  }
}

async function refreshHospitalData() {
  await load();
  await loadDispatches();
}

async function logout() {
  try {
    await fetch(apiUrl("/api/logout"), {
      method: "POST",
      credentials: "include"
    });
  } catch (error) {
    console.warn("Logout API error:", error);
  }

  // Do not clear complete localStorage/sessionStorage.
  location.reload();
}

renderAuth();
refreshHospitalData();

setInterval(refreshHospitalData, 3000);