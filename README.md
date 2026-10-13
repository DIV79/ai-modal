# ARIA – AI Voice Assistant 🤖🎙️

> **A smart, self-learning desktop voice and text assistant built with Python and Tkinter.**

ARIA is an interactive, responsive desktop AI assistant designed for Windows. It combines natural voice interaction, offline speech synthesis, quick application launching, web searches, and an adaptable self-learning engine into an elegant dark-mode interface.

---

## ✨ Features

- **🎙️ Dual Input (Voice & Text):** Click the animated pulse mic to speak naturally or type commands directly in the prompt bar.
- **🔊 Offline Text-to-Speech (TTS):** Instant audio responses powered by `pyttsx3` without requiring an internet connection for speech generation.
- **⚡ Application Launcher:** Launch popular Windows applications (VS Code, Chrome, Spotify, Discord, MS Office suite, Terminal, Calculator, etc.) instantly.
- **🌐 Web Navigation & Knowledge:** Fast access to 40+ popular platforms (YouTube, GitHub, Google, ChatGPT, Wikipedia, etc.) plus real-time queries.
- **🧠 Self-Learning Architecture:** Teach ARIA custom paths or application aliases right through the UI or voice commands—persistently saved in `commands.json`.
- **🎨 Modern Dark UI:** Custom Tkinter interface with dynamic audio pulse effects, command history, and real-time activity metrics.
- **📦 Windows Executable Ready:** Configured with PyInstaller (`ARIA.spec`) for building a portable `.exe`.

---

## 🚀 Quick Start

### Option 1: 1-Click Setup (Recommended for Windows)

Simply double-click or run:
```bat
run.bat
```
`run.bat` will automatically verify your Python installation, install required dependencies (`SpeechRecognition`, `pyttsx3`, `sounddevice`, `numpy`, `requests`, `pillow`), and launch ARIA.

---

### Option 2: Manual Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/DIV79/ai-modal.git
   cd ai-modal
   ```

2. **Create and activate a virtual environment (optional but recommended):**
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run ARIA:**
   ```bash
   python main.py
   ```

---

## 🗣️ Example Commands

| Command | Action |
| :--- | :--- |
| `open chrome` / `open spotify` | Launches the target application |
| `search python tutorials on google` | Performs a Google search |
| `search lo-fi beats on youtube` | Searches and opens YouTube results |
| `what is quantum computing` | Queries Wikipedia / Web info |
| `what time is it` / `what date is it` | Tells current local time and date |
| `teach app` *(via UI panel)* | Teaches ARIA custom applications and executables |

---

## 📁 Project Structure

```text
ai-modal/
├── aria_icon.ico       # Application icon
├── ARIA.spec           # PyInstaller build specification
├── assistant.py        # Core AIAssistant logic, TTS, Speech, & Command handlers
├── commands.json       # App registry, custom commands, and usage memory
├── main.py             # Tkinter desktop GUI & animated widgets
├── requirements.txt    # Python dependencies
├── run.bat             # 1-click Windows launcher script
├── .gitignore          # Git exclusion rules (builds, venv, caches)
└── README.md           # Project documentation
```

---

## 🛠️ Building the Standalone `.exe`

To package ARIA into a standalone Windows executable using PyInstaller:

```bash
pip install pyinstaller
pyinstaller ARIA.spec
```

The resulting executable will be generated inside the `dist/` directory.

---

## 🤝 Contributing

Contributions, issues, and feature requests are welcome! Feel free to open an issue or submit a pull request.
