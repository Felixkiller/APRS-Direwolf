"""Publisher SIMULASI untuk menguji jalur MQTT -> APRS tanpa Raspberry Pi.

Data dari skrip ini BUKAN pembacaan sensor asli. Jangan presentasikan sebagai
telemetry Raspberry Pi.
"""
import json
import random
import time
import uuid

import paho.mqtt.client as mqtt

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "raspberry_temperature"
INTERVAL = 3  # detik

client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                     client_id=f"uts-sim-{uuid.uuid4().hex[:8]}")
client.connect(BROKER, PORT, 60)
client.loop_start()
try:
    temp = 27.0
    print(f"Mengirim data SIMULASI ke {BROKER}:{PORT} topic '{TOPIC}'. Ctrl+C untuk berhenti.")
    while True:
        temp += random.uniform(-0.3, 0.3)
        payload = json.dumps({"temperature": round(temp, 1),
                              "humidity": round(random.uniform(55, 70), 1),
                              "source": "simulation"})
        client.publish(TOPIC, payload, qos=0)
        print("publish:", payload)
        time.sleep(INTERVAL)
except KeyboardInterrupt:
    print("\nBerhenti.")
finally:
    client.loop_stop()
    client.disconnect()
