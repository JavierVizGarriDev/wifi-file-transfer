## 📖 Overview

**WiFi File Transfer** solves a simple but annoying problem: moving files between a PC and a phone when there's no internet, no USB cable, and no cloud service available.

It spins up a tiny HTTP server on the PC. The phone connects to the PC's Hotspot (or the same WiFi network), scans a QR code, and can immediately send or receive files through the browser. No apps to install, no accounts, no configuration.

Originally built for a workplace environment where traditional transfer methods were blocked or impractical.

---

## 📸 Screenshots

| Ready to send | Uploading | Complete |
|---|---|---|
| ![Ready](screenshots/mobile-ui-idle.png) | ![Uploading](screenshots/mobile-ui-uploading.png) | ![Complete](screenshots/mobile-ui-success.png) |

| Generated QR code | Server console |
|---|---|
| ![QR example](screenshots/qr-example.png) | ![Console startup](screenshots/console-startup.png) |

*The server console showing the detected IP, the generated QR code, and the polling activity from the phone.*

---

## ✨ Features

- 📷 **QR code auto-generation** — On startup, the server generates a QR code with the connection URL and opens it automatically. Just scan it with your phone.
- 📤 **Mobile → PC** — Upload one or multiple files from the phone's browser directly to the PC.
- 📥 **PC → Mobile** — Drop files into the `outbox/` folder and they are pushed to the phone automatically via polling.
- 📱 **Mobile-first UI** — Responsive, no frameworks, no external CDNs. Loads instantly.
- 🌐 **Auto IP detection** — Detects the Windows Hotspot IP at startup and falls back gracefully.
- 🧪 **20 unit tests passing** — Core logic is tested (IP detection, outbox monitoring, upload endpoint, startup).
- 📦 **Standalone executable** — Download `wifi-file-transfer.exe` from [Releases](../../releases) — no Python installation required.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.10+, Flask |
| Frontend | HTML5, CSS3, Vanilla JavaScript |
| QR generation | `qrcode` + `Pillow` |
| Testing | `unittest` |
| Packaging | PyInstaller |

No frontend frameworks, no build step, no external CDNs. The entire app runs from a single Python file plus one HTML template.

---

## 🚀 How to Run

> ⚠️ **Important — order matters:**
> Activate the Windows Hotspot **before** starting the server. The server detects the Hotspot IP at startup. If you run it before the Hotspot is active, it will pick the wrong IP and the QR code won't work.

### Option 1 — Standalone executable (recommended for end users)

1. **Activate the Windows Hotspot** (Settings → Network & Internet → Mobile hotspot).
2. Download `wifi-file-transfer.exe` from the [Releases](../../releases) page.
3. Double-click it. A QR code will open automatically and the console will show the server URL, e.g. `http://192.168.1.50:5000`.
4. Connect your phone to the PC's Hotspot (or to the same WiFi network).
5. **Scan the QR code** — or manually open the URL shown in the console, using the IP printed on screen and port `5000`. Example: `http://192.168.1.50:5000`.

### Option 2 — From source (for developers)

```bash
git clone https://github.com/JavierVizGarriDev/wifi-file-transfer.git
cd wifi-file-transfer
python -m venv venv
venv\Scripts\activate          # Windows
pip install -r requirements.txt
python server.py
```

Then follow steps 4 and 5 above.

---

## 📂 Project Structure

```
wifi-file-transfer/
├── server.py                # Flask backend + QR generation + IP detection
├── test_server.py           # Unit tests (20 passing)
├── server.spec              # PyInstaller build configuration
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies (PyInstaller)
├── LICENSE                  # MIT License
├── templates/
│   └── index.html           # Mobile-first frontend
├── uploads/                 # Received files from the phone (gitignored)
├── outbox/                  # Files to send to the phone (gitignored)
└── qr/                      # Generated QR codes (gitignored)
```

---

## 🧪 Tests

Run the test suite with:

```bash
python -m unittest test_server.py
```

Current status: **20 tests passing**.

Covers:
- IP detection (typical Hotspot IP, fallback private IPs, error handling, encoding issues)
- Outbox monitoring (empty, single file, multiple files, directory skipping)
- Upload endpoint (`/upload`) — success, empty filename, rename on collision
- Startup logic (`main()`) — folder creation, error handling, `app.run` parameters

> **Note on technical debt**: the test suite does not yet cover `/poll`, `/download_push`, or `generate_qr()`. This is planned for a future iteration.

---

## 🗺️ Roadmap

- [ ] Add tests for `/poll`, `/download_push`, and `generate_qr()`
- [ ] Optional password protection for the server
- [ ] Progress bar for large file uploads
- [ ] Cross-platform IP detection (Linux / macOS)
- [ ] Native Android app (in progress on a separate branch)

---

## 🤝 Contributing

This is primarily a personal learning project, but suggestions and feedback are welcome. Feel free to open an issue or submit a pull request.

---

## 📄 License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Javier A. Vizcaino Garriga**
- GitHub: [@JavierVizGarriDev](https://github.com/JavierVizGarriDev)
- Email: javieralejandrovizcainogarriga@gmail.com

---

<p align="center">
  <i>Built to solve a real problem, one commit at a time.</i>
</p>
