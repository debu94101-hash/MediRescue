const USE_LOCAL_BACKEND = true;

const API_BASE = window.location.origin;

let mode = 'login';
let active = null;
let watchId = null;
let map = null;
let patientMarker = null;
let hospitalMarker = null;
let ambulanceMarker = null;

const $ = id => document.getElementById(id);


/* =========================
   AUTH MODAL
========================= */

function openAuth(m = 'login') {
  mode = m;

  const auth = $('auth');

  if (auth) {
    auth.classList.remove('hidden');
  }

  renderAuth();
}

function closeAuth() {
  const auth = $('auth');

  if (auth) {
    auth.classList.add('hidden');
  }
}

function renderAuth() {
  const title = $('authTitle');
  const fields = $('authFields');

  if (!title || !fields) return;

  title.textContent =
    mode === 'login'
      ? 'Driver Login'
      : 'Register Ambulance Driver';

  if (mode === 'login') {
    fields.innerHTML = `
      <input
        id="u"
        type="text"
        placeholder="Driver username"
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
  } else {
    fields.innerHTML = `
      <input
        id="name"
        placeholder="Full name"
        required
      >

      <input
        id="phone"
        placeholder="Phone"
        type="tel"
        required
      >

      <input
        id="license"
        placeholder="Driving license"
        required
      >

      <input
        id="ambulance"
        placeholder="Ambulance number"
        required
      >

      <input
        id="hospital_id"
        placeholder="Verified hospital ID"
        type="number"
        required
      >

      <input
        id="u"
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
        Driver registration requires a verified hospital and admin approval.
      </p>
    `;
  }
}


/* =========================
   LOGIN / REGISTER
========================= */

async function submitAuth() {
  try {
    const usernameInput = $('u');
    const passwordInput = $('p');

    if (!usernameInput || !passwordInput) {
      alert('Please fill the login form.');
      return;
    }

    let data = {
      username: usernameInput.value.trim(),
      password: passwordInput.value
    };

    let url = '/api/driver/login';

    if (mode === 'register') {
      url = '/api/driver/register';

      data = {
        ...data,
        name: $('name').value.trim(),
        phone: $('phone').value.trim(),
        license_number: $('license').value.trim(),
        ambulance_number: $('ambulance').value.trim(),
        hospital_id: $('hospital_id').value
      };
    }

    const response = await fetch(API_BASE + url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      credentials: 'include',
      body: JSON.stringify(data)
    });

    const result = await response.json();

    alert(
      result.message ||
      result.error ||
      (response.ok ? 'Done' : 'Request failed')
    );

    if (result.success && mode === 'login') {
      closeAuth();
      startIdleGPS();

      const logoutButton = $('logoutBtn');

      if (logoutButton) {
        logoutButton.style.display = 'inline-block';
      }
    }

    await load();

  } catch (error) {
    console.error('Authentication error:', error);
    alert('Server connection failed. Make sure Flask is running.');
  }
}


/* =========================
   LOAD DRIVER DATA
========================= */

async function load() {
  try {
    const meResponse = await fetch(
      API_BASE + '/api/driver/me',
      {
        credentials: 'include'
      }
    );

    const me = await meResponse.json();

    if (!me.success || !me.driver) {
      const logoutButton = $('logoutBtn');

      if (logoutButton) {
        logoutButton.style.display = 'none';
      }

      const auth = $('auth');

      if (auth && auth.classList.contains('hidden')) {
        openAuth('login');
      }

      return;
    }

    const emergenciesResponse = await fetch(
      API_BASE + '/api/driver/emergencies',
      {
        credentials: 'include'
      }
    );

    const emergencyResult = await emergenciesResponse.json();

    if (!emergencyResult.success) {
      console.error(
        emergencyResult.message ||
        emergencyResult.error ||
        'Unable to load emergencies'
      );
      return;
    }

    const emergencies = emergencyResult.emergencies || [];
    if (active && !emergencies.some(e => Number(e.id) === Number(active))) {
      active = null;
      if (watchId !== null) {
        navigator.geolocation.clearWatch(watchId);
        watchId = null;
      }
    }
    const list = $('list');

    if (list) {
      list.innerHTML = emergencies.length
        ? emergencies.map(emergency => {
            const status = emergency.status || '';

            let actionButton = '';

            if (status === 'HOSPITAL_ACCEPTED') {
              actionButton = `
                <button
                  onclick="accept(${emergency.id})"
                >
                  🚑 ACCEPT & START GPS
                </button>
              `;
            }

            if (status === 'DISPATCHED') {
              actionButton = `
                <button
                  onclick="markResponse(${emergency.id}, 'PICKED_UP')"
                >
                  👤 PATIENT PICKED UP
                </button>
              `;
            }

            if (status === 'PICKED_UP') {
              actionButton = `
                <button
                  onclick="markResponse(${emergency.id}, 'COMPLETED')"
                >
                  🏥 COMPLETE TRIP
                </button>
              `;
            }

            return `
              <div class="card">
                <div class="tag">
                  🚨 ${status}
                </div>

                <h2>
                  ${emergency.patient_name || 'Emergency User'}
                </h2>

                <p>
                  📍 Pickup:
                  ${Number(emergency.latitude || 0).toFixed(6)},
                  ${Number(emergency.longitude || 0).toFixed(6)}
                </p>

                <p>
                  🏥 ${emergency.hospital_name || 'Hospital not assigned'}
                </p>

                ${actionButton}
              </div>
            `;
          }).join('')
        : `
          <div class="card">
            <p>No hospital-accepted dispatches.</p>
          </div>
        `;
    }

    draw(emergencies);

    const driver = me.driver;
    const driverInfo = $('driverInfo');

    if (driverInfo) {
      const latitude = driver.latitude
        ? Number(driver.latitude).toFixed(6)
        : 'Waiting for GPS';

      const longitude = driver.longitude
        ? Number(driver.longitude).toFixed(6)
        : '';

      driverInfo.innerHTML = `
        ${driver.name || 'Driver'}
        •
        ${driver.ambulance_number || 'Ambulance'}<br>

        📍 ${latitude}, ${longitude}<br>

        Status:
        <b>${driver.status || 'UNKNOWN'}</b>
      `;
    }

    if (driver.latitude && driver.longitude) {
      updateAmbulance(
        Number(driver.latitude),
        Number(driver.longitude)
      );
    }

  } catch (error) {
    console.error('Load error:', error);
  }
}


/* =========================
   ACCEPT EMERGENCY
========================= */

async function accept(id) {
  try {
    const response = await fetch(
      API_BASE + '/api/driver/accept',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          emergency_id: id
        })
      }
    );

    const result = await response.json();

    alert(
      result.message ||
      result.error ||
      'Done'
    );

    if (result.success) {
      active = id;
      startGPS();
    }

    await load();

  } catch (error) {
    console.error('Accept emergency error:', error);
    alert('Unable to accept emergency.');
  }
}


/* =========================
   UPDATE RESPONSE STATUS
========================= */

async function markResponse(id, status) {
  try {
    const response = await fetch(
      API_BASE + '/api/driver/response-status',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          emergency_id: id,
          status: status
        })
      }
    );

    const result = await response.json();

    alert(
      result.message ||
      result.error ||
      'Done'
    );

    if (result.success) {
      if (status === 'COMPLETED') {
        if (active === id) {
          active = null;
        }
      } else {
        active = id;
        startGPS();
      }

      await load();
    }

  } catch (error) {
    console.error('Response status error:', error);
    alert('Unable to update emergency status.');
  }
}


/* =========================
   GPS
========================= */

function startIdleGPS() {
  startGPSWatch(null);
}

function startGPS() {
  if (active) {
    startGPSWatch(active);
  }
}

function startGPSWatch(emergencyId) {
  if (!navigator.geolocation) {
    alert('GPS is not supported by this browser.');
    return;
  }

  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
  }

  watchId = navigator.geolocation.watchPosition(
    async position => {
      try {
        const data = {
          latitude: position.coords.latitude,
          longitude: position.coords.longitude
        };

        if (emergencyId) {
          data.emergency_id = emergencyId;
        }

        await fetch(
          API_BASE + '/api/driver/location',
          {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json'
            },
            credentials: 'include',
            body: JSON.stringify(data)
          }
        );

        updateAmbulance(
          position.coords.latitude,
          position.coords.longitude
        );

      } catch (error) {
        console.error('GPS update error:', error);
      }
    },

    error => {
      const driverInfo = $('driverInfo');

      if (driverInfo) {
        driverInfo.innerHTML += `
          <span class="muted">
            GPS unavailable
          </span>
        `;
      }

      console.error('GPS error:', error);
    },

    {
      enableHighAccuracy: true,
      maximumAge: 2000,
      timeout: 10000
    }
  );
}
let driverGpsWatchId = null;

function startDriverLiveGPS(emergencyId) {
  driverGpsWatchId = navigator.geolocation.watchPosition(
    async (position) => {
      const payload = {
        emergency_id: emergencyId,
        latitude: position.coords.latitude,
        longitude: position.coords.longitude,
        accuracy: position.coords.accuracy
      };

      try {
        await fetch(
          API_BASE + "/api/driver/location",
          {
            method: "POST",
            mode: "cors",
            credentials: "include",
            headers: {
              "Content-Type": "application/json"
            },
            body: JSON.stringify(payload)
          }
        );
      } catch (error) {
        console.warn("Driver GPS update failed:", error);
      }
    },
    (error) => {
      console.error("Driver GPS error:", error);
    },
    {
      enableHighAccuracy: true,
      maximumAge: 2000,
      timeout: 10000
    }
  );
}


/* =========================
   DRIVER STATUS
========================= */

async function setStatus(status) {
  try {
    const response = await fetch(
      API_BASE + '/api/driver/status',
      {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        credentials: 'include',
        body: JSON.stringify({
          status: status
        })
      }
    );

    const result = await response.json();

    alert(
      result.message ||
      result.error ||
      status
    );

    await load();

  } catch (error) {
    console.error('Status update error:', error);
    alert('Unable to update driver status.');
  }
}


/* =========================
   MAP
========================= */

function initMap() {
  if (!window.L) {
    console.warn('Leaflet map library is not loaded.');
    return;
  }

  if (!map) {
    map = L.map('map').setView(
      [22.9734, 78.6569],
      5
    );

    L.tileLayer(
      'https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png',
      {
        attribution: '© OpenStreetMap contributors'
      }
    ).addTo(map);
  }
}

function draw(emergencies) {
  initMap();

  if (!map || !emergencies || !emergencies.length) {
    return;
  }

  const emergency = emergencies[0];

  if (
    emergency.latitude === undefined ||
    emergency.longitude === undefined ||
    emergency.hospital_latitude === undefined ||
    emergency.hospital_longitude === undefined
  ) {
    return;
  }

  if (patientMarker) {
    patientMarker.remove();
  }

  if (hospitalMarker) {
    hospitalMarker.remove();
  }

  patientMarker = L.marker([
    Number(emergency.latitude),
    Number(emergency.longitude)
  ])
    .addTo(map)
    .bindPopup('👤 Patient pickup');

  hospitalMarker = L.marker([
    Number(emergency.hospital_latitude),
    Number(emergency.hospital_longitude)
  ])
    .addTo(map)
    .bindPopup('🏥 Hospital');

  map.fitBounds(
    [
      [
        Number(emergency.latitude),
        Number(emergency.longitude)
      ],
      [
        Number(emergency.hospital_latitude),
        Number(emergency.hospital_longitude)
      ]
    ],
    {
      padding: [30, 30]
    }
  );
}

function updateAmbulance(latitude, longitude) {
  initMap();

  if (!map) {
    return;
  }

  const position = [
    Number(latitude),
    Number(longitude)
  ];

  if (ambulanceMarker) {
    ambulanceMarker.setLatLng(position);
  } else {
    ambulanceMarker = L.marker(position)
      .addTo(map)
      .bindPopup('🚑 Your ambulance');
  }
}


/* =========================
   NAVIGATION
========================= */

function navigateTo(latitude, longitude) {
  if (latitude && longitude) {
    const destination =
      encodeURIComponent(
        latitude + ',' + longitude
      );

    window.open(
      'https://www.google.com/maps/dir/?api=1&destination=' +
      destination,
      '_blank'
    );
  }
}


/* =========================
   LOGOUT
========================= */

async function logout() {
  try {
    await fetch(
      API_BASE + '/api/logout',
      {
        method: 'POST',
        credentials: 'include'
      }
    );
  } catch (error) {
    console.error('Logout error:', error);
  }

  if (watchId !== null) {
    navigator.geolocation.clearWatch(watchId);
    watchId = null;
  }

  localStorage.clear();
  sessionStorage.clear();

  location.reload();
}


/* =========================
   INITIALIZE
========================= */

renderAuth();
load();

// Testing ke liye interval abhi disabled hai.
// Sab sahi chalne ke baad enable kar sakte ho.
// setInterval(load, 3000);