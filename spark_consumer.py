from pyspark.sql import SparkSession
from pyspark.sql.functions import col, from_json
from pyspark.sql.types import *
import time
import requests

# Create Spark session
spark = SparkSession.builder \
    .appName("AirplaneCollision") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

# Kafka stream
df = spark.readStream \
    .format("kafka") \
    .option("kafka.bootstrap.servers", "localhost:9092") \
    .option("subscribe", "plane-data") \
    .option("startingOffsets", "earliest") \
    .load()

# Schema
schema = StructType() \
    .add("planeId", StringType()) \
    .add("lat", DoubleType()) \
    .add("lon", DoubleType()) \
    .add("altitude", IntegerType()) \
    .add("speed", IntegerType())

# Convert JSON
json_df = df.selectExpr("CAST(value AS STRING)") \
    .select(from_json(col("value"), schema).alias("data")) \
    .select("data.*")

# ✅ GLOBAL STATE (IMPORTANT)
plane_state = {}
collision_status = {}
last_print_time = {}

# Collision logic
def detect_collision(batch_df, batch_id):
    global plane_state, collision_status, last_print_time

    new_data = batch_df.collect()

    # update latest positions
    for p in new_data:
        plane_state[p.planeId] = p

    planes = list(plane_state.values())

    if len(planes) < 2:
        return

    current_pairs = {}

    for i in range(len(planes)):
        for j in range(i + 1, len(planes)):
            p1 = planes[i]
            p2 = planes[j]

            pair = tuple(sorted([p1.planeId, p2.planeId]))

            is_collision = (
                abs(p1.lat - p2.lat) < 0.9 and
                abs(p1.lon - p2.lon) < 0.9 and
                abs(p1.altitude - p2.altitude) < 2700
            )

            current_pairs[pair] = is_collision

    
    # Compare with previous state
   

    for pair, is_collision in current_pairs.items():
        prev = collision_status.get(pair, False)
        now = time.time()

        # NEW collision
        if is_collision and not prev:
            print(f"\n🚨 NEW Collision: {pair[0]} & {pair[1]}")

            # send to backend
            requests.post("http://localhost:5000/collision", json={
                "plane1": pair[0],
                "plane2": pair[1],
                "status": "NEW",
                "time": time.strftime("%H:%M:%S")
            })

            last_print_time[pair] = now

        # ONGOING (print every 5 sec only)
        elif is_collision and prev:
            last_time = last_print_time.get(pair, 0)

            if now - last_time > 15:   # 🔥 control frequency
                print(f"⚠️ Ongoing Collision: {pair[0]} & {pair[1]}")
                last_print_time[pair] = now

                requests.post("http://localhost:5000/collision", json={
                    "plane1": pair[0],
                    "plane2": pair[1],
                    "status": "ONGOING",
                    "time": time.strftime("%H:%M:%S")
                })

        # ENDED
        elif not is_collision and prev:
            print(f"✅ Collision Ended: {pair[0]} & {pair[1]}")
            if pair in last_print_time:
                del last_print_time[pair]
            
            requests.post("http://localhost:5000/collision", json={
                "plane1": pair[0],
                "plane2": pair[1],
                "status": "ENDED",
                "time": time.strftime("%H:%M:%S")
            })

    # update state
    collision_status = current_pairs


# Start streaming
query = json_df.writeStream \
    .foreachBatch(detect_collision) \
    .start()

query.awaitTermination()