# hAI.mp3rgainDockerWebUI 🎧🟢

![Language](https://img.shields.io/badge/Language-English-blue?style=for-the-badge)
![mp3rgain](https://img.shields.io/badge/Tool-mp3rgain-0ea5e9?style=for-the-badge)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=for-the-badge&logo=docker&logoColor=white)
![Flask](https://img.shields.io/badge/WebUI-Flask-black?style=for-the-badge&logo=flask&logoColor=white)
![Status](https://img.shields.io/badge/Status-Experimental-f97316?style=for-the-badge)
![License](https://img.shields.io/badge/License-MIT-slateblue?style=for-the-badge)

> 🪄 **Lossless** MP3 volume normalization in your browser – runs as a Docker / Portainer stack using `mp3rgain`.

---

## 🎯 Features

- 🖥 **Web UI** (Flask) – fully browser-based
- 📁 **Mounted folder** – process MP3s from a host folder mounted into the container
- 📤 **File upload** – upload multiple MP3 files directly from your browser
- 📦 **Batch processing** – normalize full albums or folder trees in one go
- 🎚 **Modes**: Track Gain (`-r`), Album Gain (`-a`), Undo (`-u`)
- 📥 **ZIP download** of processed files
- 🔒 **Original files remain untouched** – always copied into a job working directory first
- 💚 **Truly lossless** – no re-encoding, only `global_gain` field adjustment

---

## 🧩 Architecture

```text
Host
 └─ /opt/mp3rgain/music
     ├─ in/      ← input (original files)
     └─ out/     ← output (jobs + ZIPs)

Container
 └─ /music
     ├─ /music/in    ← INPUT_DIR
     └─ /music/out   ← OUTPUT_DIR
```

---

## 🚀 Quickstart (Portainer stack)

1. Clone this repository
2. In Portainer, create a **new stack**
3. Paste the contents of `docker-compose.yml` and adjust paths
4. Deploy the stack
5. Open the Web UI: `http://YOUR-IP:8099`

```yaml
version: "3.8"

services:
  mp3rgain-webui:
    build: https://github.com/jbkunama1/hAI.mp3rgainDockerWebUI.git
    container_name: mp3rgain-webui
    ports:
      - "8099:8099"
    environment:
      - TZ=Europe/Berlin
      - APP_PORT=8099
      - INPUT_DIR=/music/in
      - OUTPUT_DIR=/music/out
      - TEMP_DIR=/tmp/mp3rgain-jobs
      - MAX_CONTENT_LENGTH=2147483648
    volumes:
      - mp3rgain_data:/app/data
      - /opt/mp3rgain/music:/music   # adjust host path!
    restart: unless-stopped
    mem_limit: 256m
    cpus: "1.0"

volumes:
  mp3rgain_data:
```

> 💡 Adjust `/opt/mp3rgain/music` to your actual host music directory.

---

## 🕹 Web UI usage

### Choose source

- **Mounted input folder** – base is `INPUT_DIR`, optional relative subfolder, all `.mp3` found recursively
- **Upload** – select one or more `.mp3` files directly from your machine

### Choose mode

| Mode | Flag | Description |
|---|---|---|
| Track Gain | `-r` | Normalize each file independently |
| Album Gain | `-a` | Treat all files as one album |
| Undo | `-u` | Revert previous mp3gain/mp3rgain changes |

### Download result

After a successful job, an entry appears in the **Results table** with timestamp, job ID, mode and file count. Click **"Download ZIP"** to get all processed files.

---

## ⚙️ Environment variables

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `8099` | HTTP port inside the container |
| `INPUT_DIR` | `/music/in` | Input directory in the container |
| `OUTPUT_DIR` | `/music/out` | Output directory in the container |
| `TEMP_DIR` | `/tmp/mp3rgain-jobs` | Temporary job directories |
| `MAX_CONTENT_LENGTH` | `2147483648` | Max upload size (~2 GB) |

---

## 🧪 Local build & test

```bash
# Create directories
mkdir -p /opt/mp3rgain/music/in /opt/mp3rgain/music/out

# Build
docker build -t hai-mp3rgain-webui .

# Run
docker run --rm -p 8099:8099 \
  -e TZ=Europe/Berlin \
  -v /opt/mp3rgain/music:/music \
  hai-mp3rgain-webui
```

Open `http://localhost:8099` in your browser.

---

## 📚 Core tool: mp3rgain

This project wraps [`mp3rgain`](https://github.com/M-Igashi/mp3rgain), a modern lossless replacement for the classic `mp3gain`. It adjusts the `global_gain` field of MP3 frames without re-encoding audio data.

---

## 🗂 Repository structure

```
hAI.mp3rgainDockerWebUI/
├── app.py               # Flask Web UI
├── Dockerfile           # Docker image definition
├── docker-compose.yml   # Portainer stack
├── README.md            # German version
└── README_en.md         # This file (EN)
```

---

## ⚠️ Disclaimer

- Use at your own risk
- Always test with copies of your files first
- This is **not** an official project of the `mp3rgain` author

---

## 🧩 License

MIT

---

> 📖 Deutsche Version: [README.md](README.md)
