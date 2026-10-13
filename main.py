import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
import threading
import time
import os
import sys
import queue

from assistant import AIAssistant, SPEECH_AVAILABLE, TTS_AVAILABLE, MIC_AVAILABLE, SOUNDDEVICE_AVAILABLE, PYAUDIO_AVAILABLE

# ── Colour palette ────────────────────────────────────────────────────────────
BG_DARK      = "#0d0d1a"
BG_PANEL     = "#12122a"
BG_CARD      = "#1a1a35"
ACCENT       = "#7c3aed"      # violet
ACCENT2      = "#06b6d4"      # cyan
SUCCESS      = "#10b981"
WARNING      = "#f59e0b"
DANGER       = "#ef4444"
TEXT_PRIMARY = "#f1f5f9"
TEXT_MUTED   = "#94a3b8"
BORDER       = "#2d2d5a"

# ── Fonts (fall back to system fonts gracefully) ──────────────────────────────
def _font(size, weight="normal", family="Segoe UI"):
    return (family, size, weight)


class PulseButton(tk.Canvas):
    """Circular mic button with an animated pulse ring."""

    def __init__(self, master, command, **kwargs):
        size = 110
        super().__init__(master, width=size, height=size,
                         bg=BG_DARK, highlightthickness=0, **kwargs)
        self.size = size
        self.command = command
        self._pulse_r = 0
        self._active = False
        self._anim_id = None
        self._draw_idle()
        self.bind("<Button-1>", lambda e: self.command())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)

    def _draw_idle(self):
        self.delete("all")
        cx = cy = self.size // 2
        r = 40
        # outer glow
        self.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                         fill="#1e0a4a", outline=ACCENT, width=2)
        # main circle
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=ACCENT, outline="", tags="btn")
        # mic icon (simple rectangle + arc)
        self.create_rectangle(cx - 8, cy - 18, cx + 8, cy + 8,
                              fill=TEXT_PRIMARY, outline="")
        self.create_arc(cx - 14, cy - 4, cx + 14, cy + 18,
                        start=0, extent=-180, fill=TEXT_PRIMARY, outline="")
        self.create_line(cx, cy + 18, cx, cy + 26, fill=TEXT_PRIMARY, width=3)
        self.create_line(cx - 10, cy + 26, cx + 10, cy + 26,
                         fill=TEXT_PRIMARY, width=3)

    def _draw_active(self, pulse_r):
        self.delete("all")
        cx = cy = self.size // 2
        r = 40
        # animated pulse ring
        alpha_rings = [pulse_r, pulse_r - 12, pulse_r - 24]
        colors = [ACCENT2, "#0891b2", "#0e7490"]
        for pr, col in zip(alpha_rings, colors):
            if pr > 0:
                self.create_oval(cx - pr, cy - pr, cx + pr, cy + pr,
                                 fill="", outline=col, width=2)
        # glowing circle
        self.create_oval(cx - r - 8, cy - r - 8, cx + r + 8, cy + r + 8,
                         fill="#0c1a3a", outline=ACCENT2, width=3)
        self.create_oval(cx - r, cy - r, cx + r, cy + r,
                         fill=ACCENT2, outline="")
        # mic icon
        self.create_rectangle(cx - 8, cy - 18, cx + 8, cy + 8,
                              fill=TEXT_PRIMARY, outline="")
        self.create_arc(cx - 14, cy - 4, cx + 14, cy + 18,
                        start=0, extent=-180, fill=TEXT_PRIMARY, outline="")
        self.create_line(cx, cy + 18, cx, cy + 26, fill=TEXT_PRIMARY, width=3)
        self.create_line(cx - 10, cy + 26, cx + 10, cy + 26,
                         fill=TEXT_PRIMARY, width=3)

    def set_active(self, active: bool):
        self._active = active
        if active:
            self._pulse_r = 45
            self._animate()
        else:
            if self._anim_id:
                self.after_cancel(self._anim_id)
                self._anim_id = None
            self._draw_idle()

    def _animate(self):
        if not self._active:
            return
        self._pulse_r += 1.5
        if self._pulse_r > 60:
            self._pulse_r = 45
        self._draw_active(self._pulse_r)
        self._anim_id = self.after(30, self._animate)

    def _on_enter(self, _):
        if not self._active:
            self.configure(cursor="hand2")

    def _on_leave(self, _):
        pass


class HistoryFrame(tk.Frame):
    """Scrollable log of past commands and responses."""

    def __init__(self, master, **kwargs):
        super().__init__(master, bg=BG_CARD, **kwargs)
        # header
        tk.Label(self, text="📋  Command History", bg=BG_CARD,
                 fg=TEXT_MUTED, font=_font(9, "bold")).pack(anchor="w", padx=10, pady=(8, 2))
        # scrollable text
        self.text = tk.Text(self, bg=BG_CARD, fg=TEXT_PRIMARY,
                            font=_font(9), bd=0, relief="flat",
                            wrap="word", state="disabled", cursor="arrow")
        sb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.text.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # colour tags
        self.text.tag_configure("user",     foreground=ACCENT2,  font=_font(9, "bold"))
        self.text.tag_configure("response", foreground=TEXT_PRIMARY, font=_font(9))
        self.text.tag_configure("error",    foreground=DANGER,   font=_font(9))
        self.text.tag_configure("ts",       foreground=TEXT_MUTED, font=_font(8))

    def add(self, user_text: str, response: str):
        import datetime
        self.text.configure(state="normal")
        ts = datetime.datetime.now().strftime("%H:%M:%S")
        self.text.insert("end", f"[{ts}]  ", "ts")
        self.text.insert("end", f"🎙 {user_text}\n", "user")
        tag = "error" if "❌" in response else "response"
        self.text.insert("end", f"   {response}\n\n", tag)
        self.text.configure(state="disabled")
        self.text.see("end")


class StatsFrame(tk.Frame):
    """Shows top-used apps and quick capability overview."""

    def __init__(self, master, assistant: AIAssistant, **kwargs):
        super().__init__(master, bg=BG_CARD, **kwargs)
        self.assistant = assistant
        tk.Label(self, text="📊  Top Commands", bg=BG_CARD,
                 fg=TEXT_MUTED, font=_font(9, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        self.list_var = tk.StringVar()
        self.listbox = tk.Listbox(self, listvariable=self.list_var,
                                  bg=BG_CARD, fg=TEXT_PRIMARY,
                                  selectbackground=ACCENT, selectforeground=TEXT_PRIMARY,
                                  font=_font(9), bd=0, relief="flat",
                                  highlightthickness=0, height=6)
        self.listbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.refresh()

    def refresh(self):
        top = self.assistant.get_top_commands(6)
        if top:
            entries = [f"{i+1}. {name}  ×{cnt}" for i, (name, cnt) in enumerate(top)]
        else:
            entries = ["No commands used yet."]
        self.list_var.set(entries)


class MainApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("ARIA – AI Voice Assistant")
        self.geometry("820x680")
        self.minsize(700, 560)
        self.configure(bg=BG_DARK)
        self.resizable(True, True)

        # centre on screen
        self.update_idletasks()
        x = (self.winfo_screenwidth() - 820) // 2
        y = (self.winfo_screenheight() - 680) // 2
        self.geometry(f"820x680+{x}+{y}")

        self.assistant = AIAssistant()
        self._listening = False
        self._msg_queue: queue.Queue = queue.Queue()

        self._build_ui()
        self._poll_queue()
        self._update_status_bar()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # ── UI construction ────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── top bar ──────────────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=BG_PANEL, height=58)
        topbar.pack(fill="x")
        topbar.pack_propagate(False)

        tk.Label(topbar, text="  🤖  ARIA", bg=BG_PANEL,
                 fg=TEXT_PRIMARY, font=_font(16, "bold")).pack(side="left", padx=16, pady=12)
        tk.Label(topbar, text="AI Voice Assistant  •  Always Learning",
                 bg=BG_PANEL, fg=TEXT_MUTED, font=_font(9)).pack(side="left")

        # version badge
        badge = tk.Label(topbar, text=" v2.0 ", bg=ACCENT, fg=TEXT_PRIMARY,
                         font=_font(8, "bold"), padx=6, pady=2)
        badge.pack(side="right", padx=16, pady=16)

        # ── main split ───────────────────────────────────────────────────────
        body = tk.Frame(self, bg=BG_DARK)
        body.pack(fill="both", expand=True, padx=12, pady=8)

        # left column
        left = tk.Frame(body, bg=BG_DARK)
        left.pack(side="left", fill="both", expand=True)

        # right sidebar
        right = tk.Frame(body, bg=BG_DARK, width=220)
        right.pack(side="right", fill="y", padx=(8, 0))
        right.pack_propagate(False)

        self._build_left(left)
        self._build_right(right)

        # ── status bar ───────────────────────────────────────────────────────
        self.statusbar = tk.Label(self, text="Ready", bg=BG_PANEL,
                                  fg=TEXT_MUTED, font=_font(8),
                                  anchor="w", padx=12)
        self.statusbar.pack(fill="x", side="bottom")

    def _build_left(self, parent):
        # ── voice display card ───────────────────────────────────────────────
        card = tk.Frame(parent, bg=BG_CARD, bd=0)
        card.pack(fill="x", pady=(0, 8))

        # waveform label (decorative)
        self.wave_label = tk.Label(card, text="───── Ready to listen ─────",
                                   bg=BG_CARD, fg=TEXT_MUTED, font=_font(9))
        self.wave_label.pack(pady=(14, 0))

        # recognised text display
        self.heard_var = tk.StringVar(value="Press the mic or type a command below")
        heard_lbl = tk.Label(card, textvariable=self.heard_var,
                             bg=BG_CARD, fg=ACCENT2,
                             font=_font(12, "bold"), wraplength=460, justify="center")
        heard_lbl.pack(pady=(6, 0), padx=20)

        # response display
        self.resp_var = tk.StringVar(value="")
        resp_lbl = tk.Label(card, textvariable=self.resp_var,
                            bg=BG_CARD, fg=TEXT_PRIMARY,
                            font=_font(10), wraplength=460, justify="center")
        resp_lbl.pack(pady=(6, 14), padx=20)

        # ── pulse mic button ─────────────────────────────────────────────────
        btn_row = tk.Frame(parent, bg=BG_DARK)
        btn_row.pack(pady=4)

        self.mic_btn = PulseButton(btn_row, command=self._toggle_listen)
        self.mic_btn.pack(side="left", padx=16)

        shortcuts = tk.Frame(btn_row, bg=BG_DARK)
        shortcuts.pack(side="left", padx=8)

        lbl_hint = tk.Label(shortcuts, text="Quick actions:", bg=BG_DARK,
                            fg=TEXT_MUTED, font=_font(8))
        lbl_hint.pack(anchor="w")

        quick_cmds = [
            ("🕐  Time", "what time is it"),
            ("📅  Date", "what date is it"),
            ("📱  List Apps", "what apps do you know"),
            ("❓  Help", "help"),
            ("🌐  YouTube", "open youtube"),
            ("🌐  GitHub", "open github"),
            ("🌐  Gmail", "open gmail"),
            ("💰  Price Check", "price of "),
            ("📂  List Files", "list files in d:\\"),
        ]
        for label, cmd in quick_cmds:
            b = tk.Button(shortcuts, text=label,
                          bg=BG_CARD, fg=TEXT_PRIMARY,
                          font=_font(8), relief="flat", bd=0,
                          cursor="hand2", padx=10, pady=4,
                          activebackground=ACCENT, activeforeground=TEXT_PRIMARY,
                          command=lambda c=cmd: self._run_text_command(c))
            b.pack(fill="x", pady=2)

        # ── text input ───────────────────────────────────────────────────────
        input_row = tk.Frame(parent, bg=BG_DARK)
        input_row.pack(fill="x", pady=(6, 0))

        self.text_input = tk.Entry(input_row, bg=BG_CARD, fg=TEXT_PRIMARY,
                                   insertbackground=ACCENT2,
                                   font=_font(11), relief="flat", bd=0)
        self.text_input.pack(side="left", fill="x", expand=True,
                              ipady=10, ipadx=10)
        self.text_input.bind("<Return>", lambda e: self._submit_text())
        self.text_input.insert(0, "Type a command and press Enter…")
        self.text_input.configure(fg=TEXT_MUTED)
        self.text_input.bind("<FocusIn>", self._clear_placeholder)
        self.text_input.bind("<FocusOut>", self._restore_placeholder)

        send_btn = tk.Button(input_row, text="  Send  ",
                             bg=ACCENT, fg=TEXT_PRIMARY,
                             font=_font(10, "bold"), relief="flat", bd=0,
                             cursor="hand2", padx=14, pady=10,
                             activebackground="#6d28d9",
                             command=self._submit_text)
        send_btn.pack(side="right", padx=(6, 0))

        # ── learn new command ─────────────────────────────────────────────────
        learn_row = tk.Frame(parent, bg=BG_DARK)
        learn_row.pack(fill="x", pady=(6, 0))

        tk.Label(learn_row, text="Teach new app:", bg=BG_DARK,
                 fg=TEXT_MUTED, font=_font(8)).pack(side="left", padx=(0, 6))

        self.learn_name = tk.Entry(learn_row, bg=BG_CARD, fg=TEXT_PRIMARY,
                                   insertbackground=ACCENT2,
                                   font=_font(9), relief="flat", width=14)
        self.learn_name.pack(side="left", ipady=6, ipadx=6)
        tk.Label(learn_row, text="→  Path:", bg=BG_DARK,
                 fg=TEXT_MUTED, font=_font(8)).pack(side="left", padx=6)
        self.learn_path = tk.Entry(learn_row, bg=BG_CARD, fg=TEXT_PRIMARY,
                                   insertbackground=ACCENT2,
                                   font=_font(9), relief="flat", width=22)
        self.learn_path.pack(side="left", ipady=6, ipadx=6)

        teach_btn = tk.Button(learn_row, text="Teach",
                              bg=SUCCESS, fg=TEXT_PRIMARY,
                              font=_font(9, "bold"), relief="flat", bd=0,
                              cursor="hand2", padx=10, pady=6,
                              activebackground="#059669",
                              command=self._teach_app)
        teach_btn.pack(side="left", padx=(6, 0))

        # ── history ───────────────────────────────────────────────────────────
        self.history_frame = HistoryFrame(parent)
        self.history_frame.pack(fill="both", expand=True, pady=(10, 0))

    def _build_right(self, parent):
        # ── stats ────────────────────────────────────────────────────────────
        self.stats_frame = StatsFrame(parent, self.assistant)
        self.stats_frame.pack(fill="x", pady=(0, 8))

        # ── capabilities ─────────────────────────────────────────────────────
        caps = tk.Frame(parent, bg=BG_CARD)
        caps.pack(fill="x", pady=(0, 8))
        tk.Label(caps, text="⚡  Capabilities", bg=BG_CARD,
                 fg=TEXT_MUTED, font=_font(9, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        items = [
            ("🎤", "Voice commands"),
            ("🔊", "Text-to-speech"),
            ("📂", "Open any app"),
            ("🌐", "80+ named websites"),
            ("🔍", "Web search"),
            ("💰", "Price checker"),
            ("📄", "Read & edit files"),
            ("▶️", "Run scripts"),
            ("🧠", "Learns & remembers"),
            ("📊", "Usage stats"),
        ]
        for icon, text in items:
            row = tk.Frame(caps, bg=BG_CARD)
            row.pack(fill="x", padx=10, pady=1)
            tk.Label(row, text=icon, bg=BG_CARD, font=_font(10)).pack(side="left")
            tk.Label(row, text=text, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=_font(9)).pack(side="left", padx=6)
        tk.Frame(caps, bg=BG_CARD, height=8).pack()

        # ── mic info ─────────────────────────────────────────────────────────
        mic_info = tk.Frame(parent, bg=BG_CARD)
        mic_info.pack(fill="x", pady=(0, 8))
        tk.Label(mic_info, text="🎙  Microphone", bg=BG_CARD,
                 fg=TEXT_MUTED, font=_font(9, "bold")).pack(anchor="w", padx=10, pady=(8, 2))

        if PYAUDIO_AVAILABLE:
            mic_status = "✅  PyAudio (full)"
            mic_col = SUCCESS
        elif SOUNDDEVICE_AVAILABLE:
            mic_status = "✅  sounddevice (active)"
            mic_col = SUCCESS
        else:
            mic_status = "❌  No audio backend\n(pip install sounddevice)"
            mic_col = DANGER

        tk.Label(mic_info, text=mic_status, bg=BG_CARD, fg=mic_col,
                 font=_font(9), justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        tts_status = "✅  Available" if TTS_AVAILABLE else "❌  Not available"
        tts_col = SUCCESS if TTS_AVAILABLE else DANGER
        tk.Label(mic_info, text=f"🔊  TTS: {tts_status}", bg=BG_CARD, fg=tts_col,
                 font=_font(9), justify="left").pack(anchor="w", padx=10, pady=(0, 8))

        # ── help card ────────────────────────────────────────────────────────
        help_card = tk.Frame(parent, bg=BG_CARD)
        help_card.pack(fill="x")
        tk.Label(help_card, text="💡  Example Commands", bg=BG_CARD,
                 fg=TEXT_MUTED, font=_font(9, "bold")).pack(anchor="w", padx=10, pady=(8, 4))
        examples = [
            '"Open YouTube"',
            '"Go to GitHub"',
            '"Price of iPhone 15"',
            '"Read file main.py"',
            '"Open file d:\\mycode.py"',
            '"Create file hi.py with content print(hi)"',
            '"Rewrite file app.py replace hello with world"',
            '"Run file script.py"',
            '"List files in d:\\"',
            '"Open Chrome"',
            '"Search for Python"',
        ]
        for ex in examples:
            tk.Label(help_card, text=ex, bg=BG_CARD, fg=ACCENT2,
                     font=_font(8), justify="left").pack(anchor="w", padx=14, pady=1)
        tk.Frame(help_card, bg=BG_CARD, height=8).pack()

    # ── Event handlers ─────────────────────────────────────────────────────────
    def _clear_placeholder(self, _):
        if self.text_input.get() == "Type a command and press Enter…":
            self.text_input.delete(0, "end")
            self.text_input.configure(fg=TEXT_PRIMARY)

    def _restore_placeholder(self, _):
        if not self.text_input.get():
            self.text_input.insert(0, "Type a command and press Enter…")
            self.text_input.configure(fg=TEXT_MUTED)

    def _submit_text(self):
        text = self.text_input.get().strip()
        if not text or text == "Type a command and press Enter…":
            return
        self.text_input.delete(0, "end")
        self._run_text_command(text)

    def _run_text_command(self, command: str):
        self.heard_var.set(f'🎙 "{command}"')
        self.resp_var.set("Processing…")
        threading.Thread(target=self._process, args=(command,), daemon=True).start()

    def _toggle_listen(self):
        if self._listening:
            return  # already listening; ignore double-click
        if not MIC_AVAILABLE:
            self._show_error("No microphone backend found.\nRun: pip install sounddevice")
            return
        self._listening = True
        self.mic_btn.set_active(True)
        self.wave_label.configure(text="─── Listening… speak now ───", fg=ACCENT2)
        self.heard_var.set("🎤 Listening…")
        self.resp_var.set("")
        threading.Thread(target=self._listen_thread, daemon=True).start()

    def _listen_thread(self):
        text, err = self.assistant.listen_once()
        self._msg_queue.put(("listened", text, err))

    def _process(self, command: str):
        response = self.assistant.process_command(command)
        self._msg_queue.put(("response", command, response))

    # ── Queue polling (thread-safe UI updates) ─────────────────────────────────
    def _poll_queue(self):
        try:
            while True:
                msg = self._msg_queue.get_nowait()
                kind = msg[0]

                if kind == "listened":
                    _, text, err = msg
                    self._listening = False
                    self.mic_btn.set_active(False)
                    self.wave_label.configure(text="───── Ready to listen ─────", fg=TEXT_MUTED)
                    if err:
                        self.heard_var.set(f"⚠️ {err}")
                        self.resp_var.set("")
                    else:
                        self.heard_var.set(f'🎙 "{text}"')
                        self.resp_var.set("Processing…")
                        threading.Thread(target=self._process, args=(text,), daemon=True).start()

                elif kind == "response":
                    _, command, response = msg
                    self.resp_var.set(response[:120] + ("…" if len(response) > 120 else ""))
                    self.history_frame.add(command, response)
                    self.stats_frame.refresh()

        except Exception:
            pass
        self.after(80, self._poll_queue)

    def _update_status_bar(self):
        import datetime
        now = datetime.datetime.now().strftime("%H:%M:%S")
        known = len(self.assistant.data.get("apps", {})) + len(self.assistant.data.get("learned_paths", {}))
        self.statusbar.configure(
            text=f"  🕐 {now}   |   📦 {known} apps known   |   🧠 Learning enabled"
        )
        self.after(1000, self._update_status_bar)

    def _teach_app(self):
        name = self.learn_name.get().strip().lower()
        path = self.learn_path.get().strip()
        if not name or not path:
            self._show_error("Please fill in both the app name and the path.")
            return
        self.assistant._remember_path(name, path)
        self.learn_name.delete(0, "end")
        self.learn_path.delete(0, "end")
        msg = f"✅ Taught: '{name}' → '{path}'"
        self.resp_var.set(msg)
        self.history_frame.add(f"[Teach] {name}", msg)
        self.stats_frame.refresh()
        self.assistant.speak(f"Got it, I'll remember {name}")

    def _show_error(self, msg: str):
        messagebox.showerror("ARIA – Error", msg, parent=self)

    def _on_close(self):
        self.destroy()


# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    app = MainApp()
    app.mainloop()
