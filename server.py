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
import requests
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

LLAMA_URL = "http://raspberrypi.local:18081/completion"
N_PREDICT = 200

STATIC_DIR = os.path.dirname(os.path.abspath(__file__))

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")
CORS(app)

# Latest sensor snapshot (updated by POST /sensors)
latest_sensors = {}


# ── Frontend static files ─────────────────────────────────────────────────────

@app.route("/")
def index():
    return send_from_directory(STATIC_DIR, "index.html")


# ── Sensor endpoints ──────────────────────────────────────────────────────────

@app.route("/sensors", methods=["POST"])
def receive_sensors():
    """Devices POST their sensor JSON here."""
    data = request.get_json(force=True, silent=True)
    if not isinstance(data, dict):
        return jsonify({"error": "Expected a JSON object"}), 400
    latest_sensors.update(data)
    return jsonify({"ok": True})


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
    app.run(host="0.0.0.0", port=5000, debug=False)
