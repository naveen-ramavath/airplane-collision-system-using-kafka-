"""
AeroGuard — Kafka Producer  (v3 — directional flight paths)
============================================================
7 planes, ALL starting at the same point.
Each plane has a UNIQUE heading so they spread out in different
directions naturally. As they move, different pairs come into
proximity → collision → separation → new collisions.

Run with:  python producer.py
Stop with: Ctrl+C
"""

from kafka import KafkaProducer
import json
import time
import random
import math

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

# ─────────────────────────────────────────────────────────────
#  7 PLANES — no zones, no groups, free airspace
# ─────────────────────────────────────────────────────────────
PLANE_IDS = ["A1", "B1", "C1", "D1", "E1", "F1", "G1"]

# All planes start at the SAME point
# (guarantees every pair starts in collision range)
START_LAT = 17.25
START_LON = 78.25
START_ALT = 31000

# Each plane gets a unique heading (evenly spread around 360°)
# so they fan out in different directions
num_planes = len(PLANE_IDS)
headings   = {
    pid: (360 / num_planes) * i
    for i, pid in enumerate(PLANE_IDS)
}

# Speed of movement (degrees per second)
# Small enough that collisions persist across batches
SPEED = 0.004   # ~0.4 km/s at equator

positions = {}
for pid in PLANE_IDS:
    positions[pid] = {
        "lat":      START_LAT,
        "lon":      START_LON,
        "altitude": START_ALT + random.randint(-500, 500),
        "heading":  headings[pid],
    }

print("=" * 60)
print("  ✈  AeroGuard Producer  —  v3 Directional")
print("=" * 60)
print(f"  Planes   : {PLANE_IDS}")
print(f"  Start    : ({START_LAT}, {START_LON}), alt ~{START_ALT:,} ft")
print(f"  Headings : {' | '.join(f'{p}={headings[p]:.0f}°' for p in PLANE_IDS)}")
print(f"  Speed    : {SPEED} deg/s (with small random drift)")
print(f"  Strategy : planes start together → fan out → cross paths")
print("=" * 60)
print("  Starting stream — all 7 planes active simultaneously")
print("  Ctrl+C to stop\n")

# ─────────────────────────────────────────────────────────────
#  STREAM LOOP
# ─────────────────────────────────────────────────────────────
cycle = 0
while True:
    cycle += 1

    for plane in PLANE_IDS:
        pos     = positions[plane]
        heading = pos["heading"]

        # Move in current heading direction + small random wobble
        heading_rad = math.radians(heading)
        wobble      = random.uniform(-10, 10)           # ±10° wobble

        pos["lat"] = round(
            pos["lat"] + SPEED * math.cos(heading_rad) + random.uniform(-0.001, 0.001),
            4
        )
        pos["lon"] = round(
            pos["lon"] + SPEED * math.sin(heading_rad) + random.uniform(-0.001, 0.001),
            4
        )
        pos["altitude"] = max(25000, min(40000,
            pos["altitude"] + random.randint(-100, 100)
        ))
        pos["heading"] = (heading + wobble) % 360

        # Occasionally reverse direction so planes come back and re-collide
        if random.random() < 0.02:      # 2% chance per cycle
            pos["heading"] = (pos["heading"] + 180) % 360

        data = {
            "planeId":  plane,
            "lat":      pos["lat"],
            "lon":      pos["lon"],
            "altitude": pos["altitude"],
            "speed":    random.randint(700, 900),
        }

        producer.send("plane-data", value=data)
        print(f"  [{cycle:04d}] ✈ {plane}  "
              f"lat={pos['lat']:.4f}  lon={pos['lon']:.4f}  "
              f"alt={pos['altitude']:,}ft  hdg={pos['heading']:.0f}°")

    print()
    time.sleep(1)