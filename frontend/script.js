const planesList = document.getElementById("planes");
const alertsList = document.getElementById("alerts");

async function fetchData() {
    // get planes
    const planesRes = await fetch("http://127.0.0.1:5000/planes");
    const planes = await planesRes.json();

    planesList.innerHTML = "";
    planes.forEach(p => {
        const li = document.createElement("li");
        li.textContent = `Plane ${p.planeId} → (${p.lat}, ${p.lon})`;
        planesList.appendChild(li);
    });

    // get alerts
    const alertsRes = await fetch("http://127.0.0.1:5000/alerts");
    const alerts = await alertsRes.json();

    alertsList.innerHTML = "";
    alerts.forEach(a => {
        const li = document.createElement("li");
        li.textContent = a;
        alertsList.appendChild(li);
    });
}

// refresh every 2 seconds
setInterval(fetchData, 2000);