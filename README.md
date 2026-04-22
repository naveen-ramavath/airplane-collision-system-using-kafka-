# 🚀 Airplane Collision Detection System

A real-time system that detects potential airplane collisions using streaming data and displays them on a live dashboard.

## 📌 Tech Stack
- **Kafka** → Data streaming
- **PySpark Structured Streaming** → Real-time processing
- **Flask** → Backend API
- **HTML, CSS, JavaScript** → Frontend Dashboard

## 🎯 Features
- ✈️ Live flight data streaming
- 🚨 Real-time collision detection
- 🔁 Collision states:
  - NEW
  - ONGOING
  - ENDED
- 📊 Dashboard with:
  - Active Flights
  - New Alerts
  - Ongoing Collisions
  - Resolved Collisions
- 🧠 Graph-based risk analysis:
  - HIGH / MEDIUM / LOW risk flights

## 📂 Project Structure
```text
airplane-project/
│
├── producer.py              # Kafka data generator
├── spark_consumer.py        # Spark streaming + collision logic
├── app.py                   # Flask backend
│
├── frontend/
│   ├── index.html           # UI
│   ├── script.js            # Frontend logic
│   └── style.css            # Styling
```

## ⚙️ Setup Instructions

### 1️⃣ Start Kafka
```bash
cd /mnt/c/Users/<your-username>/Downloads/kafka_2.13-4.2.0

bin/zookeeper-server-start.sh config/zookeeper.properties

# Open new terminal:
bin/kafka-server-start.sh config/server.properties
```

### 2️⃣ Create Topic
```bash
bin/kafka-topics.sh --create \
--topic plane-data \
--bootstrap-server localhost:9092 \
--partitions 1 \
--replication-factor 1
```

### 3️⃣ Run Producer
```bash
cd /mnt/c/projects/airplane-project
python3 producer.py
```

### 4️⃣ Run Flask Backend
```bash
cd /mnt/c/projects/airplane-project
python3 app.py
```

### 5️⃣ Configure Backend URL (IMPORTANT)
Since Spark runs in WSL, use your Windows IP.

Find IP:
```bash
ipconfig
```

Update in `spark_consumer.py`:
```python
BACKEND_URL = "http://<your-ip>:5000"
```

### 6️⃣ Run Spark
```bash
cd /mnt/c/projects/airplane-project

spark-submit \
--packages org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.1 \
spark_consumer.py
```

### 7️⃣ Open Dashboard
Navigate to http://localhost:5000 in your browser.

## 🔄 How It Works
1. Producer generates flight data
2. Kafka streams the data
3. Spark processes and detects collisions
4. Flask stores and serves data
5. UI displays real-time updates

## 🧠 Collision Logic
```text
distance = sqrt((lat1 - lat2)^2 + (lon1 - lon2)^2)
```

Collision if:
`distance < threshold` AND `altitude difference < threshold`

## 📊 Graph-Based Enhancement
- **Planes** = Nodes
- **Collisions** = Edges
- **Degree of node** = Risk level
  - **HIGH** → multiple collisions (degree >= 2)
  - **MEDIUM** → one collision (degree == 1)
  - **LOW** → no collision (degree == 0)

## 🚀 Expected Output

**Terminal:**
```text
🚨 NEW Collision: A1 & B1
⚠️ Ongoing Collision: A1 & B1
✅ Collision Ended: A1 & B1
```

**UI:**
- Live flights table
- Collision alerts
- Risk levels

## ⚠️ Important Notes
- Do **NOT** use localhost for Spark → Flask communication in WSL.
- Always use your system IP.
- Ensure Kafka is running before Spark.

## 🛠 Debug Tips

Check backend:
```bash
curl http://localhost:5000/collisions
```

Check Kafka:
```bash
bin/kafka-console-consumer.sh \
--bootstrap-server localhost:9092 \
--topic plane-data
```

## 📌 Future Improvements
- GraphX-based clustering
- Map visualization (Leaflet/Google Maps)
- ML-based collision prediction
