"""Terminal subscriber untuk melihat payload MQTT mentah."""
import json
import uuid

import paho.mqtt.client as mqtt


BROKER = "broker.emqx.io"
PORT = 1883
TOPICS = ("raspberry_temperature", "suhu_ukdc")


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        print(f"Terhubung ke {BROKER}:{PORT}")
        for topic in TOPICS:
            client.subscribe(topic, qos=0)
            print(f"Subscribe: {topic}")
    else:
        print(f"Koneksi MQTT gagal: {reason_code}")


def on_message(client, userdata, message):
    raw = message.payload.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = None

    print(f"\nWaktu  : {userdata['now']()}")
    print(f"Topic  : {message.topic}")
    print(f"Raw    : {raw}")
    if parsed is not None:
        print(f"JSON   : {parsed}")


def main():
    from datetime import datetime

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"uts-subscriber-{uuid.uuid4().hex[:8]}",
        userdata={"now": lambda: datetime.now().strftime("%d-%m-%Y %H:%M:%S")},
    )
    client.on_connect = on_connect
    client.on_message = on_message

    print("Menunggu telemetry. Tekan Ctrl+C untuk berhenti.")
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
