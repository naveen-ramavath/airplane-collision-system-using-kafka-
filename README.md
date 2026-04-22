# 🚀 AeroGuard: Airplane Collision Detection System (with GraphX)

A real-time, highly-responsive system that detects potential airplane collisions using streaming telemetry data. It analyzes flight risk on-the-fly using Graph-based modeling concepts and displays critical alerts on a live, beautifully-designed dashboard.

---

## 🌟 What We Built

We designed a complete end-to-end Big Data pipeline for air traffic control simulation:
1. **Data Ingestion**: A Kafka Producer generates realistic, high-throughput flight telemetry (latitude, longitude, altitude, speed) for a fleet of airplanes.
2. **Stream Processing & Graph Analysis**: PySpark Structured Streaming consumes the live feed. It evaluates proximity thresholds and constructs a dynamic graph where **Nodes = Planes** and **Edges = Collisions**. It calculates the degree of each node to determine real-time risk tiers (HIGH, MEDIUM, LOW).
3. **Backend API**: A Flask server acts as the bridge, receiving processed state changes and telemetry from Spark via HTTP POST requests, maintaining an in-memory state of the active airspace.
4. **Live Dashboard**: A modern, glassmorphic UI built with Vanilla JS and CSS dynamically fetches data from Flask. It features live animated counters, priority-sorted collision cards, and a real-time airspace table highlighted by risk level.

---

## 📌 Tech Stack
- **Apache Kafka** → Real-time data streaming and message brokering
- **PySpark Structured Streaming** → Distributed stream processing
- **Graph-based Modeling** → Risk analysis via node degree calculations
- **Flask (Python)** → RESTful Backend API
- **HTML, CSS, JavaScript** → Premium Frontend Dashboard with dynamic DOM updates

## 🎯 Features
- ✈️ **Live Flight Data Streaming**: See plane coordinates and metrics update in real-time.
- 🚨 **Real-time Collision Detection**: Instant threshold-based proximity alerts.
- 🔁 **Collision State Machine**:
  - `NEW`: Just detected
  - `ONGOING`: Persisting over time
  - `ENDED`: Planes have safely separated
- 📊 **Dynamic Dashboard**:
  - Animated Active Flights and Collision counters
  - Clean, prioritized alert cards
- 🧠 **Graph-based Risk Analysis**:
  - Planes as nodes
  - Collisions as edges
  - Risk levels: 🔴 **HIGH**, 🟡 **MEDIUM**, 🟢 **LOW**

## 📂 Project Structure
```text
airplane-project/
│
├── producer.py              # Kafka telemetry data generator
├── spark_consumer.py        # Spark streaming + Graph risk logic
├── app.py                   # Flask backend server
│
├── frontend/
│   ├── index.html           # Dashboard layout
│   ├── script.js            # Live polling and DOM updates
│   └── style.css            # Premium UI styling and animations
└── README.md                # Project documentation
```

---

## ⚙️ Setup Instructions & Terminal Guide

To run this system, you will need **4 separate terminal windows** running simultaneously.

### Terminal 1: Start Zookeeper & Kafka
*Start the Kafka cluster to handle the data stream.*
```bash
cd /mnt/c/Users/<your-username>/Downloads/kafka_2.13-4.2.0

# Start Zookeeper
bin/zookeeper-server-start.sh config/zookeeper.properties

# Once Zookeeper is running, open a new tab/terminal and start Kafka:
bin/kafka-server-start.sh config/server.properties
```

### Terminal 2: Initialize Topic & Run Producer
*Create the topic and start generating simulated flight data.*
```bash
# Create the topic (only needed the first time)
cd /mnt/c/Users/<your-username>/Downloads/kafka_2.13-4.2.0
bin/kafka-topics.sh --create --topic plane-data --bootstrap-server localhost:9092 --partitions 1 --replication-factor 1

# Run the producer
cd /mnt/c/projects/airplane-project
python3 producer.py
```

### Terminal 3: Run Flask Backend
*Start the web server to host the UI and receive Spark data.*
```bash
cd /mnt/c/projects/airplane-project
python3 app.py
```
*(The server will start on `http://0.0.0.0:5000`)*

### Terminal 4: Configure & Run Spark
*Run the heavy analytics engine.*

**Important**: Since Spark runs in WSL, it needs to reach the Flask server running on Windows.
1. Find your Windows IP address by running `ipconfig` in PowerShell or checking the WSL DNS resolver.
2. Update the `BACKEND_URL` in `spark_consumer.py`:
   ```python
   BACKEND_URL = "http://<your-ip>:5000"
   ```

3. Start the Spark consumer:
```bash
cd /mnt/c/projects/airplane-project

spark-submit \
  --packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
  spark_consumer.py
```

### 5️⃣ Open Dashboard
Open your web browser and navigate to:
**👉 http://localhost:5000**

---

## 🔄 How It Works
1. **Kafka Producer** generates continuous flight telemetry data.
2. **Spark** ingests the streaming data in micro-batches.
3. **Collision detection** is performed based on distance and altitude.
4. **Graph modeling** builds relationships and calculates degree-based risk.
5. **Spark POSTs** processed data to the Flask backend.
6. **Flask** stores the active state of the airspace.
7. **UI dashboard** polls Flask every 2 seconds and displays real-time updates.

## 🧠 Collision Logic
Distance is calculated using the Euclidean formula on coordinates:
```text
distance = sqrt((lat1 - lat2)^2 + (lon1 - lon2)^2)
```
A collision event is triggered if:
`distance < threshold` **AND** `altitude difference < threshold`

## 🧠 Graph-Based Risk Analysis
- Each plane is treated as a **node** (vertex).
- Each active collision is treated as an **edge**.

**Example:**
- `A1` ↔ `B1`
- `A1` ↔ `C1`
- 👉 `A1` has 2 edges → **HIGH RISK**

**Risk Calculation:**
*Degree of node = number of active collisions involving that plane.*
- **Degree >= 2** → 🔴 **HIGH** risk
- **Degree == 1** → 🟡 **MEDIUM** risk
- **Degree == 0** → 🟢 **LOW** (Safe) risk

## 📊 Expected Output

**Terminal (Spark):**
```text
🚨 NEW Collision: A1 & B1
⚠️ Ongoing Collision: A1 & B1
✅ Collision Ended: A1 & B1
```

**UI Dashboard:**
- Live updating flights table sorted alphabetically.
- Animated collision alerts with critical badges.
- Row highlights based on Risk levels (HIGH / MEDIUM / LOW).

---

## ⚠️ Important Notes
- **Do NOT use localhost** for Spark → Flask communication inside WSL. You must use the host system IP.
- Ensure the **Kafka cluster is fully running** before starting the Spark job.
- The system is dynamic; it avoids hardcoding plane pairs and handles generic plane IDs automatically.

## 🛠 Debug Tips

**Check Flask Backend Data:**
```bash
curl http://localhost:5000/flights
curl http://localhost:5000/collisions
```

**Monitor Raw Kafka Stream:**
```bash
cd /mnt/c/Users/<your-username>/Downloads/kafka_2.13-4.2.0
bin/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic plane-data
```

## 📌 Future Improvements
- **Interactive Graph Visualization**: Build a network graph UI using D3.js or similar to visualize nodes and edges.
- **Heatmaps**: Implement spatial mapping for frequent collision zones.
- **Machine Learning**: Introduce predictive models to forecast collisions before they break proximity thresholds.
