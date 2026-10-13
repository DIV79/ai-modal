import json
import os
import subprocess
import webbrowser
import datetime
import threading
import time
import re
import shutil
from pathlib import Path
from urllib.parse import quote_plus

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    TTS_AVAILABLE = False

# Try PyAudio first; fall back to sounddevice (works on Python 3.14+)
try:
    import pyaudio  # noqa: F401
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

try:
    import sounddevice as sd
    import numpy as np
    import wave, io
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

MIC_AVAILABLE = PYAUDIO_AVAILABLE or SOUNDDEVICE_AVAILABLE

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False

# ── Popular websites library ──────────────────────────────────────────────────
WEBSITE_MAP: dict[str, str] = {
    # Video / Social
    "youtube": "https://www.youtube.com",
    "youtube music": "https://music.youtube.com",
    "instagram": "https://www.instagram.com",
    "facebook": "https://www.facebook.com",
    "twitter": "https://twitter.com",
    "x": "https://twitter.com",
    "tiktok": "https://www.tiktok.com",
    "snapchat": "https://www.snapchat.com",
    "reddit": "https://www.reddit.com",
    "linkedin": "https://www.linkedin.com",
    "pinterest": "https://www.pinterest.com",
    "tumblr": "https://www.tumblr.com",
    "discord": "https://discord.com",
    "twitch": "https://www.twitch.tv",
    # Shopping
    "amazon": "https://www.amazon.in",
    "flipkart": "https://www.flipkart.com",
    "myntra": "https://www.myntra.com",
    "meesho": "https://www.meesho.com",
    "snapdeal": "https://www.snapdeal.com",
    "nykaa": "https://www.nykaa.com",
    "ajio": "https://www.ajio.com",
    "ebay": "https://www.ebay.com",
    "aliexpress": "https://www.aliexpress.com",
    # News / Info
    "google": "https://www.google.com",
    "bing": "https://www.bing.com",
    "wikipedia": "https://www.wikipedia.org",
    "bbc": "https://www.bbc.com",
    "ndtv": "https://www.ndtv.com",
    "times of india": "https://timesofindia.indiatimes.com",
    "the hindu": "https://www.thehindu.com",
    "news18": "https://www.news18.com",
    "cnbc": "https://www.cnbc.com",
    "techcrunch": "https://techcrunch.com",
    "the verge": "https://www.theverge.com",
    # Tech / Dev
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "w3schools": "https://www.w3schools.com",
    "mdn": "https://developer.mozilla.org",
    "pypi": "https://pypi.org",
    "npm": "https://www.npmjs.com",
    "replit": "https://replit.com",
    "codepen": "https://codepen.io",
    # AI / Tools
    "chatgpt": "https://chat.openai.com",
    "gemini": "https://gemini.google.com",
    "claude": "https://claude.ai",
    "perplexity": "https://www.perplexity.ai",
    "canva": "https://www.canva.com",
    "figma": "https://www.figma.com",
    "notion": "https://www.notion.so",
    "trello": "https://trello.com",
    "jira": "https://www.atlassian.com/software/jira",
    # Entertainment / Streaming
    "netflix": "https://www.netflix.com",
    "hotstar": "https://www.hotstar.com",
    "spotify": "https://open.spotify.com",
    "prime video": "https://www.primevideo.com",
    "disney plus": "https://www.disneyplus.com",
    "zee5": "https://www.zee5.com",
    "sonyliv": "https://www.sonyliv.com",
    # Finance
    "google pay": "https://pay.google.com",
    "paytm": "https://www.paytm.com",
    "phonepe": "https://www.phonepe.com",
    "zerodha": "https://zerodha.com",
    "moneycontrol": "https://www.moneycontrol.com",
    # Email / Cloud
    "gmail": "https://mail.google.com",
    "outlook": "https://outlook.live.com",
    "google drive": "https://drive.google.com",
    "google docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "onedrive": "https://onedrive.live.com",
    "dropbox": "https://www.dropbox.com",
    # Travel
    "make my trip": "https://www.makemytrip.com",
    "irctc": "https://www.irctc.co.in",
    "goibibo": "https://www.goibibo.com",
    "airbnb": "https://www.airbnb.co.in",
}

COMMANDS_FILE = os.path.join(os.path.dirname(__file__), "commands.json")

# Common Windows app search paths
APP_SEARCH_PATHS = [
    r"C:\Program Files",
    r"C:\Program Files (x86)",
    os.path.expandvars(r"%APPDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%PROGRAMDATA%\Microsoft\Windows\Start Menu\Programs"),
    os.path.expandvars(r"%LOCALAPPDATA%"),
    r"C:\Windows",
    r"C:\Windows\System32",
]

# Known full paths for popular apps that are NOT on the system PATH
# We try each candidate in order and use the first one that exists.
_LAPPDATA = os.path.expandvars("%LOCALAPPDATA%")
_APPDATA   = os.path.expandvars("%APPDATA%")
_PROGFILES = os.environ.get("PROGRAMFILES",  r"C:\Program Files")
_PROGFX86  = os.environ.get("PROGRAMFILES(X86)", r"C:\Program Files (x86)")

WELL_KNOWN_PATHS: dict[str, list[str]] = {
    "chrome": [
        rf"{_PROGFILES}\Google\Chrome\Application\chrome.exe",
        rf"{_PROGFX86}\Google\Chrome\Application\chrome.exe",
        rf"{_LAPPDATA}\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        rf"{_PROGFILES}\Mozilla Firefox\firefox.exe",
        rf"{_PROGFX86}\Mozilla Firefox\firefox.exe",
    ],
    "edge": [
        rf"{_PROGFILES}\Microsoft\Edge\Application\msedge.exe",
        rf"{_PROGFX86}\Microsoft\Edge\Application\msedge.exe",
        r"C:\Windows\SystemApps\Microsoft.MicrosoftEdge_8wekyb3d8bbwe\MicrosoftEdge.exe",
    ],
    "microsoft edge": [
        rf"{_PROGFILES}\Microsoft\Edge\Application\msedge.exe",
    ],
    "spotify": [
        rf"{_APPDATA}\Spotify\Spotify.exe",
        rf"{_LAPPDATA}\Spotify\Spotify.exe",
        rf"{_PROGFILES}\Spotify\Spotify.exe",
    ],
    "discord": [
        rf"{_LAPPDATA}\Discord\Update.exe",
        rf"{_APPDATA}\Discord\Discord.exe",
        rf"{_LAPPDATA}\Discord\app-1.0.9181\Discord.exe",
    ],
    "steam": [
        rf"{_PROGFILES}\Steam\steam.exe",
        rf"{_PROGFX86}\Steam\steam.exe",
        r"C:\Steam\steam.exe",
    ],
    "vlc": [
        rf"{_PROGFILES}\VideoLAN\VLC\vlc.exe",
        rf"{_PROGFX86}\VideoLAN\VLC\vlc.exe",
    ],
    "vs code": [
        rf"{_LAPPDATA}\Programs\Microsoft VS Code\Code.exe",
        rf"{_PROGFILES}\Microsoft VS Code\Code.exe",
    ],
    "visual studio code": [
        rf"{_LAPPDATA}\Programs\Microsoft VS Code\Code.exe",
        rf"{_PROGFILES}\Microsoft VS Code\Code.exe",
    ],
    "word": [
        rf"{_PROGFILES}\Microsoft Office\root\Office16\WINWORD.EXE",
        rf"{_PROGFX86}\Microsoft Office\root\Office16\WINWORD.EXE",
        rf"{_PROGFILES}\Microsoft Office\Office16\WINWORD.EXE",
    ],
    "excel": [
        rf"{_PROGFILES}\Microsoft Office\root\Office16\EXCEL.EXE",
        rf"{_PROGFX86}\Microsoft Office\root\Office16\EXCEL.EXE",
    ],
    "powerpoint": [
        rf"{_PROGFILES}\Microsoft Office\root\Office16\POWERPNT.EXE",
        rf"{_PROGFX86}\Microsoft Office\root\Office16\POWERPNT.EXE",
    ],
    "whatsapp": [
        rf"{_LAPPDATA}\WhatsApp\WhatsApp.exe",
        rf"{_APPDATA}\WhatsApp\WhatsApp.exe",
    ],
    "telegram": [
        rf"{_APPDATA}\Telegram Desktop\Telegram.exe",
        rf"{_LAPPDATA}\Telegram Desktop\Telegram.exe",
    ],
    "zoom": [
        rf"{_APPDATA}\Zoom\bin\Zoom.exe",
        rf"{_LAPPDATA}\Zoom\bin\Zoom.exe",
        rf"{_PROGFILES}\Zoom\bin\Zoom.exe",
    ],
    "teams": [
        rf"{_LAPPDATA}\Microsoft\Teams\current\Teams.exe",
        rf"{_APPDATA}\Microsoft\Teams\current\Teams.exe",
        rf"{_PROGFILES}\Microsoft\Teams\current\Teams.exe",
    ],
    "microsoft teams": [
        rf"{_LAPPDATA}\Microsoft\Teams\current\Teams.exe",
    ],
    "obs": [
        rf"{_PROGFILES}\obs-studio\bin\64bit\obs64.exe",
        rf"{_PROGFX86}\obs-studio\bin\64bit\obs64.exe",
    ],
    "obs studio": [
        rf"{_PROGFILES}\obs-studio\bin\64bit\obs64.exe",
    ],
    "notepad++": [
        rf"{_PROGFILES}\Notepad++\notepad++.exe",
        rf"{_PROGFX86}\Notepad++\notepad++.exe",
    ],
    "7zip": [
        rf"{_PROGFILES}\7-Zip\7zFM.exe",
        rf"{_PROGFX86}\7-Zip\7zFM.exe",
    ],
    "winrar": [
        rf"{_PROGFILES}\WinRAR\WinRAR.exe",
        rf"{_PROGFX86}\WinRAR\WinRAR.exe",
    ],
}


def _resolve_well_known(name: str) -> str | None:
    """Return the first existing path from WELL_KNOWN_PATHS for `name`."""
    candidates = WELL_KNOWN_PATHS.get(name.lower(), [])
    for path in candidates:
        if os.path.isfile(path):
            return path
    return None


class AIAssistant:
    def __init__(self):
        self.data = self._load_data()
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self.is_listening = False
        self.callback = None  # UI callback for status updates
        self._init_speech()
        self._init_tts()

    # ──────────────────────────────────────────────
    #  Persistence
    # ──────────────────────────────────────────────
    def _load_data(self):
        try:
            with open(COMMANDS_FILE, "r") as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {
                "apps": {},
                "custom_commands": {},
                "learned_paths": {},
                "usage_count": {},
                "history": [],
            }

    def _save_data(self):
        with open(COMMANDS_FILE, "w") as f:
            json.dump(self.data, f, indent=4)

    # ──────────────────────────────────────────────
    #  Init
    # ──────────────────────────────────────────────
    def _init_speech(self):
        if SPEECH_AVAILABLE:
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True
            if PYAUDIO_AVAILABLE:
                try:
                    self.microphone = sr.Microphone()
                except Exception:
                    self.microphone = None
            else:
                self.microphone = None  # will use sounddevice path

    def _init_tts(self):
        if TTS_AVAILABLE:
            try:
                self.tts_engine = pyttsx3.init()
                voices = self.tts_engine.getProperty("voices")
                # prefer a female voice if available
                for v in voices:
                    if "female" in v.name.lower() or "zira" in v.name.lower():
                        self.tts_engine.setProperty("voice", v.id)
                        break
                self.tts_engine.setProperty("rate", 175)
                self.tts_engine.setProperty("volume", 0.9)
            except Exception:
                self.tts_engine = None

    # ──────────────────────────────────────────────
    #  TTS
    # ──────────────────────────────────────────────
    def speak(self, text):
        """Speak text in a background thread so the UI never freezes."""
        if self.tts_engine:
            def _run():
                try:
                    self.tts_engine.say(text)
                    self.tts_engine.runAndWait()
                except Exception:
                    pass
            threading.Thread(target=_run, daemon=True).start()

    # ──────────────────────────────────────────────
    #  Microphone / Recognition
    # ──────────────────────────────────────────────
    def listen_once(self):
        """Capture one utterance and return (text, error_message)."""
        if not SPEECH_AVAILABLE:
            return None, "SpeechRecognition not installed."
        if not MIC_AVAILABLE:
            return None, "No audio backend found. Run: pip install sounddevice"

        # ── PyAudio path (standard) ────────────────────────────────────────
        if PYAUDIO_AVAILABLE and self.microphone is not None:
            try:
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                    audio = self.recognizer.listen(source, timeout=8, phrase_time_limit=10)
                text = self.recognizer.recognize_google(audio)
                return text.lower().strip(), None
            except sr.WaitTimeoutError:
                return None, "Listening timed out – no speech detected."
            except sr.UnknownValueError:
                return None, "Could not understand – please speak clearly."
            except sr.RequestError as e:
                return None, f"Speech service error: {e}"
            except Exception as e:
                return None, str(e)

        # ── sounddevice path (Python 3.14 compatible) ──────────────────────
        if SOUNDDEVICE_AVAILABLE:
            try:
                SAMPLE_RATE = 16000
                DURATION    = 7       # seconds to record
                CHANNELS    = 1

                audio_np = sd.rec(
                    int(DURATION * SAMPLE_RATE),
                    samplerate=SAMPLE_RATE,
                    channels=CHANNELS,
                    dtype="int16",
                )
                sd.wait()  # block until recording done

                # Convert numpy array → in-memory WAV → AudioData
                wav_buf = io.BytesIO()
                with wave.open(wav_buf, "wb") as wf:
                    wf.setnchannels(CHANNELS)
                    wf.setsampwidth(2)           # int16 = 2 bytes
                    wf.setframerate(SAMPLE_RATE)
                    wf.writeframes(audio_np.tobytes())
                wav_buf.seek(0)

                with sr.AudioFile(wav_buf) as source:
                    audio_data = self.recognizer.record(source)

                text = self.recognizer.recognize_google(audio_data)
                return text.lower().strip(), None

            except sr.UnknownValueError:
                return None, "Could not understand – please speak clearly."
            except sr.RequestError as e:
                return None, f"Speech service error: {e}"
            except Exception as e:
                return None, str(e)

        return None, "No microphone backend available."

    # ──────────────────────────────────────────────
    #  Command Processing
    # ──────────────────────────────────────────────
    def process_command(self, command: str) -> str:
        """Parse and execute a command. Returns a human-readable response."""
        command_raw = command.strip()
        command = command_raw.lower()
        self._log_history(command)

        # ── greetings ──────────────────────────────
        for word in ("hello", "hi", "hey"):
            if command.startswith(word):
                msg = "Hello! How can I help you today?"
                self.speak(msg)
                return msg

        # ── time / date ────────────────────────────
        if any(k in command for k in ("what time", "current time", "tell me the time")):
            now = datetime.datetime.now().strftime("%I:%M %p")
            msg = f"The current time is {now}."
            self.speak(msg)
            return msg

        if any(k in command for k in ("what date", "today's date", "what day")):
            today = datetime.datetime.now().strftime("%A, %B %d, %Y")
            msg = f"Today is {today}."
            self.speak(msg)
            return msg

        # ── price check ────────────────────────────
        m = re.match(r"(?:price of|check price of|how much (?:does|is|costs?)|price for|cost of)\s+(.+)", command)
        if m:
            return self._check_price(m.group(1).strip())

        # ── website open (explicit) ─────────────────
        for keyword in ("go to ", "visit ", "open site ", "open website "):
            if command.startswith(keyword):
                target = command_raw[len(keyword):].strip()
                return self._open_website(target)

        # ── code / file operations ─────────────────
        if command.startswith("read file "):
            return self._code_read(command_raw[len("read file "):].strip())

        if command.startswith("open file "):
            return self._code_open_in_editor(command_raw[len("open file "):].strip())

        m2 = re.match(r"create file (.+?) with content (.+)", command_raw, re.IGNORECASE)
        if m2:
            return self._code_create(m2.group(1).strip(), m2.group(2).strip())

        m3 = re.match(r"rewrite file (.+?) replace (.+?) with (.+)", command_raw, re.IGNORECASE)
        if m3:
            return self._code_rewrite(m3.group(1).strip(), m3.group(2).strip(), m3.group(3).strip())

        if re.match(r"run file ", command):
            return self._code_run(command_raw[len("run file "):].strip())

        m4 = re.match(r"(?:show|list) files? (?:in|at) (.+)", command_raw, re.IGNORECASE)
        if m4:
            return self._list_files(m4.group(1).strip())

        # ── open app (also tries named website first) ─
        for keyword in ("open ", "launch ", "start ", "run "):
            if command.startswith(keyword):
                target = command_raw[len(keyword):].strip()
                site_result = self._try_open_as_website(target.lower())
                if site_result:
                    return site_result
                return self._open_app(target)

        # ── search ─────────────────────────────────
        for keyword in ("search for ", "search ", "google ", "look up ", "find "):
            if command.startswith(keyword):
                query = command[len(keyword):].strip()
                return self._web_search(query)

        # ── teach / learn ──────────────────────────
        if command.startswith("learn ") or command.startswith("remember "):
            return self._learn_command(command)

        # ── list known apps ────────────────────────
        if any(k in command for k in ("what apps", "list apps", "show apps", "which apps")):
            apps = list(self.data["apps"].keys()) + list(self.data["learned_paths"].keys())
            msg = "I know these apps: " + ", ".join(sorted(apps)[:20])
            self.speak(msg)
            return msg

        # ── help ───────────────────────────────────
        if "help" in command or "what can you do" in command:
            msg = (
                "You can say:\n"
                "• 'Open [app name]' – opens an application\n"
                "• 'Open YouTube' / 'Go to GitHub' – opens a website (80+ known!)\n"
                "• 'Search for [query]' – web search\n"
                "• 'Price of [item]' – checks Amazon, Flipkart & Google Shopping\n"
                "• 'Read file [path]' – read a file\n"
                "• 'Open file [path]' – open in VS Code / Notepad\n"
                "• 'Create file [path] with content [text]' – create a file\n"
                "• 'Rewrite file [path] replace [old] with [new]' – edit a file\n"
                "• 'Run file [path]' – run a Python/.bat/.ps1 script\n"
                "• 'List files in [folder]' – browse a directory\n"
                "• 'What time is it?' – current time\n"
                "• 'Learn [keyword] open [path]' – teach me a new app"
            )
            self.speak("I can open apps and websites, check prices, read and edit files, run scripts, and much more.")
            return msg

        # ── fallback: try to open as app name ──────
        result = self._open_app(command)
        if "❌" not in result:
            return result

        # ── ultimate fallback: web search ──────────
        msg = f"I'm not sure what you mean by '{command}'. Searching the web instead…"
        self.speak(msg)
        self._web_search(command)
        return msg

    # ──────────────────────────────────────────────
    #  Website Opening
    # ──────────────────────────────────────────────
    def _try_open_as_website(self, name: str) -> str | None:
        """Return a response string if name matches a known website, else None."""
        name = name.lower().strip()
        if name in WEBSITE_MAP:
            url = WEBSITE_MAP[name]
            webbrowser.open(url)
            msg = f"🌐 Opening {name.title()} → {url}"
            self.speak(f"Opening {name}")
            return msg
        return None

    def _open_website(self, target: str) -> str:
        """Open a website by name or direct URL."""
        t = target.lower().strip()
        if t in WEBSITE_MAP:
            url = WEBSITE_MAP[t]
            webbrowser.open(url)
            msg = f"🌐 Opening {t.title()} → {url}"
            self.speak(f"Opening {t}")
            return msg
        # Looks like a URL?
        if "." in target and " " not in target:
            url = target if target.startswith("http") else f"https://{target}"
            webbrowser.open(url)
            msg = f"🌐 Opening {url}"
            self.speak(f"Opening {target}")
            return msg
        # Fuzzy match against known sites
        for name, url in WEBSITE_MAP.items():
            if t in name or name in t:
                webbrowser.open(url)
                msg = f"🌐 Opening {name.title()} → {url}"
                self.speak(f"Opening {name}")
                return msg
        msg = f"❌ Unknown website '{target}'. Try: 'open site youtube' or 'go to github.com'"
        return msg

    # ──────────────────────────────────────────────
    #  Price Checker
    # ──────────────────────────────────────────────
    def _check_price(self, product: str) -> str:
        """Open price search pages on Amazon, Flipkart, and Google Shopping."""
        q = quote_plus(product)
        amazon_url   = f"https://www.amazon.in/s?k={q}"
        flipkart_url = f"https://www.flipkart.com/search?q={q}"
        google_url   = f"https://www.google.com/search?q={quote_plus(product + ' price india')}&tbm=shop"
        webbrowser.open(google_url)
        time.sleep(0.4)
        webbrowser.open(amazon_url)
        time.sleep(0.4)
        webbrowser.open(flipkart_url)
        msg = (
            f"💰 Searching prices for: {product}\n"
            f"   Opened: Google Shopping, Amazon.in, Flipkart\n"
            f"   Check your browser for the best deals!"
        )
        self.speak(f"Searching prices for {product} on Amazon and Flipkart")
        return msg

    # ──────────────────────────────────────────────
    #  Code / File Operations
    # ──────────────────────────────────────────────
    def _code_read(self, filepath: str) -> str:
        """Read and return the contents of a file."""
        path = Path(filepath)
        if not path.exists():
            self.speak("File not found")
            return f"❌ File not found: {filepath}"
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            preview = "\n".join(lines[:50])
            suffix = f"\n… ({len(lines) - 50} more lines)" if len(lines) > 50 else ""
            msg = f"📄 {path.name} ({len(lines)} lines):\n\n{preview}{suffix}"
            self.speak(f"Reading {path.name}, {len(lines)} lines")
            return msg
        except Exception as e:
            return f"❌ Could not read file: {e}"

    def _code_open_in_editor(self, filepath: str) -> str:
        """Open a file in VS Code if available, else Notepad."""
        path = Path(filepath)
        if not path.exists():
            return f"❌ File not found: {filepath}"
        vscode = _resolve_well_known("vs code")
        if vscode:
            subprocess.Popen([vscode, str(path)])
            self.speak(f"Opening {path.name} in VS Code")
            return f"📝 Opened in VS Code: {path.name}"
        subprocess.Popen(["notepad.exe", str(path)])
        self.speak(f"Opening {path.name} in Notepad")
        return f"📝 Opened in Notepad: {path.name}"

    def _code_create(self, filepath: str, content: str) -> str:
        """Create a new file with the given content."""
        path = Path(filepath)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
            msg = f"✅ Created file: {path}\n   Content: {content[:80]}{'…' if len(content) > 80 else ''}"
            self.speak(f"Created {path.name}")
            return msg
        except Exception as e:
            return f"❌ Failed to create file: {e}"

    def _code_rewrite(self, filepath: str, old_text: str, new_text: str) -> str:
        """Replace old_text with new_text inside a file."""
        path = Path(filepath)
        if not path.exists():
            return f"❌ File not found: {filepath}"
        try:
            content = path.read_text(encoding="utf-8")
            count = content.count(old_text)
            if count == 0:
                return f"⚠️ Text not found in {path.name}: '{old_text}'"
            new_content = content.replace(old_text, new_text)
            path.write_text(new_content, encoding="utf-8")
            msg = f"✅ Rewrote {path.name}: replaced {count} occurrence(s)\n   '{old_text}' → '{new_text}'"
            self.speak(f"Rewrote {path.name}")
            return msg
        except Exception as e:
            return f"❌ Failed to rewrite file: {e}"

    def _code_run(self, filepath: str) -> str:
        """Execute a Python, batch, or PowerShell file and return output."""
        path = Path(filepath)
        if not path.exists():
            return f"❌ File not found: {filepath}"
        ext = path.suffix.lower()
        try:
            if ext == ".py":
                result = subprocess.run(
                    ["python", str(path)],
                    capture_output=True, text=True, timeout=30
                )
            elif ext in (".bat", ".cmd"):
                result = subprocess.run(
                    ["cmd", "/c", str(path)],
                    capture_output=True, text=True, timeout=30
                )
            elif ext == ".ps1":
                result = subprocess.run(
                    ["powershell", "-File", str(path)],
                    capture_output=True, text=True, timeout=30
                )
            else:
                subprocess.Popen(str(path), shell=True)
                return f"✅ Launched: {path.name}"
            output = ((result.stdout or "") + (result.stderr or "")).strip()[:500]
            icon = "✅" if result.returncode == 0 else "❌"
            msg = f"{icon} Ran {path.name} (exit {result.returncode}):\n{output if output else '(no output)'}"
            self.speak(f"Ran {path.name}")
            return msg
        except subprocess.TimeoutExpired:
            return f"⏱️ {path.name} timed out after 30 seconds."
        except Exception as e:
            return f"❌ Failed to run {path.name}: {e}"

    def _list_files(self, dirpath: str) -> str:
        """List files and folders in a directory."""
        path = Path(dirpath)
        if not path.exists():
            return f"❌ Directory not found: {dirpath}"
        if not path.is_dir():
            return f"❌ Not a directory: {dirpath}"
        try:
            items = list(path.iterdir())
            dirs  = sorted([i for i in items if i.is_dir()], key=lambda x: x.name)
            files = sorted([i for i in items if i.is_file()], key=lambda x: x.name)
            lines = [f"📁 {path} ({len(items)} items):"]
            for d in dirs[:20]:
                lines.append(f"  📂 {d.name}/")
            for f in files[:30]:
                size = f.stat().st_size
                size_str = f"{size/1024:.1f} KB" if size > 1024 else f"{size} B"
                lines.append(f"  📄 {f.name}  ({size_str})")
            if len(items) > 50:
                lines.append(f"  … and {len(items)-50} more items")
            self.speak(f"Found {len(items)} items in {path.name}")
            return "\n".join(lines)
        except Exception as e:
            return f"❌ Could not list directory: {e}"

    # ──────────────────────────────────────────────
    #  App Opening
    # ──────────────────────────────────────────────
    def _open_app(self, app_name: str) -> str:
        name_lower = app_name.lower().strip()

        # 1. Check learned paths first (user-taught)
        if name_lower in self.data.get("learned_paths", {}):
            path = self.data["learned_paths"][name_lower]
            return self._launch(path, app_name)

        # 2. Check well-known full paths (Chrome, Edge, Spotify, etc.)
        well_known = _resolve_well_known(name_lower)
        if well_known:
            self._remember_path(name_lower, well_known)  # cache for next time
            return self._launch(well_known, app_name)

        # 3. Check built-in app dict (system apps like notepad, calc, etc.)
        if name_lower in self.data.get("apps", {}):
            exe = self.data["apps"][name_lower]
            # Try as-is (relies on PATH / Windows app resolution)
            result = self._launch(exe, app_name)
            if "❌" not in result:
                return result
            # If failed, try to find it on disk
            found = self._find_executable(exe)
            if found:
                self._remember_path(name_lower, found)
                return self._launch(found, app_name)
            return result

        # 4. Fuzzy match against known names
        fuzzy = self._fuzzy_find_app(name_lower)
        if fuzzy:
            return self._open_app(fuzzy)

        # 5. Try shutil.which / disk search
        found = self._find_executable(name_lower + ".exe")
        if found:
            self._remember_path(name_lower, found)
            return self._launch(found, app_name)

        msg = f"❌ Could not find '{app_name}'. Use the 'Teach new app' form to add it!"
        self.speak(f"I couldn't find {app_name}.")
        return msg

    def _launch(self, path_or_exe: str, friendly_name: str) -> str:
        try:
            subprocess.Popen(path_or_exe, shell=True)
            self._increment_usage(friendly_name)
            msg = f"✅ Opening {friendly_name}…"
            self.speak(f"Opening {friendly_name}")
            return msg
        except Exception as e:
            return f"❌ Failed to open {friendly_name}: {e}"

    def _find_executable(self, exe_name: str) -> str | None:
        """Search common paths for an executable."""
        # shutil.which covers PATH
        found = shutil.which(exe_name)
        if found:
            return found
        # Search common directories
        for base in APP_SEARCH_PATHS:
            for root, dirs, files in os.walk(base):
                for f in files:
                    if f.lower() == exe_name.lower() or f.lower() == exe_name.lower() + ".exe":
                        return os.path.join(root, f)
                # Don't go too deep
                if root.count(os.sep) - base.count(os.sep) > 3:
                    del dirs[:]
        return None

    def _fuzzy_find_app(self, query: str) -> str | None:
        """Return the best matching known app name."""
        all_names = list(self.data.get("apps", {}).keys()) + list(self.data.get("learned_paths", {}).keys())
        for name in all_names:
            if query in name or name in query:
                return name
        return None

    # ──────────────────────────────────────────────
    #  Web Search
    # ──────────────────────────────────────────────
    def _web_search(self, query: str) -> str:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        webbrowser.open(url)
        msg = f"🔍 Searching for: {query}"
        self.speak(f"Searching for {query}")
        return msg

    # ──────────────────────────────────────────────
    #  Learning
    # ──────────────────────────────────────────────
    def _learn_command(self, command: str) -> str:
        """
        Syntax: 'learn <keyword> open <path>'
                'remember <keyword> as <path>'
        """
        # Try: learn X open Y
        m = re.search(r"(?:learn|remember)\s+(.+?)\s+(?:open|as|=)\s+(.+)", command)
        if m:
            keyword = m.group(1).strip().lower()
            path = m.group(2).strip()
            self._remember_path(keyword, path)
            msg = f"✅ Got it! I'll remember '{keyword}' → '{path}'"
            self.speak(f"Got it, I'll remember {keyword}.")
            return msg
        msg = "📚 To teach me, say: 'Learn [name] open [full path to app]'"
        self.speak(msg)
        return msg

    def _remember_path(self, keyword: str, path: str):
        self.data.setdefault("learned_paths", {})[keyword] = path
        self._save_data()

    # ──────────────────────────────────────────────
    #  Stats / History
    # ──────────────────────────────────────────────
    def _increment_usage(self, name: str):
        self.data.setdefault("usage_count", {})
        self.data["usage_count"][name] = self.data["usage_count"].get(name, 0) + 1
        self._save_data()

    def _log_history(self, command: str):
        entry = {"time": datetime.datetime.now().isoformat(), "command": command}
        self.data.setdefault("history", []).append(entry)
        # keep last 200 entries
        self.data["history"] = self.data["history"][-200:]
        self._save_data()

    def get_top_commands(self, n=5):
        counts = self.data.get("usage_count", {})
        return sorted(counts.items(), key=lambda x: x[1], reverse=True)[:n]

    def get_recent_history(self, n=10):
        return self.data.get("history", [])[-n:]
