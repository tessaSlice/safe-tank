const CONFIG = {
  // Base URL of the bridge server (server.py)
  serverUrl: "http://localhost:5000",

  // How often (ms) the frontend polls for new sensor data
  pollIntervalMs: 2000,

  // Thresholds for warning/danger colors on each sensor
  thresholds: {
    humidity:    { warn: 70,  danger: 85  },  // %
    temperature: { warn: 35,  danger: 40  },  // °C
    gas:         { warn: 300, danger: 600 },  // ppm (adjust to your sensor)
  },

  // Set to true to use live server data, false to show demo values
  liveMode: true,
};
