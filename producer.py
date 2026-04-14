from kafka import KafkaProducer
import json
import time
import random

producer = KafkaProducer(
    bootstrap_servers='localhost:9092',
    value_serializer=lambda v: json.dumps(v).encode('utf-8')
)

planes = ["A1", "B1", "C1"]

while True:
    data = {
        "planeId": random.choice(planes),
        "lat": round(17.3 + random.random(), 3),
        "lon": round(78.4 + random.random(), 3),
        "altitude": random.randint(28000, 35000),
        "speed": random.randint(700, 900)
    }

    producer.send('plane-data', value=data)
    print("Sent:", data)

    time.sleep(1)