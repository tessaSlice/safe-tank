#!/usr/bin/env python3
"""
HTTP endpoint for the Raspberry Pi (QNX OS).
Serves the latest sensor readings from the file written by sensor-collection.py.

Endpoints:
  GET /sensors  — returns the most recent reading as JSON
  GET /history  — returns all readings currently in the buffer file

Run alongside sensor-collection.py:
    python sensor-endpoint.py &
    python sensor-collection.py
"""

import json
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

SENSOR_DATA_FILE = "/tmp/sensor_data.json"
PORT = 8080


class SensorHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/sensors":
            self._serve_latest()
        elif self.path == "/history":
            self._serve_all()
        else:
            self._respond(404, {"error": "Not found"})

    def _serve_latest(self):
        data = self._read_file()
        if data is None:
            self._respond(503, {"error": "No sensor data available yet"})
            return
        readings = data.get("readings", [])
        if not readings:
            self._respond(503, {"error": "No sensor data available yet"})
            return
        self._respond(200, readings[-1])

    def _serve_all(self):
        data = self._read_file()
        if data is None:
            self._respond(200, {"readings": []})
            return
        self._respond(200, data)

    def _read_file(self):
        if not os.path.exists(SENSOR_DATA_FILE):
            return None
        try:
            with open(SENSOR_DATA_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return None

    def _respond(self, status, body):
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format, *args):
        pass


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", PORT), SensorHandler)
    print(f"Sensor endpoint listening on port {PORT}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
