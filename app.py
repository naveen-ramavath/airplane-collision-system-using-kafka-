from flask import Flask, jsonify
from kafka import KafkaConsumer
from flask_cors import CORS
import json
import threading

app = Flask(__name__)
CORS(app)
planes = {}
alerts = []

def consume_data():
    consumer = KafkaConsumer(
        'plane-data',
        bootstrap_servers='localhost:9092',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for message in consumer:
        data = message.value
        planes[data['planeId']] = data

        # simple collision check
        ids = list(planes.keys())
        for i in range(len(ids)):
            for j in range(i+1, len(ids)):
                p1 = planes[ids[i]]
                p2 = planes[ids[j]]

                distance = ((p1['lat'] - p2['lat'])**2 + (p1['lon'] - p2['lon'])**2) ** 0.5
                altitude_diff = abs(p1['altitude'] - p2['altitude'])

                if distance < 0.05 and altitude_diff < 1000:
                    alert = f"⚠️ Collision Risk between {ids[i]} and {ids[j]}"
                    if alert not in alerts:
                        alerts.append(alert)

# run consumer in background
threading.Thread(target=consume_data, daemon=True).start()

@app.route("/planes")
def get_planes():
    return jsonify(list(planes.values()))

@app.route("/alerts")
def get_alerts():
    return jsonify(alerts)

if __name__ == "__main__":
    app.run(debug=True)