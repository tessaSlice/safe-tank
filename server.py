"""
Bridge server for the sensor dashboard.

Endpoints:
  POST /sensors  — Pi (or any device) pushes a JSON blob of all sensor readings
  GET  /sensors  — Frontend polls this to get the latest readings
  POST /query    — Frontend sends {query} → server forwards to llama-server → returns {response}

Run:
    pip install flask flask-cors requests
    python server.py
"""

import os
import time
import threading
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

"""
curl http://172.20.10.6:18081/completion \
  -X POST \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello from the server!", "n_predict":32}'
"""

LLAMA_URL = "http://172.20.10.6:18081/completion"
N_PREDICT = 200

PI_SENSOR_URL = "http://172.20.10.6:8080/sensors"
PI_POLL_INTERVAL_S = 2

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app)

# Latest sensor snapshot (updated by polling the Pi)
latest_sensors = {}


# ── Frontend static files ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ── Sensor polling (pulls from Pi) ────────────────────────────────────────────

def _poll_pi_sensors():
    """Background thread that pulls sensor data from the Pi."""
    while True:
        try:
            resp = requests.get(PI_SENSOR_URL, timeout=5)
            if resp.ok:
                data = resp.json()
                if isinstance(data, dict):
                    latest_sensors.update(data)
        except Exception:
            pass
        time.sleep(PI_POLL_INTERVAL_S)


@app.route("/sensors", methods=["GET"])
def get_sensors():
    """Frontend polls here to get the latest sensor snapshot."""
    return jsonify(latest_sensors)


# ── LLM endpoint ─────────────────────────────────────────────────────────────

def build_prompt(query: str, sensor_data: dict) -> str:
    lines = ["You are an assistant monitoring environmental sensors.",
             "Current readings:"]
    if "temperature" in sensor_data:
        lines.append(f"  Temperature : {sensor_data['temperature']} °C")
    if "humidity" in sensor_data:
        lines.append(f"  Humidity    : {sensor_data['humidity']} %")
    if "gas" in sensor_data:
        lines.append(f"  Gas (ppm)   : {sensor_data['gas']}")
    if "vibration" in sensor_data:
        lines.append(f"  Vibration   : {'detected' if sensor_data['vibration'] else 'none'}")
    lines.append(f"\nUser question: {query}\nAnswer concisely:")
    return "\n".join(lines)


@app.route("/query", methods=["POST"])
def query():
    """Frontend POSTs {query} here; server adds sensor context and calls llama-server."""
    body = request.get_json(force=True, silent=True) or {}
    user_query = body.get("query", "").strip()
    if not user_query:
        return jsonify({"error": "query field is required"}), 400

    prompt = build_prompt(user_query, latest_sensors)

    try:
        llama_resp = requests.post(
            LLAMA_URL,
            json={"prompt": prompt, "n_predict": N_PREDICT},
            timeout=60,
        )
        llama_resp.raise_for_status()
        content = llama_resp.json().get("content", "").strip()
    except requests.exceptions.ConnectionError:
        return jsonify({"error": "Cannot reach llama-server on port 18081. Is it running?"}), 502
    except requests.exceptions.Timeout:
        return jsonify({"error": "llama-server timed out"}), 504
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify({"response": content})


if __name__ == "__main__":
    poller = threading.Thread(target=_poll_pi_sensors, daemon=True)
    poller.start()
    app.run(host="0.0.0.0", port=5000, debug=False)
