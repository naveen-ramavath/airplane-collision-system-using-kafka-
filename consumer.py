from kafka import KafkaConsumer
import json
import math

consumer = KafkaConsumer(
    'plane-data',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

planes = {}

def calculate_distance(p1, p2):
    return math.sqrt((p1['lat'] - p2['lat'])**2 + (p1['lon'] - p2['lon'])**2)

for message in consumer:
    data = message.value
    planes[data['planeId']] = data

    print("Received:", data)

    # Check collision
    for id1 in planes:
        for id2 in planes:
            if id1 != id2:
                p1 = planes[id1]
                p2 = planes[id2]

                distance = calculate_distance(p1, p2)
                altitude_diff = abs(p1['altitude'] - p2['altitude'])

                if distance < 0.05 and altitude_diff < 1000:
                    print(f"⚠️ Collision Risk between {id1} and {id2}")