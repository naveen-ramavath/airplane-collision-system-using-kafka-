"""
AeroGuard — Spark Structured Streaming Consumer
================================================
Reads plane telemetry from Kafka, detects collisions between
every pair of planes, and POSTs state changes to Flask.

Collision thresholds:
  distance  < 0.1  degrees (≈ 11 km)
  altitude  < 3500 feet difference

State machine per pair:
  (not colliding) ──NEW──► ACTIVE ──ONGOING──► ACTIVE ──ENDED──► (not colliding)

ONGOING heartbeats are throttled: one POST per pair every 10 s.
"""
# in this we have graphx and spark streaming

from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import (
    StructType, StringType, DoubleType, IntegerType
)
import time
import requests
import subprocess

# ─────────────────────────────────────────────────────────────
#  RESOLVE WINDOWS HOST IP FROM WSL
# ─────────────────────────────────────────────────────────────

def get_windows_host_ip() -> str:
    """
    Tries three strategies to find the IP of the Windows host
    that WSL2 can reach, in order of reliability.
    """
    # 1. /etc/resolv.conf nameserver line
    try:
        with open("/etc/resolv.conf") as f:
            for line in f:
                if line.startswith("nameserver"):
                    ip = line.strip().split()[1]
                    print(f"[CONFIG] Host IP from resolv.conf: {ip}")
                    return ip
    except Exception as e:
        print(f"[WARN]  resolv.conf failed: {e}")

    # 2. ip route default gateway
    try:
        out = subprocess.check_output(["ip", "route", "show", "default"], text=True)
        ip  = out.strip().split()[2]          # "default via <IP> dev eth0"
        print(f"[CONFIG] Host IP from ip route: {ip}")
        return ip
    except Exception as e:
        print(f"[WARN]  ip route failed: {e}")

    # 3. Hard-coded fallback
    ip = "172.17.48.1"
    print(f"[CONFIG] Using fallback IP: {ip}")
    return ip


WINDOWS_HOST_IP = get_windows_host_ip()
BACKEND_URL     = f"http://{WINDOWS_HOST_IP}:5000"
print(f"[CONFIG] Flask backend → {BACKEND_URL}")


# ─────────────────────────────────────────────────────────────
#  STARTUP CONNECTIVITY CHECK
# ─────────────────────────────────────────────────────────────

def check_backend_reachable() -> bool:
    try:
        r = requests.get(f"{BACKEND_URL}/ping", timeout=3)
        print(f"[CONFIG] ✅ Backend reachable — HTTP {r.status_code}")
        return True
    except requests.exceptions.ConnectionError:
        print(f"[CONFIG] ❌ Cannot reach Flask at {BACKEND_URL}")
        print( "[CONFIG]    → Start Flask: python app.py  (Windows, host='0.0.0.0')")
        print( "[CONFIG]    → Allow port 5000 in Windows Firewall")
        return False


check_backend_reachable()


# ─────────────────────────────────────────────────────────────
#  SPARK SESSION
# ─────────────────────────────────────────────────────────────

spark = SparkSession.builder \
    .appName("AeroGuard-CollisionDetection") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")


# ─────────────────────────────────────────────────────────────
#  KAFKA STREAM
# ─────────────────────────────────────────────────────────────

raw_df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe",               "plane-data") \
    .option("startingOffsets",         "latest") \
    .load()


# ─────────────────────────────────────────────────────────────
#  SCHEMA + PARSE
# ─────────────────────────────────────────────────────────────

plane_schema = StructType() \
    .add("planeId",   StringType()) \
    .add("lat",       DoubleType()) \
    .add("lon",       DoubleType()) \
    .add("altitude",  IntegerType()) \
    .add("speed",     IntegerType())

planes_df = raw_df \
    .selectExpr("CAST(value AS STRING) AS value") \
    .select(from_json(col("value"), plane_schema).alias("d")) \
    .select("d.*")


# ─────────────────────────────────────────────────────────────
#  COLLISION THRESHOLDS
#
#  DIST_THRESHOLD : horizontal distance in degrees
#    0.1° ≈ 11 km  — use 0.5° for easier testing with spread data
#
#  ALT_THRESHOLD  : vertical separation in feet
#    3500 ft is standard separation minimum
# ─────────────────────────────────────────────────────────────

DIST_THRESHOLD = 0.1    # degrees  — relaxed for testing (old producer data spreads planes)
ALT_THRESHOLD  = 800   # feet     — relaxed so altitude spread doesn't block all detections


# ─────────────────────────────────────────────────────────────
#  GLOBAL STATE  (lives in the Spark driver process)
# ─────────────────────────────────────────────────────────────

plane_state      = {}   # planeId  → Row  (latest position)
collision_status = {}   # pair     → bool (True = currently colliding)
last_post_time   = {}   # pair     → float (epoch of last ONGOING POST)

ONGOING_THROTTLE_SEC = 10   # minimum seconds between ONGOING heartbeats


# ─────────────────────────────────────────────────────────────
#  HTTP HELPER
# ─────────────────────────────────────────────────────────────

def safe_post(endpoint: str, payload, label: str = "") -> bool:
    url = f"{BACKEND_URL}{endpoint}"
    try:
        res = requests.post(url, json=payload, timeout=5)
        print(f"[POST ✅] {label:20s} → HTTP {res.status_code} | {res.text[:60]}")
        return True
    except requests.exceptions.ConnectionError as e:
        print(f"[POST ❌] {label} → ConnectionError: {e}")
        print(f"          Is Flask running at {BACKEND_URL}?")
    except requests.exceptions.Timeout:
        print(f"[POST ⏱] {label} → Timed out after 5 s")
    except Exception as e:
        print(f"[POST ❌] {label} → {type(e).__name__}: {e}")
    return False


# ─────────────────────────────────────────────────────────────
#  BATCH PROCESSOR  (called by foreachBatch)
# ─────────────────────────────────────────────────────────────

def detect_collision(batch_df, batch_id):
    """
    Called once per micro-batch.

    Steps:
      1. Update plane_state with latest rows from this batch.
      2. POST all current positions to /flights.
      3. Compute distance + altitude diff for every pair.
      4. Print diagnostic table so you can see why pairs collide or not.
      5. Diff against collision_status → fire NEW / ONGOING / ENDED.
      6. Update collision_status.
    """
    global plane_state, collision_status, last_post_time

    rows = batch_df.collect()
    if not rows:
        return

    # ── 1. Update positions ─────────────────────────────────
    for row in rows:
        if row.planeId:
            plane_state[row.planeId] = row

    planes = list(plane_state.values())
    n      = len(planes)

    if n < 2:
        print(f"[Batch {batch_id}] Only {n} plane known — need ≥ 2 for collision check")
        # Still post flights
        payload = []
        for p in planes:
            pd = p.asDict()
            pd["risk"] = "LOW"
            payload.append(pd)
        safe_post("/flights", payload, label="FLIGHTS")
        return

    # ── 3. Compute all pair metrics & Graph Degree ───────────
    current_pairs = {}   # pair → bool
    pair_metrics  = {}   # pair → (dist, alt_d)
    degrees       = {p.planeId: 0 for p in planes}

    for i in range(n):
        for j in range(i + 1, n):
            p1   = planes[i]
            p2   = planes[j]
            pair = tuple(sorted([p1.planeId, p2.planeId]))

            dist  = ((p1.lat - p2.lat) ** 2 + (p1.lon - p2.lon) ** 2) ** 0.5
            alt_d = abs(p1.altitude - p2.altitude)

            is_col = dist < DIST_THRESHOLD and alt_d < ALT_THRESHOLD
            current_pairs[pair] = is_col
            pair_metrics[pair]  = (dist, alt_d)
            
            if is_col:
                degrees[p1.planeId] += 1
                degrees[p2.planeId] += 1

    # ── 2. Send all flights to Flask with Risk ────────────────
    payload = []
    for p in planes:
        pd = p.asDict()
        deg = degrees[p.planeId]
        if deg >= 2:
            pd["risk"] = "HIGH"
        elif deg == 1:
            pd["risk"] = "MEDIUM"
        else:
            pd["risk"] = "LOW"
        payload.append(pd)
        
    safe_post("/flights", payload, label="FLIGHTS")

    # ── 4. Diagnostic table (every batch) ───────────────────
    total_pairs     = len(current_pairs)
    colliding_pairs = sum(1 for v in current_pairs.values() if v)
    print(f"\n[Batch {batch_id}] Planes: {[p.planeId for p in planes]}")
    print(f"  Thresholds → dist < {DIST_THRESHOLD:.1f}°  |  alt < {ALT_THRESHOLD:,} ft")
    print(f"  {'PAIR':<12} {'DIST (°)':>10} {'ALT DIFF (ft)':>14} {'COLLIDING':>10}")
    print(f"  {'─'*12} {'─'*10} {'─'*14} {'─'*10}")
    for pair, (dist, alt_d) in sorted(pair_metrics.items()):
        col_str = "💥 YES" if current_pairs[pair] else "no"
        mark_d  = "✓" if dist  < DIST_THRESHOLD else f"✗>{DIST_THRESHOLD}"
        mark_a  = "✓" if alt_d < ALT_THRESHOLD  else f"✗>{ALT_THRESHOLD}"
        print(f"  {pair[0]+' & '+pair[1]:<12} {dist:>9.4f}{mark_d}  {alt_d:>7,} ft{mark_a}  {col_str:>10}")
    print(f"  → {colliding_pairs}/{total_pairs} pairs colliding")

    # ── 5. Fire state-change events ─────────────────────────
    now = time.time()

    for pair, is_col in current_pairs.items():
        was_col = collision_status.get(pair, False)

        # ── NEW ──────────────────────────────────────────────
        if is_col and not was_col:
            print(f"\n🚨 NEW Collision    : {pair[0]} & {pair[1]}")
            safe_post("/collision", {
                "plane1": pair[0],
                "plane2": pair[1],
                "status": "NEW",
                "time":   time.strftime("%H:%M:%S"),
            }, label="NEW COLLISION")
            last_post_time[pair] = now

        # ── ONGOING (throttled to every 10 s) ─────────────────
        elif is_col and was_col:
            if now - last_post_time.get(pair, 0) > ONGOING_THROTTLE_SEC:
                print(f"⚠️  Ongoing Collision: {pair[0]} & {pair[1]}")
                safe_post("/collision", {
                    "plane1": pair[0],
                    "plane2": pair[1],
                    "status": "ONGOING",
                    "time":   time.strftime("%H:%M:%S"),
                }, label="ONGOING COLLISION")
                last_post_time[pair] = now

        # ── ENDED ─────────────────────────────────────────────
        elif not is_col and was_col:
            print(f"✅ Collision Ended  : {pair[0]} & {pair[1]}")
            safe_post("/collision", {
                "plane1": pair[0],
                "plane2": pair[1],
                "status": "ENDED",
                "time":   time.strftime("%H:%M:%S"),
            }, label="ENDED COLLISION")
            last_post_time.pop(pair, None)

    # ── 6. Persist only currently-active pairs ───────────────
    collision_status = {p: True for p, v in current_pairs.items() if v}


# ─────────────────────────────────────────────────────────────
#  START STREAMING QUERY
# ─────────────────────────────────────────────────────────────

query = planes_df.writeStream \
    .foreachBatch(detect_collision) \
    .option("checkpointLocation", "/tmp/aeroguard_checkpoint") \
    .start()

print("[Spark] ✅ Streaming started — waiting for plane data…")
query.awaitTermination()