async function loadCollisions() {
    try {
        const res = await fetch("http://localhost:5000/collisions");
        const data = await res.json();

        const list = document.getElementById("collisionList");
        list.innerHTML = "";

        data.forEach(c => {
            const li = document.createElement("li");

            if (c.status === "NEW") {
                li.textContent = `🚨 ${c.plane1} & ${c.plane2} STARTED (${c.time})`;
                li.style.background = "#ff4d4d";
            } 
            else if (c.status === "ONGOING") {
                li.textContent = `⚠️ ${c.plane1} & ${c.plane2} ONGOING (${c.time})`;
                li.style.background = "#ffa500";
            } 
            else if (c.status === "ENDED") {
                li.textContent = `✅ ${c.plane1} & ${c.plane2} ENDED (${c.time})`;
                li.style.background = "#4CAF50";
            }

            list.appendChild(li);
        });
    } catch (err) {
        console.error("Error fetching collisions:", err);
    }
}

// refresh every 2 seconds
setInterval(loadCollisions, 2000);