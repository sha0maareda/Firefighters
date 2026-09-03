# 🔥 Smart Fire Fighting System using IoT

An IoT-based fire detection and suppression system designed for high-risk industrial environments (steel/iron factories, chemical storage facilities, fuel and flammable material warehouses). The facility is divided into independently monitored **zones**, each capable of detecting and reacting to fire **locally and instantly**, while also communicating with a **central monitoring unit** and **neighboring zones** over the network.

---

## 🎯 Problem Statement

Large industrial facilities with high fire risk (factories, chemical plants, fuel storage areas) need a fire response system that is:
- **Fast** — reacts to fire within the zone itself, without waiting on a network round-trip
- **Resilient** — keeps working even if the network/connectivity goes down
- **Aware** — notifies the central management team immediately so they can respond
- **Preventive** — warns neighboring zones early to reduce the risk of fire spreading
- **Data-driven** — logs every fire incident so the facility can analyze root causes and improve safety over time

---

## 🧠 System Architecture

The facility is divided into multiple **zones**. Each zone has its own embedded fire-detection circuit, and all zones report to a **central unit** (factory management/monitoring room).

```
                    ┌─────────────────────────┐
                    │      Central Unit         │
                    │  (Node-RED Dashboard +    │
                    │   HiveMQ Cloud Broker)    │
                    └────────────┬──────────────┘
                                 │  MQTT (telemetry + alerts)
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
   ┌────▼─────┐            ┌────▼─────┐            ┌────▼─────┐
   │  Zone 1   │  <──────>  │  Zone 2   │  <──────>  │  Zone 3   │
   │  (ESP32)  │  neighbor  │  (ESP32)  │  neighbor  │  (ESP32)  │
   └───────────┘   alerts   └───────────┘   alerts   └───────────┘
```

### How each zone behaves

1. **Continuously reads sensors** — flame sensor + NTC temperature sensor
2. **Reacts locally the instant fire is detected** — no network dependency:
   - Activates a relay (connected to an extinguisher / solenoid valve)
   - Sounds a local buzzer + lights a local alarm LED
3. **Publishes an MQTT alert immediately** to the central unit so the response team can be dispatched
4. **Publishes periodic telemetry** (temperature, flame status) regardless of fire state, so the dashboard always shows live conditions
5. **Warns neighboring zones** over MQTT the moment fire is detected, so they can take precautions before the fire spreads
6. **Logs every fire event** (zone, timestamp, sensor readings) for later data analysis

---

## 🛠️ Hardware Components (per zone)

| Component | Role |
|---|---|
| ESP32 DevKit | Main microcontroller, WiFi + MQTT |
| Flame Sensor (digital) | Detects flame/fire presence |
| NTC Thermistor (10K, Beta 3950) | Measures ambient temperature |
| Relay Module | Triggers the extinguisher / solenoid valve |
| Buzzer | Local audible alarm |
| LED (Alarm) | Indicates fire in this zone |
| LED (Warning) | Indicates fire in a neighboring zone |

> **Simulation note:** This project was simulated on [Wokwi](https://wokwi.com). Since Wokwi doesn't include a real flame sensor part, it was substituted with a digital input (pushbutton/slide switch) that mimics the flame sensor's HIGH/LOW output. The NTC temperature sensor used is Wokwi's `wokwi-ntc-temperature-sensor`, read via the Beta-parameter equation (see `firmware/`).

---

## 💻 Software & Tools

| Tool | Purpose |
|---|---|
| **MicroPython** | Firmware language for the ESP32 zone nodes |
| **HiveMQ Cloud** | MQTT broker connecting zones to the central dashboard |
| **Node-RED** | Central dashboard — live readings, alerts, and data logging |
| **Wokwi** | Circuit simulation and testing environment |

---

## 📁 Repository Structure

```
smart-fire-fighting-iot/
│
├── README.md
│
├── zones/
│   ├── zone1/
│   │   ├── main.py
│   │   ├── diagram.json
│   │   └── wokwi-project.txt
│   │
│   ├── zone2/
│   │   ├── main.py
│   │   ├── diagram.json
│   │   └── wokwi-project.txt
│   │
│   └── zone3/
│       ├── main.py
│       ├── diagram.json
│       └── wokwi-project.txt
│
├── node-red/
│   └── flow.json
│
├── data/
│   └── fire_events.csv
│
└── docs/
    ├── block-diagram.png
    └── dashboard-screenshot.png

```

> All three zone firmware files are identical except for `ZONE_ID`, `NEIGHBOR_ZONES`, and the MQTT client ID — kept as separate files under `firmware/zoneX/` since each runs on a physically separate ESP32 board.

---

## 📡 MQTT Topic Structure

| Topic | Direction | Frequency | Payload Example |
|---|---|---|---|
| `factory/{zone}/telemetry` | Zone → Central | Every 5s (always) | `{"zone":"zone2","flame":false,"temperature":29,"fire_active":false,"timestamp":...}` |
| `factory/{zone}/alert` | Zone → Central & neighbor zones | On event only | `{"zone":"zone2","event":"fire_detected","flame":true,"temperature":63,"timestamp":...}` |

- `telemetry` feeds the **live dashboard readings** (temperature gauge, flame status) — this is sent continuously regardless of fire state.
- `alert` is sent only on a **state change** (`fire_detected` / `fire_cleared`) and triggers dashboard notifications, neighbor-zone warnings, and CSV logging.

---

## ⚙️ Setup & Installation

### 1. Firmware (per zone)
1. Open the Wokwi project (or flash to a real ESP32 with MicroPython installed)
2. Copy `firmware/zoneX/main.py` to the board
3. Update `WIFI_SSID` / `WIFI_PASS` and the HiveMQ Cloud credentials (`MQTT_BROKER`, `MQTT_PORT`, username/password)
4. Run — the board connects to WiFi, connects to the MQTT broker, and starts publishing telemetry every 5 seconds

### 2. MQTT Broker (HiveMQ Cloud)
1. Create a free cluster at [console.hivemq.cloud](https://console.hivemq.cloud)
2. Create credentials under **Access Management**
3. Use the cluster host + port `8883` (TLS) in both the firmware and Node-RED

### 3. Node-RED Dashboard
1. Install Node-RED and the `node-red-dashboard` palette
2. Import `node-red/flow.json`
3. Update the MQTT broker config node with your HiveMQ Cloud host/credentials
4. Deploy — the dashboard shows live per-zone readings, fire notifications, and logs fire events to `fire_events.csv`

---

## 📊 Data Logging & Analytics

Every fire event (`fire_detected` / `fire_cleared`) is appended to `fire_events.csv` with the following columns:

```
zone, event, flame, temperature, timestamp, iso_date
```

This log is intended to help the facility's safety team identify recurring problem zones, common trigger conditions (e.g. temperature spikes vs. direct flame detection), and response times — supporting future improvements to sensor placement, thresholds, or fire suppression coverage.

---

## 🎥 Demo

- Block diagram: [View Block Diagram](docs/block-diagram.png)
- Demo video: [Watch Demo Video](docs/demo.mp4)
- Dashboard screenshots: [View Dashboard Screenshots](docs/dashboard-screenshot.png)

---

## 🚀 Future Improvements

- Port firmware from MicroPython to C for production deployment
- Replace CSV logging with a time-series database (e.g. InfluxDB) for larger-scale analytics
- Add gas/smoke sensor (MQ2) per zone for earlier detection
- Add authentication/access control on the dashboard
- Support dynamic zone configuration instead of hardcoded zone count

---

## 👥 Contributors

- Alshaimaa Reda
- Malak Moataz
- Ahmed Tamer
- Mohamed Emad
- Saif El Tahewy

## 📄 License

This project is licensed under the [MIT License](LICENSE).
