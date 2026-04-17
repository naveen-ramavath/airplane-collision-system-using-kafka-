from kafka import KafkaProducer
import json
import time
import random

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

planes = ["A1", "B1", "C1", "D1", "E1"]

# store last positions (to simulate movement)
positions = {
    p: {
        "lat": random.uniform(17.0, 18.0),
        "lon": random.uniform(78.0, 79.0),
        "altitude": random.randint(29000, 35000)
    }
    for p in planes
}

while True:
    plane = random.choice(planes)

    # small movement (realistic)
    positions[plane]["lat"] += random.uniform(-0.05, 0.05)
    positions[plane]["lon"] += random.uniform(-0.05, 0.05)
    positions[plane]["altitude"] += random.randint(-500, 500)

    data = {
        "planeId": plane,
        "lat": round(positions[plane]["lat"], 3),
        "lon": round(positions[plane]["lon"], 3),
        "altitude": positions[plane]["altitude"],
        "speed": random.randint(700, 900)
    }

    producer.send('plane-data', value=data)
    print("Sent:", data)

    time.sleep(1)