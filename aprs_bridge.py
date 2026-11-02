"""MQTT -> APRS bridge untuk UTS (YD3ADB-11).

Menerima suhu dari topic MQTT `raspberry_temperature`, lalu membuat paket
APRS weather yang bisa dibaca aprs.fi.

Mode:
  py aprs_bridge.py                 # subscribe MQTT, tulis latest_aprs_info.txt
                                    # (dibaca Direwolf lewat CBEACON infocmd)
  py aprs_bridge.py --direct        # + kirim langsung ke APRS-IS (tanpa Direwolf)
  py aprs_bridge.py --dry-run       # hanya cetak paket, tidak kirim apa pun
  py aprs_bridge.py --print-latest  # dipanggil Direwolf: cetak info terbaru
                                    # kalau umurnya < --max-age detik
"""
import argparse
import json
import os
import re
import socket
import sys
import time
import uuid

CALLSIGN = "YD3ADB-11"
PASSCODE = "23973"
APRS_IS_HOST = "rotate.aprs2.net"
APRS_IS_PORT = 14580

BROKER = "broker.emqx.io"
PORT = 1883
TOPIC = "raspberry_temperature"

# GANTI dengan lokasi sensor yang sebenarnya (derajat desimal, selatan/barat negatif).
# Nilai bawaan hanya perkiraan area Surabaya.
LAT = -7.2290
LON = 112.7480

INFO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "latest_aprs_info.txt")


# ---------------------------------------------------------------- parsing
def parse_payload(raw):
    """Kembalikan (suhu_C, kelembapan_persen_atau_None) atau None kalau gagal."""
    text = raw.strip()
    # JSON
    try:
        obj = json.loads(text)
    except ValueError:
        obj = None
    if isinstance(obj, dict):
        temp = hum = None
        for k, v in obj.items():
            key = k.lower()
            if key in ("temperature", "temp", "suhu", "t") and isinstance(v, (int, float)):
                temp = float(v)
            elif key in ("humidity", "hum", "rh", "kelembapan", "h") and isinstance(v, (int, float)):
                hum = float(v)
        return (temp, hum) if temp is not None else None
    if isinstance(obj, (int, float)):
        return float(obj), None
    if isinstance(obj, list) and len(obj) == 2 and all(isinstance(x, (int, float)) for x in obj):
        return obj[1] / 10.0, obj[0] / 10.0  # [RH x10, suhu x10]
    # Teks: temp=26.5'C / Temperature: 26.5 C
    m = re.search(r"(?:temp(?:erature)?|suhu)\s*[=:]\s*(-?\d+(?:\.\d+)?)", text, re.I)
    if m:
        return float(m.group(1)), None
    m = re.fullmatch(r"-?\d+(?:\.\d+)?", text)
    if m:
        return float(text), None
    return None


# ---------------------------------------------------------------- APRS
def _lat(lat):
    h = "N" if lat >= 0 else "S"
    lat = abs(lat)
    d = int(lat)
    return f"{d:02d}{(lat - d) * 60:05.2f}{h}"


def _lon(lon):
    h = "E" if lon >= 0 else "W"
    lon = abs(lon)
    d = int(lon)
    return f"{d:03d}{(lon - d) * 60:05.2f}{h}"


def build_info(temp_c, hum=None, lat=LAT, lon=LON):
    """Info field APRS weather: posisi + simbol cuaca '_' + t(F) [+ h]."""
    temp_f = int(round(temp_c * 9.0 / 5.0 + 32.0))
    temp_f = max(-99, min(999, temp_f))
    info = f"!{_lat(lat)}/{_lon(lon)}_.../...t{temp_f:03d}"
    if hum is not None:
        h = int(round(hum))
        info += f"h{0 if h >= 100 else max(1, h):02d}"
    info += f" RPi {temp_c:.1f}C MQTT"
    return info


def packet(info):
    return f"{CALLSIGN}>APRS,TCPIP*:{info}"


def send_aprs_is(pkt, timeout=10):
    """Login ke APRS-IS dan kirim satu paket. Return (ok, pesan_server)."""
    with socket.create_connection((APRS_IS_HOST, APRS_IS_PORT), timeout=timeout) as s:
        s.settimeout(timeout)
        s.recv(512)  # banner server
        s.sendall(f"user {CALLSIGN} pass {PASSCODE} vers mqtt-aprs-uts 1.0\r\n".encode())
        resp = s.recv(512).decode(errors="replace").strip()
        if "unverified" in resp.lower() or "verified" not in resp.lower():
            return False, resp
        s.sendall((pkt + "\r\n").encode())
        time.sleep(1)  # beri waktu server memproses sebelum tutup
        return True, resp


# ---------------------------------------------------------------- Direwolf side
def print_latest(max_age):
    """Dipanggil Direwolf (CBEACON infocmd). Cetak info hanya jika masih segar."""
    try:
        if time.time() - os.path.getmtime(INFO_FILE) > max_age:
            return
        with open(INFO_FILE, encoding="utf-8") as f:
            sys.stdout.write(f.read().strip())
    except OSError:
        pass


def write_info(info):
    tmp = f"{INFO_FILE}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(info)
    for attempt in range(5):
        try:
            os.replace(tmp, INFO_FILE)
            return
        except PermissionError:
            if attempt == 4:
                raise
            # Direwolf may briefly open the destination while executing infocmd.
            time.sleep(0.05)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--direct", action="store_true", help="kirim juga langsung ke APRS-IS")
    ap.add_argument("--dry-run", action="store_true", help="hanya cetak paket")
    ap.add_argument("--print-latest", action="store_true", help="mode untuk Direwolf infocmd")
    ap.add_argument("--max-age", type=int, default=180, help="umur maks data (detik) untuk --print-latest")
    ap.add_argument("--interval", type=int, default=300,
                    help="jeda minimum antar upload langsung ke APRS-IS (detik, default 300)")
    ap.add_argument("--lat", type=float, default=LAT)
    ap.add_argument("--lon", type=float, default=LON)
    args = ap.parse_args()

    if args.print_latest:
        print_latest(args.max_age)
        return

    import paho.mqtt.client as mqtt

    state = {"last_upload": 0.0}

    def on_connect(client, userdata, flags, reason_code, properties):
        if reason_code == 0:
            client.subscribe(TOPIC)
            print(f"MQTT terhubung ke {BROKER}:{PORT}, subscribe '{TOPIC}'")
        else:
            print("MQTT gagal:", reason_code)

    def on_message(client, userdata, msg):
        raw = msg.payload.decode("utf-8", errors="replace")
        parsed = parse_payload(raw)
        if parsed is None:
            print(f"[skip] payload tidak dikenali: {raw!r}")
            return
        temp, hum = parsed
        info = build_info(temp, hum, args.lat, args.lon)
        pkt = packet(info)
        print(f"[{time.strftime('%H:%M:%S')}] MQTT {raw!r} -> {pkt}")
        if args.dry_run:
            return
        write_info(info)
        if args.direct and time.time() - state["last_upload"] >= args.interval:
            try:
                ok, resp = send_aprs_is(pkt)
                print("  APRS-IS:", "terkirim" if ok else "DITOLAK", "|", resp)
                if ok:
                    state["last_upload"] = time.time()
            except OSError as e:
                print("  APRS-IS error:", e)

    client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                         client_id=f"aprs-bridge-{uuid.uuid4().hex[:8]}")
    client.on_connect = on_connect
    client.on_message = on_message
    try:
        client.connect(BROKER, PORT, 60)
        client.loop_forever()
    except KeyboardInterrupt:
        print("\nBerhenti.")
    finally:
        client.disconnect()


if __name__ == "__main__":
    main()
