from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import time

app = Flask(__name__, static_folder='frontend', static_url_path='')
CORS(app)

# ─────────────────────────────────────────
#  SERVE FRONTEND
# ─────────────────────────────────────────

@app.route('/')
def home():
    return send_from_directory('frontend', 'index.html')


# ─────────────────────────────────────────
#  HEALTH CHECK
# ─────────────────────────────────────────

@app.route('/ping', methods=['GET'])
def ping():
    return jsonify({"status": "ok", "message": "Flask is alive"})


# ─────────────────────────────────────────
#  FLIGHT STORAGE
#  Defined first so /stats can reference it safely.
# ─────────────────────────────────────────

flights_dict = {}   # planeId → latest plane dict

@app.route('/flights', methods=['POST'])
def receive_flights():
    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No data received"}), 400
        if not isinstance(data, list):
            return jsonify({"error": "Expected a list of planes"}), 400

        for plane in data:
            if "planeId" in plane:
                flights_dict[plane['planeId']] = plane

        print(f"✈️  Flights updated: {len(flights_dict)} planes tracked")
        return jsonify({"status": "received", "count": len(flights_dict)})

    except Exception as e:
        print("❌ Error in /flights:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/flights', methods=['GET'])
def get_flights():
    return jsonify(list(flights_dict.values()))


# ─────────────────────────────────────────
#  COLLISION STORAGE
#
#  collisions_dict  — active collisions (NEW or ONGOING)
#     key:  (plane1, plane2) sorted tuple
#     val:  { plane1, plane2, status, time }
#
#  ended_dict       — recently resolved, kept for 30 s display
#     key:  same tuple
#     val:  { ..., "ended_at": epoch }
#
#  Cumulative counters (never reset while server runs):
#     total_new       — +1 each time a NEW event arrives
#     total_ongoing   — +1 each ONGOING heartbeat received
#     total_resolved  — +1 each time an ENDED event arrives
# ─────────────────────────────────────────

collisions_dict = {}
ended_dict      = {}

ENDED_TTL_SEC = 30   # how long ENDED cards stay visible in the UI

total_new      = 0
total_ongoing  = 0
total_resolved = 0


def _purge_expired_ended():
    """Remove ENDED entries older than ENDED_TTL_SEC."""
    now    = time.time()
    to_del = [k for k, v in ended_dict.items()
              if now - v.get("ended_at", now) > ENDED_TTL_SEC]
    for k in to_del:
        del ended_dict[k]


@app.route('/collision', methods=['POST'])
def receive_collision():
    global total_new, total_ongoing, total_resolved

    try:
        data = request.get_json(force=True)

        if not data:
            return jsonify({"error": "No data received"}), 400
        if "plane1" not in data or "plane2" not in data:
            return jsonify({"error": "Missing plane1 or plane2"}), 400

        pair_key = tuple(sorted([data['plane1'], data['plane2']]))
        status   = data.get("status", "NEW")

        # ── NEW ──────────────────────────────────────────────
        if status == "NEW":
            total_new += 1
            collisions_dict[pair_key] = {
                "plane1": data['plane1'],
                "plane2": data['plane2'],
                "status": "NEW",
                "time":   data.get("time", ""),
            }
            ended_dict.pop(pair_key, None)   # clear any old ENDED entry
            print(f"🚨 NEW  [{pair_key}]  total_new={total_new}")

        # ── ONGOING ──────────────────────────────────────────
        elif status == "ONGOING":
            total_ongoing += 1
            if pair_key in collisions_dict:
                collisions_dict[pair_key]["status"] = "ONGOING"
                collisions_dict[pair_key]["time"]   = data.get("time", "")
            else:
                # We missed the NEW — create the entry now
                total_new += 1
                collisions_dict[pair_key] = {
                    "plane1": data['plane1'],
                    "plane2": data['plane2'],
                    "status": "ONGOING",
                    "time":   data.get("time", ""),
                }
            print(f"⚠️  ONGOING [{pair_key}]  total_ongoing={total_ongoing}")

        # ── ENDED ─────────────────────────────────────────────
        elif status == "ENDED":
            total_resolved += 1
            removed = collisions_dict.pop(pair_key, None)
            if removed:
                removed["status"]   = "ENDED"
                removed["time"]     = data.get("time", "")
                removed["ended_at"] = time.time()
                ended_dict[pair_key] = removed
            print(f"✅ ENDED [{pair_key}]  total_resolved={total_resolved}")

        _purge_expired_ended()

        return jsonify({"status": "received",
                        "pair":   list(pair_key),
                        "event":  status})

    except Exception as e:
        print("❌ Error in /collision:", e)
        return jsonify({"error": str(e)}), 500


@app.route('/collisions', methods=['GET'])
def get_collisions():
    """Return active (NEW/ONGOING) + recently ENDED collisions."""
    _purge_expired_ended()
    active = list(collisions_dict.values())
    ended  = list(ended_dict.values())
    # Don't serialize internal 'ended_at' field
    for e in ended:
        e.pop("ended_at", None)
    return jsonify(active + ended)


# ─────────────────────────────────────────
#  STATS
# ─────────────────────────────────────────

@app.route('/stats', methods=['GET'])
def get_stats():
    return jsonify({
        "active_flights":    len(flights_dict),
        "active_collisions": len(collisions_dict),
        "total_new":         total_new,
        "total_ongoing":     total_ongoing,
        "total_resolved":    total_resolved,
    })


# ─────────────────────────────────────────
#  DEBUG
# ─────────────────────────────────────────

@app.route('/debug', methods=['GET'])
def debug_view():
    _purge_expired_ended()
    return jsonify({
        "flights_count":     len(flights_dict),
        "active_collisions": len(collisions_dict),
        "ended_count":       len(ended_dict),
        "total_new":         total_new,
        "total_ongoing":     total_ongoing,
        "total_resolved":    total_resolved,
        "flights":           list(flights_dict.values()),
        "collisions":        list(collisions_dict.values()),
        "ended":             [dict(v, ended_at=None) for v in ended_dict.values()],
    })


# ─────────────────────────────────────────
#  RUN
# ─────────────────────────────────────────

if __name__ == '__main__':
    print("🚀 Flask starting on http://0.0.0.0:5000")
    print("   Endpoints: /ping  /flights  /collisions  /collision  /stats  /debug")
    app.run(host='0.0.0.0', port=5000, debug=False)