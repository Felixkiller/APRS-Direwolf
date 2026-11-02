"""Dashboard web MQTT untuk menampilkan suhu dan kelembapan secara live."""
import json
import os
import queue
import re
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

import paho.mqtt.client as mqtt


BROKER = os.environ.get("MQTT_BROKER", "broker.emqx.io")
PORT = int(os.environ.get("MQTT_PORT", "1883"))
WEB_PORT = int(os.environ.get("DASHBOARD_PORT", "8080"))
TOPICS = tuple(filter(None, os.environ.get(
    "MQTT_TOPICS", "raspberry_temperature,suhu_ukdc"
).split(",")))

state_lock = threading.Lock()
listeners = []
state = {
    "mqtt_connected": False,
    "broker": BROKER,
    "port": PORT,
    "messages": 0,
    "topics": {},
}


def number(value):
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"[-+]?\d+(?:[.,]\d+)?", str(value))
    if not match:
        raise ValueError(f"Angka tidak ditemukan pada {value!r}")
    return float(match.group(0).replace(",", "."))


def parse_payload(raw):
    text = raw.strip()
    if not text:
        return None, None

    try:
        data = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        data = None

    if isinstance(data, dict):
        temp = next((data[key] for key in ("temperature", "temp", "suhu", "t") if key in data), None)
        humidity = next((data[key] for key in ("humidity", "hum", "rh", "kelembapan") if key in data), None)
        try:
            temp = number(temp) if temp is not None else None
            humidity = number(humidity) if humidity is not None else None
        except ValueError:
            return None, None
        return temp, humidity

    if isinstance(data, list) and len(data) >= 2:
        try:
            humidity, temp = number(data[0]), number(data[1])
            if abs(humidity) >= 100:
                humidity /= 10
            if abs(temp) >= 100:
                temp /= 10
            return temp, humidity
        except ValueError:
            return None, None

    temp_match = re.search(r"(?:temp(?:erature)?|suhu)\s*[:=]\s*([-+]?\d+(?:[.,]\d+)?)", text, re.I)
    hum_match = re.search(r"(?:humidity|kelembapan|rh)\s*[:=]\s*([-+]?\d+(?:[.,]\d+)?)", text, re.I)
    if temp_match or hum_match:
        return (
            number(temp_match.group(1)) if temp_match else None,
            number(hum_match.group(1)) if hum_match else None,
        )

    try:
        return number(text), None
    except ValueError:
        return None, None


def publish_update(topic, raw, temp, humidity):
    payload = {
        "topic": topic,
        "temperature": temp,
        "humidity": humidity,
        "raw": raw[:500],
        "time": datetime.now().strftime("%d-%m-%Y %H:%M:%S"),
    }
    with state_lock:
        state["messages"] += 1
        state["topics"][topic] = payload
        listeners_copy = list(listeners)
    encoded = json.dumps(payload)
    for listener in listeners_copy:
        listener.put(encoded)


def on_connect(client, userdata, flags, reason_code, properties=None):
    with state_lock:
        state["mqtt_connected"] = reason_code == 0
    if reason_code == 0:
        for topic in TOPICS:
            client.subscribe(topic, qos=0)
        print("MQTT terhubung:", ", ".join(TOPICS))
    else:
        print("MQTT gagal terhubung:", reason_code)


def on_disconnect(client, userdata, disconnect_flags=None, reason_code=None, properties=None):
    with state_lock:
        state["mqtt_connected"] = False


def on_message(client, userdata, message):
    raw = message.payload.decode("utf-8", errors="replace")
    temp, humidity = parse_payload(raw)
    print(datetime.now().strftime("%H:%M:%S"), message.topic, raw)
    publish_update(message.topic, raw, temp, humidity)


PAGE = """<!doctype html>
<html lang="id">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>MQTT Telemetry Dashboard</title>
<style>
:root{color-scheme:dark;font-family:Segoe UI,Arial,sans-serif}
body{margin:0;background:#09111f;color:#eaf2ff}
main{max-width:980px;margin:auto;padding:24px}
header{display:flex;justify-content:space-between;align-items:center;gap:16px}
h1{margin:0;font-size:24px}.status{padding:8px 12px;border-radius:20px;background:#543c20}
.status.ok{background:#174d34}.status.bad{background:#5d1f2b}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:18px;margin-top:24px}
.card{background:#142038;border:1px solid #263a60;border-radius:16px;padding:20px}
.topic{color:#8fbaff;font-weight:bold;overflow-wrap:anywhere}
.values{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin:20px 0}
.value{background:#0b1426;border-radius:12px;padding:14px;text-align:center}
.value strong{display:block;font-size:34px;color:#fff}.value span{color:#91a5c7}
.time,.raw{color:#91a5c7;font-size:13px}.raw{white-space:pre-wrap;word-break:break-word;min-height:34px}
footer{margin-top:24px;color:#7089b0;font-size:13px}
</style></head>
<body><main>
<header><h1>MQTT / APRS Telemetry</h1><div id="status" class="status">Menghubungkan</div></header>
<div class="grid" id="cards"></div>
<footer id="info"></footer>
</main><script>
const topics=["__TOPICS__"];
const cards=document.getElementById("cards");
for(const topic of topics){cards.insertAdjacentHTML("beforeend",`
<section class="card" id="card-${topic.replace(/[^a-z0-9]/gi,"-")}">
<div class="topic">${topic}</div><div class="values">
<div class="value"><strong id="temp-${topic.replace(/[^a-z0-9]/gi,"-")}">--</strong><span>Suhu C</span></div>
<div class="value"><strong id="hum-${topic.replace(/[^a-z0-9]/gi,"-")}">--</strong><span>Kelembapan %RH</span></div></div>
<div class="time" id="time-${topic.replace(/[^a-z0-9]/gi,"-")}">Belum ada data</div><pre class="raw" id="raw-${topic.replace(/[^a-z0-9]/gi,"-")}"></pre>
</section>`)}
function cardId(topic){return topic.replace(/[^a-z0-9]/gi,"-")}
function format(v){return v===null||v===undefined?"--":Number(v).toFixed(1)}
async function load(){const response=await fetch("/api/status");const data=await response.json();
const status=document.getElementById("status");status.textContent=data.mqtt_connected?"MQTT Terhubung":"MQTT Terputus";
status.className="status "+(data.mqtt_connected?"ok":"bad");document.getElementById("info").textContent=`Broker: ${data.broker}:${data.port} | Pesan diterima: ${data.messages}`;
for(const [topic,item] of Object.entries(data.topics||{})){const id=cardId(topic);document.getElementById("temp-"+id).textContent=format(item.temperature)+" °C";
document.getElementById("hum-"+id).textContent=format(item.humidity)+" %RH";document.getElementById("time-"+id).textContent="Diterima "+item.time;document.getElementById("raw-"+id).textContent=item.raw}}
load();setInterval(load,3000);
const stream=new EventSource("/events");stream.onmessage=load;
</script></body></html>"""


class DashboardHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        print(format % args)

    def send_json(self, status, value):
        data = json.dumps(value).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            page = PAGE.replace('"__TOPICS__"', json.dumps(TOPICS))
            data = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
        elif path == "/api/status":
            with state_lock:
                self.send_json(200, dict(state, topics=dict(state["topics"])))
        elif path == "/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream")
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "keep-alive")
            self.end_headers()
            listener = queue.Queue(maxsize=100)
            with state_lock:
                listeners.append(listener)
            try:
                while True:
                    listener.get(timeout=20)
                    self.wfile.write(b"data: update\n\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, queue.Empty, OSError):
                pass
            finally:
                with state_lock:
                    if listener in listeners:
                        listeners.remove(listener)
        else:
            self.send_error(404)


def start_mqtt():
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"uts-dashboard-{uuid.uuid4().hex[:8]}",
    )
    client.on_connect = on_connect
    client.on_disconnect = on_disconnect
    client.on_message = on_message
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    while True:
        try:
            client.connect(BROKER, PORT, 60)
            client.loop_forever(retry_first_connection=True)
        except OSError as exc:
            print("Kesalahan MQTT:", exc)
            with state_lock:
                state["mqtt_connected"] = False
            time.sleep(5)


def main():
    mqtt_thread = threading.Thread(target=start_mqtt, daemon=True)
    mqtt_thread.start()
    server = ThreadingHTTPServer(("0.0.0.0", WEB_PORT), DashboardHandler)
    print(f"Dashboard: http://localhost:{WEB_PORT}")
    print(f"API: http://localhost:{WEB_PORT}/api/status")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        server.shutdown()


if __name__ == "__main__":
    main()
