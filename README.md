# Safe Tank — Sensor Dashboard

A real-time sensor monitoring dashboard with an AI chat interface, powered by a Raspberry Pi (QNX OS) and a local LLM.

## Architecture

```
[Pi: sensor-collection.py] → writes → /tmp/sensor_data.json
[Pi: sensor-endpoint.py]   → serves → GET :8080/sensors
[Laptop: server.py]        → polls Pi every 2s → serves dashboard on :5000
[Browser]                  → polls server.py GET /sensors + POST /query for AI chat
```

## Prerequisites

- Python 3
- Connected to the same Wi-Fi hotspot as the Raspberry Pi (Pi IP: `172.20.10.6`)

## Local Setup (your laptop)

1. Install dependencies:

   ```bash
   pip install flask flask-cors requests
   ```

2. Verify you can reach the Pi:

   ```bash
   ping 172.20.10.6
   ```

3. Start the server:

   ```bash
   python server.py
   ```

4. Open `http://localhost:5000` in your browser.

## Raspberry Pi Setup

### Hardware

- Raspberry Pi (running QNX OS)
- DHT11 sensor (temperature + humidity) connected to GPIO 17
- Vibration sensor connected to GPIO 16
- LED indicators: green on GPIO 27, red on GPIO 18

### Software Dependencies

```bash
pip install rpi_gpio
```

No other pip packages are required — `sensor-endpoint.py` uses only Python stdlib.

### Files to Copy to the Pi

- `sensor-collection.py`
- `sensor-endpoint.py`

### Running

SSH into the Pi and run both scripts:

```bash
python sensor-endpoint.py &
python sensor-collection.py
```

- `sensor-collection.py` reads the DHT11 (temperature/humidity) and vibration sensor, writing results to `/tmp/sensor_data.json`.
- `sensor-endpoint.py` serves that data over HTTP on port 8080.

The data file is automatically overwritten when it exceeds 64 KB or after 5 minutes, whichever comes first.

### (Optional) LLM Server

To enable the AI chat feature, run llama-server on the Pi:

```bash
llama-server --port 18081 --model <path-to-model.gguf>
```

This listens on port 18081 and accepts completion requests from `server.py`.

## AI Chat

The "Ask the AI" feature requires llama-server running on the Pi:

```
http://172.20.10.6:18081
```

If it's not running, sensor data still displays but the chat will return connection errors.

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Dashboard shows "Disconnected" | Browser can't reach server.py | Make sure `python server.py` is running and you're hitting `localhost:5000` |
| Sensor values stay at "—" | Pi not reachable | Confirm you're on the hotspot, ping `172.20.10.6`, check `sensor-endpoint.py` is running |
| AI chat returns errors | llama-server not running | Start llama-server on the Pi (port 18081) |
| Sensor file grows too large | Shouldn't happen | `sensor-collection.py` auto-resets at 64 KB or 5 min intervals |
