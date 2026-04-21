// ============================================================
//  AeroGuard — Real-Time Dashboard  |  script.js
//
//  Architecture:
//    /ping       → connection status only
//    /collisions → collision alert panel + NEW/ONGOING/ENDED counts
//    /flights    → live airspace table + active flight count
//    /stats      → cumulative totals (best-effort, optional)
//
//  Poll cycle every 2 s:
//    checkConnection() → loadCollisions() → loadFlights() → tryLoadStats()
//
//  Counts are ALWAYS derived from the data directly (never depend on /stats).
//  /stats enriches the New Alerts + Resolved counters with server-side totals.
// ============================================================

const BASE_URL   = "http://localhost:5000";
const REFRESH_MS = 2000;

// Planes currently in an active (NEW or ONGOING) collision
let collidingPlanes = new Set();

// Local snapshot of counts updated each cycle
let counts = {
    flights:  0,
    newAlerts: 0,
    ongoing:  0,
    resolved: 0,
};


// ─────────────────────────────────────────
//  ANIMATED COUNTER
// ─────────────────────────────────────────
function setCount(elId, value) {
    const el = document.getElementById(elId);
    if (!el) return;
    const current = parseInt(el.textContent, 10);
    if (!isNaN(current) && current === value) return;  // no change

    el.style.transform = "scale(1.4)";
    el.style.opacity   = "0.5";
    el.textContent     = value;
    setTimeout(() => {
        el.style.transform = "";
        el.style.opacity   = "";
    }, 250);
}


// ─────────────────────────────────────────
//  CONNECTION STATUS
// ─────────────────────────────────────────
function setStatus(online, text) {
    const dot   = document.getElementById("statusDot");
    const label = document.getElementById("statusText");
    if (!dot || !label) return;
    dot.className     = "status-dot " + (online ? "online" : "offline");
    label.textContent = text;
}

async function checkConnection() {
    try {
        const res = await fetch(`${BASE_URL}/ping?_=${Date.now()}`, { cache: "no-store" });
        setStatus(res.ok, res.ok ? "Connected" : `Flask error ${res.status}`);
    } catch {
        setStatus(false, "Disconnected");
    }
}


// ─────────────────────────────────────────
//  LOAD COLLISIONS
//  → renders alert cards
//  → derives NEW / ONGOING / ENDED counts from data
//  → builds collidingPlanes for flight table
// ─────────────────────────────────────────
async function loadCollisions() {
    try {
        const res = await fetch(`${BASE_URL}/collisions?_=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) {
            console.warn(`/collisions returned HTTP ${res.status}`);
            return;
        }
        const data = await res.json();

        const list       = document.getElementById("collisionList");
        const emptyState = document.getElementById("emptyState");
        const badge      = document.getElementById("collisionsCount");

        if (!list || !emptyState) return;

        list.innerHTML = "";
        collidingPlanes.clear();

        // ── Derive counts from the actual array ──────────────
        let cntNew = 0, cntOngoing = 0, cntEnded = 0;
        for (const c of data) {
            if (c.status === "NEW")     cntNew++;
            else if (c.status === "ONGOING") cntOngoing++;
            else if (c.status === "ENDED")   cntEnded++;
        }

        counts.newAlerts = cntNew;
        counts.ongoing   = cntOngoing;
        counts.resolved  = cntEnded;      // may be enriched later by /stats

        // Update badge on the panel header
        if (badge) badge.textContent = data.length;

        if (!data || data.length === 0) {
            emptyState.style.display = "flex";
            return;
        }
        emptyState.style.display = "none";

        // ── Sort: NEW → ONGOING → ENDED ──────────────────────
        const PRIORITY = { NEW: 1, ONGOING: 2, ENDED: 3 };
        data.sort((a, b) => (PRIORITY[a.status] || 9) - (PRIORITY[b.status] || 9));

        // ── Render cards ─────────────────────────────────────
        const STYLES = {
            NEW:     { icon: "🚨", cls: "state-new",     badge: "badge-new",     label: "CRITICAL ALERT" },
            ONGOING: { icon: "⚠️", cls: "state-ongoing", badge: "badge-ongoing", label: "ONGOING"        },
            ENDED:   { icon: "✅", cls: "state-ended",   badge: "badge-ended",   label: "RESOLVED"       },
        };

        for (const c of data) {
            if (!c) continue;

            // Track planes in active collisions
            if (c.status !== "ENDED") {
                if (c.plane1) collidingPlanes.add(c.plane1);
                if (c.plane2) collidingPlanes.add(c.plane2);
            }

            const s  = STYLES[c.status] ?? STYLES.ONGOING;
            const li = document.createElement("li");
            li.className = `incident-card ${s.cls}`;
            li.innerHTML = `
                <div class="icon-col">${s.icon}</div>
                <div class="incident-details">
                    <div class="planes-id">
                        <span class="plane-tag">${c.plane1 || "—"}</span>
                        <span class="vs-sep">vs</span>
                        <span class="plane-tag">${c.plane2 || "—"}</span>
                    </div>
                    <span class="status-badge ${s.badge}">${s.label}</span>
                </div>
                <div class="time-stamp">
                    <small>Last Update</small>
                    ${c.time || "—"}
                </div>
            `;
            list.appendChild(li);
        }

    } catch (err) {
        console.error("❌ /collisions error:", err);
    }
}


// ─────────────────────────────────────────
//  LOAD FLIGHTS
//  → renders live airspace table
//  → derives active flight count
//  → marks RISK / NOMINAL using collidingPlanes
//    (must run AFTER loadCollisions)
// ─────────────────────────────────────────
async function loadFlights() {
    try {
        const res = await fetch(`${BASE_URL}/flights?_=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) {
            console.warn(`/flights returned HTTP ${res.status}`);
            return;
        }
        const data = await res.json();

        const tbody = document.getElementById("flightsList");
        const badge = document.getElementById("flightsCount");

        if (!tbody) return;

        counts.flights = data.length;
        if (badge) badge.textContent = data.length;

        tbody.innerHTML = "";

        if (!data || data.length === 0) {
            tbody.innerHTML = `
                <tr class="empty-row">
                    <td colspan="6">
                        <div class="table-empty">
                            <span>📡</span>
                            Waiting for flight telemetry…
                        </div>
                    </td>
                </tr>`;
            return;
        }

        // Sort alphabetically
        data.sort((a, b) => (a.planeId || "").localeCompare(b.planeId || ""));

        for (const p of data) {
            if (!p) continue;
            const inDanger = collidingPlanes.has(p.planeId);
            const statusHtml = inDanger
                ? `<span class="flight-status-badge danger">⚠ RISK</span>`
                : `<span class="flight-status-badge">● NOMINAL</span>`;

            const tr = document.createElement("tr");
            tr.innerHTML = `
                <td><span class="flight-id">${p.planeId || "—"}</span></td>
                <td><span class="coord-val">${Number(p.lat      || 0).toFixed(4)}</span></td>
                <td><span class="coord-val">${Number(p.lon      || 0).toFixed(4)}</span></td>
                <td><span class="alt-val">${Number(p.altitude || 0).toLocaleString()} ft</span></td>
                <td><span class="speed-val">${p.speed || "—"} kts</span></td>
                <td>${statusHtml}</td>
            `;
            tbody.appendChild(tr);
        }

    } catch (err) {
        console.error("❌ /flights error:", err);
    }
}


// ─────────────────────────────────────────
//  TRY LOAD STATS  (best-effort / optional)
//  Enriches New Alerts + Resolved with cumulative
//  server-side totals.  Silently skipped if /stats
//  is unavailable so other panels still work.
// ─────────────────────────────────────────
async function tryLoadStats() {
    try {
        const res = await fetch(`${BASE_URL}/stats?_=${Date.now()}`, { cache: "no-store" });
        if (!res.ok) return;                         // endpoint missing → skip silently
        const d = await res.json();

        // Prefer server cumulative totals for New Alerts + Resolved
        if (typeof d.total_new      === "number") counts.newAlerts = d.total_new;
        if (typeof d.total_resolved === "number") counts.resolved  = d.total_resolved;
        // Ongoing = live active pairs right now
        if (typeof d.active_collisions === "number") counts.ongoing = d.active_collisions;
        if (typeof d.active_flights    === "number") counts.flights  = d.active_flights;

    } catch {
        // /stats not available — use counts derived from data, no problem
    }
}


// ─────────────────────────────────────────
//  FLUSH COUNTS TO DOM
//  Called once per cycle after all fetches complete
// ─────────────────────────────────────────
function flushCounts() {
    setCount("statsFlights", counts.flights);
    setCount("statsNew",     counts.newAlerts);
    setCount("statsOngoing", counts.ongoing);
    setCount("statsEnded",   counts.resolved);
}


// ─────────────────────────────────────────
//  FOOTER TIMESTAMP
// ─────────────────────────────────────────
function updateTimestamp() {
    const el = document.getElementById("lastUpdated");
    if (el) el.textContent = `Last updated: ${new Date().toLocaleTimeString()}`;
}


// ─────────────────────────────────────────
//  POLL CYCLE
//  Order:
//    1. checkConnection  (ping → status badge)
//    2. loadCollisions   (builds collidingPlanes + local counts)
//    3. loadFlights      (uses collidingPlanes for RISK badge)
//    4. tryLoadStats     (enriches counts with cumulative totals)
//    5. flushCounts      (writes final counts to DOM)
//    6. updateTimestamp
// ─────────────────────────────────────────
async function refresh() {
    await checkConnection();
    await loadCollisions();
    await loadFlights();
    await tryLoadStats();
    flushCounts();
    updateTimestamp();
}


// ─────────────────────────────────────────
//  BOOT
// ─────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    setStatus(false, "Connecting…");
    refresh();
    setInterval(refresh, REFRESH_MS);
});