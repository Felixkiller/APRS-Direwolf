# Panduan APRS – YD3ADB-11 → aprs.fi

## Jalur yang tersedia

Ada dua cara mengirim data cuaca:

1. **Direwolf/IGate:** MQTT -> bridge -> Direwolf -> APRS-IS -> aprs.fi.
2. **Upload langsung:** MQTT -> bridge -> APRS-IS -> aprs.fi.

Gunakan salah satu jalur, jangan mengaktifkan keduanya sekaligus agar paket tidak masuk duplikat.

## Persiapan

1. Pastikan virtual environment dan MQTT client sudah tersedia:

   ```powershell
   cd "C:\Users\Felix\Downloads\APRS direwolf"
   .\.venv\Scripts\python.exe -m pip install paho-mqtt
   ```

2. Pastikan lokasi dan callsign sudah sesuai:
   - `CALLSIGN`, `PASSCODE`, dan koordinat di `aprs_bridge.py`.
   - `MYCALL`, `IGLOGIN`, dan koordinat di `direwolf.conf`.

3. Bawaan koordinat adalah perkiraan Surabaya:
   - Python: `LAT = -7.2290`, `LON = 112.7480`.
   - Direwolf: `lat=7^13.74S long=112^44.88E`.

## Cara A: Upload langsung ke APRS-IS (direkomendasikan tanpa Direwolf)

Terminal 1 — jalankan bridge dan koneksikan penerima APRS:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe aprs_bridge.py --direct --interval 60
```

Terminal 2 — jika Raspberry Pi/sensor nyata belum mengirim MQTT, jalankan pengujian simulasi:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe mqtt_test_publisher.py
```

Bridge harus menampilkan:

```text
MQTT terhubung ke broker.emqx.io:1883, subscribe 'raspberry_temperature'
```

Paket cuaca yang dikirim harus berbentuk kurang lebih:

```text
YD3ADB-11>APRS,TCPIP*:!0713.74S/11244.88E_.../...t080h65 RPi 26.5C MQTT
```

Saat paket dikirim, terminal bridge harus menampilkan:

```text
APRS-IS: terkirim | # logresp YD3ADB-11 verified, server ...
```

Kemudian buka:

```text
https://aprs.fi/#!call=a%2FYD3ADB-11
```

Pembaruan aprs.fi dapat membutuhkan waktu beberapa menit.

## Cara B: Dengan Direwolf

Direwolf diperlukan untuk jalur ini. Pastikan file `direwolf.exe`, `direwolf.conf`, dan `aprs_bridge.py` tersedia pada folder yang sama.

Terminal 1 — jalankan Direwolf:

```powershell
direwolf.exe -c direwolf.conf -t 0
```

Terminal 2 — jalankan bridge tanpa `--direct`:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe aprs_bridge.py
```

Terminal 3 — publisher simulasi hanya untuk pengujian:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe mqtt_test_publisher.py
```

Pada terminal Direwolf harus ada status login IGate dan beacon APRS cuaca. Perintah `CBEACON` dalam `direwolf.conf` memanggil:

```text
.\.venv\Scripts\python.exe aprs_bridge.py --print-latest --max-age 180
```

Edit `ADEVICE` jika radio/audio belum sesuai. Untuk komputer tanpa radio/audio yang terpasang, gunakan Cara A.

## Format data sensor

Topic MQTT adalah:

```text
raspberry_temperature
```

Format JSON yang didukung:

```json
{"temperature": 26.5, "humidity": 65}
```

Format teks yang didukung:

```text
temp=26.5
```

## Pemeriksaan tanpa mengirim

Cetak paket tanpa kirim ke APRS-IS atau menulis file:

```powershell
.\.venv\Scripts\python.exe aprs_bridge.py --dry-run
```

Data `mqtt_test_publisher.py` adalah simulasi, bukan pembacaan sensor fisik. Jangan mengirim simulasi dan menyajikannya sebagai data sensor nyata.

## Dashboard live dan subscriber

Terminal 1 — jalankan dashboard web:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe mqtt_dashboard.py
```

Buka dashboard pada browser:

```text
http://localhost:8080
```

Dashboard menunjukkan status MQTT, suhu, kelembapan, waktu penerimaan, dan payload mentah. Status serta data dapat juga diperiksa melalui API:

```text
http://localhost:8080/api/status
```

Untuk mengganti topic MQTT saat menjalankan dashboard:

```powershell
$env:MQTT_TOPICS="raspberry_temperature"
.\.venv\Scripts\python.exe mqtt_dashboard.py
```

Terminal 2 — tampilkan subscriber dan payload mentah:

```powershell
.\.venv\Scripts\python.exe mqtt_subscriber.py
```

Untuk uji dashboard tanpa sensor, jalankan publisher simulasi pada terminal ketiga:

```powershell
.\.venv\Scripts\python.exe mqtt_test_publisher.py
```
