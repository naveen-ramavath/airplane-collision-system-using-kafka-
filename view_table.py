from kafka import KafkaConsumer
import json

consumer = KafkaConsumer(
    'plane-data',
    bootstrap_servers='localhost:9092',
    value_deserializer=lambda x: json.loads(x.decode('utf-8'))
)

print("PlaneID | Latitude | Longitude | Altitude | Speed")
print("--------------------------------------------------")

for msg in consumer:
    d = msg.value
    print(f"{d['planeId']} | {d['lat']} | {d['lon']} | {d['altitude']} | {d['speed']}")