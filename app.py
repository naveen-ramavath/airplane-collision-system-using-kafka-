from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

collisions = []

@app.route('/collision', methods=['POST'])
def receive_collision():
    data = request.json

    # avoid duplicates
    if data not in collisions:
        collisions.append(data)

    return jsonify({"status": "received"})

@app.route('/collisions', methods=['GET'])
def get_collisions():
    return jsonify(collisions)

if __name__ == '__main__':
    app.run(debug=True, port=5000)