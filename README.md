# APRS Direwolf

Proyek ini berfungsi untuk mengirim data cuaca/sensor dari MQTT ke jaringan APRS (APRS-IS) dengan dua cara:

- Jalur langsung: MQTT -> bridge -> APRS-IS
- Jalur dengan Direwolf: MQTT -> bridge -> Direwolf -> APRS-IS/IGate

Tujuan utamanya adalah menampilkan data suhu dan kelembapan dari sensor atau simulasi ke APRS, lalu bisa dilihat di aprs.fi atau melalui dashboard lokal.

## Fitur utama

- Menerima payload MQTT berupa JSON atau teks sederhana
- Menangkap variabel seperti `temperature`, `temp`, `humidity`, `hum`
- Membuat paket APRS weather format yang bisa dibaca APRS-IS
- Mendukung mode `--direct` untuk kirim langsung tanpa Direwolf
- Mendukung mode `--dry-run` untuk menguji payload tanpa mengirim
- Menyediakan dashboard web untuk memonitor data MQTT live
- Mendukung subscriber terminal untuk memantau payload mentah

## Arsitektur singkat

```text
Sensor / Raspberry Pi / MQTT Publisher
                |
                v
        MQTT broker (broker.emqx.io)
                |
                v
   aprs_bridge.py (parse + build APRS packet)
                |
      +---------------------------+
      |                           |
      v                           v
Direwolf + IGate             APRS-IS direct
      |                           |
      v                           v
    aprs.fi / APRS network      aprs.fi / APRS network
```

## Struktur file

```text
APRS-Direwolf/
├── aprs_bridge.py          # MQTT -> APRS bridge
├── mqtt_dashboard.py       # dashboard live web
├── mqtt_subscriber.py      # subscriber payload MQTT di terminal
├── mqtt_test_publisher.py   # publisher simulasi untuk testing
├── direwolf.conf           # konfigurasi Direwolf / IGate
├── PANDUAN_APRS.md         # panduan penggunaan dalam Bahasa Indonesia
├── latest_aprs_info.txt    # file hasil data APRS terbaru
├── requirements-dashboard.txt
├── APRS direwolf.zip       # arsip proyek
└── README.md               # dokumentasi proyek
```

## Persyaratan

- Python 3.9+
- Paket: `paho-mqtt`
- Untuk mode Direwolf: Direwolf terinstall dan `direwolf.conf` sesuai
- Akses internet agar bisa login ke APRS-IS
- Callsign APRS yang valid, contoh: `YD3ADB-11`

## Instalasi

Pada Windows:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe -m pip install paho-mqtt
```

Atau jika belum ada virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements-dashboard.txt
```

## Mode 1: Kirim langsung ke APRS-IS (tanpa Direwolf)

Jalankan bridge:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe aprs_bridge.py --direct --interval 60
```

Untuk pengujian tanpa sensor asli:

```powershell
.\.venv\Scripts\python.exe mqtt_test_publisher.py
```

Data sampel yang dikirim biasanya berbentuk:

```json
{"temperature": 26.5, "humidity": 65}
```

atau

```text
temp=26.5
```

Bridge akan menghasilkan paket APRS seperti:

```text
YD3ADB-11>APRS,TCPIP*:!0713.74S/11244.88E_.../...t080h65 RPi 26.5C MQTT
```

## Mode 2: Menggunakan Direwolf

1. Jalankan Direwolf:

```powershell
direwolf.exe -c direwolf.conf -t 0
```

2. Jalankan bridge:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe aprs_bridge.py
```

3. Jalankan publisher simulasi bila diperlukan:

```powershell
.\.venv\Scripts\python.exe mqtt_test_publisher.py
```

Direwolf akan membaca data terbaru dari `latest_aprs_info.txt` melalui `CBEACON` dan mengirimnya ke APRS-IS.

## Dashboard live

Jalankan dashboard:

```powershell
cd "C:\Users\Felix\Downloads\APRS direwolf"
.\.venv\Scripts\python.exe mqtt_dashboard.py
```

Buka browser ke:

```text
http://localhost:8080
```

API status:

```text
http://localhost:8080/api/status
```

Dashboard menampilkan:

- status koneksi MQTT
- suhu saat ini
- kelembapan saat ini
- waktu data diterima
- payload mentah

## Subscriber data MQTT

Untuk melihat payload mentah dari topic MQTT:

```powershell
.\.venv\Scripts\python.exe mqtt_subscriber.py
```

## Konfigurasi penting

File utama yang perlu diperhatikan:

- `aprs_bridge.py`
  - `CALLSIGN = "YD3ADB-11"`
  - `PASSCODE = "23973"`
  - `LAT = -7.2290`
  - `LON = 112.7480`

- `direwolf.conf`
  - `MYCALL YD3ADB-11`
  - `IGLOGIN YD3ADB-11 23973`
  - `PBEACON` untuk posisi IGate
  - `CBEACON` untuk mengirim data suhu

## Catatan penting

- Jangan aktifkan dua jalur pengiriman secara bersamaan bila tidak diperlukan, agar paket tidak masuk double.
- Data `mqtt_test_publisher.py` adalah simulasi, bukan pembacaan sensor fisik yang asli.
- Pastikan koordinat lokasi sesuai dengan lokasi sensor anda.
- `aprs.fi` mungkin perlu beberapa menit untuk memperbarui data.

## Referensi tambahan

- Panduan lengkap: `PANDUAN_APRS.md`
- File `latest_aprs_info.txt` digunakan sebagai cache APRS terbaru yang dibaca Direwolf

## Ringkasan

Proyek ini cocok untuk kebutuhan monitoring suhu/kelembapan berbasis MQTT yang ingin dipublikasikan ke jaringan APRS. Dengan kombinasi `aprs_bridge.py`, `direwolf.conf`, dan `mqtt_dashboard.py`, Anda bisa menjalankan jalur pengiriman data secara lokal maupun langsung ke APRS-IS.

Jika Anda ingin, saya juga bisa membuat versi README yang lebih formal untuk GitHub, atau versi singkat yang lebih cocok untuk dijadikan landing page proyek.
