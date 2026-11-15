#!/usr/bin/env python3
"""Decode three hand-pair photos or live three-second holds; optionally save captures."""
from __future__ import annotations

import argparse
from collections import deque
import csv
from pathlib import Path
import sys
import tempfile
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from urllib.request import urlopen

from decoder import decode, parse_pairs
from encoder import BACK_PATTERNS, load_words


HOLD_SECONDS = 3.0
MOTION_TOLERANCE = 0.035  # Fraction of the camera frame, measured from hold start.
RELEASE_SECONDS = 0.4

# Valarian-inspired Bright Architectural Monochrome Palette
BG_BASE = "#F4F6F9"       # Crisp cool alabaster window background
BG_SURFACE = "#FFFFFF"    # Pure white bento card surface
BG_ELEVATED = "#EEF2F6"   # Soft technical slate for stages & secondary controls
BG_INPUT = "#F8FAFC"      # Bright input & card surface
BG_HOVER = "#E2E8F0"      # Subtle interactive hover state
BORDER_SUBTLE = "#CBD5E1" # Crisp 1px structural hairline border
BORDER_FOCUS = "#0284C7"  # Active focus border
BORDER_STRONG = "#94A3B8" # Strong structural border
TEXT_PRIMARY = "#0F172A"  # Deep stark slate-black
TEXT_SECONDARY = "#334155"
TEXT_MUTED = "#64748B"
ACCENT_PRIMARY = "#0F172A"
ACCENT_TECH = "#0284C7"

SANS_FONT = "Segoe UI" if sys.platform == "win32" else "TkDefaultFont"
MONO_FONT = "Consolas" if sys.platform == "win32" else "TkFixedFont"


def configure_valarian_theme(root: tk.Tk) -> None:
    """Apply the bright Valarian architectural monochrome theme to ttk widgets."""
    root.configure(background=BG_BASE)

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")

    style.configure(".", background=BG_BASE, foreground=TEXT_PRIMARY, font=(SANS_FONT, 10))
    style.configure("TFrame", background=BG_BASE)
    style.configure("Surface.TFrame", background=BG_SURFACE)
    style.configure("Card.TFrame", background=BG_SURFACE)
    style.configure("Viewport.TFrame", background=BG_ELEVATED)

    style.configure("TLabel", background=BG_BASE, foreground=TEXT_PRIMARY, font=(SANS_FONT, 10))
    style.configure(
        "Eyebrow.TLabel",
        background=BG_BASE,
        foreground=ACCENT_TECH,
        font=(MONO_FONT, 8, "bold"),
    )
    style.configure(
        "Title.TLabel",
        background=BG_BASE,
        foreground=TEXT_PRIMARY,
        font=(SANS_FONT, 20, "bold"),
    )
    style.configure(
        "Subtitle.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=(SANS_FONT, 10),
    )
    style.configure(
        "Muted.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_MUTED,
        font=(MONO_FONT, 9),
    )
    style.configure(
        "Viewport.TLabel",
        background=BG_ELEVATED,
        foreground=TEXT_SECONDARY,
        font=(MONO_FONT, 10),
    )
    style.configure(
        "LiveTelemetry.TLabel",
        background=BG_SURFACE,
        foreground=ACCENT_TECH,
        font=(MONO_FONT, 11, "bold"),
        padding=(12, 6),
    )
    style.configure(
        "Status.TLabel",
        background=BG_BASE,
        foreground=TEXT_SECONDARY,
        font=(MONO_FONT, 9),
    )
    style.configure(
        "Slot.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=(MONO_FONT, 10),
    )
    style.configure(
        "DockTitle.TLabel",
        background=BG_SURFACE,
        foreground=ACCENT_TECH,
        font=(MONO_FONT, 8, "bold"),
    )

    # High-contrast stark obsidian primary button
    style.configure(
        "Primary.TButton",
        background=ACCENT_PRIMARY,
        foreground="#FFFFFF",
        bordercolor=ACCENT_PRIMARY,
        lightcolor=ACCENT_PRIMARY,
        darkcolor=ACCENT_PRIMARY,
        borderwidth=1,
        relief="flat",
        focusthickness=0,
        font=(MONO_FONT, 9, "bold"),
        padding=(16, 8),
    )
    style.map(
        "Primary.TButton",
        background=[("active", "#1E293B"), ("pressed", "#334155"), ("disabled", BG_ELEVATED)],
        foreground=[("disabled", TEXT_MUTED)],
        bordercolor=[("active", "#1E293B"), ("disabled", BORDER_SUBTLE)],
    )

    # Hairline secondary button
    style.configure(
        "TButton",
        background=BG_ELEVATED,
        foreground=TEXT_PRIMARY,
        bordercolor=BORDER_SUBTLE,
        lightcolor=BORDER_SUBTLE,
        darkcolor=BORDER_SUBTLE,
        borderwidth=1,
        relief="flat",
        focusthickness=0,
        font=(MONO_FONT, 9),
        padding=(12, 7),
    )
    style.map(
        "TButton",
        background=[("active", BG_HOVER), ("pressed", BORDER_SUBTLE), ("disabled", BG_INPUT)],
        foreground=[("disabled", TEXT_MUTED)],
        bordercolor=[("active", BORDER_STRONG), ("disabled", BORDER_SUBTLE)],
    )

    # Radiobuttons & Checkbuttons on bright surface
    style.configure(
        "TRadiobutton",
        background=BG_SURFACE,
        foreground=TEXT_PRIMARY,
        indicatorbackground=BG_INPUT,
        indicatorforeground=ACCENT_TECH,
        upperbordercolor=BORDER_STRONG,
        lowerbordercolor=BORDER_STRONG,
        focusthickness=0,
        font=(MONO_FONT, 9, "bold"),
        padding=(4, 2),
    )
    style.map(
        "TRadiobutton",
        background=[("active", BG_SURFACE)],
        foreground=[("selected", ACCENT_TECH), ("active", TEXT_PRIMARY)],
        indicatorbackground=[("selected", ACCENT_TECH), ("active", BG_HOVER)],
    )

    style.configure(
        "TCheckbutton",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        indicatorbackground=BG_INPUT,
        indicatorforeground=ACCENT_TECH,
        upperbordercolor=BORDER_STRONG,
        lowerbordercolor=BORDER_STRONG,
        focusthickness=0,
        font=(SANS_FONT, 9),
        padding=(4, 2),
    )
    style.map(
        "TCheckbutton",
        background=[("active", BG_SURFACE)],
        foreground=[("disabled", TEXT_MUTED), ("selected", TEXT_PRIMARY), ("active", TEXT_PRIMARY)],
        indicatorbackground=[("selected", ACCENT_TECH), ("disabled", BG_ELEVATED)],
    )

    # Clean architectural progressbar
    style.configure(
        "Horizontal.TProgressbar",
        troughcolor=BG_ELEVATED,
        background=ACCENT_TECH,
        bordercolor=BORDER_SUBTLE,
        lightcolor=ACCENT_TECH,
        darkcolor=ACCENT_TECH,
        thickness=7,
    )

    # Readout entry in bottom dock
    style.configure(
        "TEntry",
        fieldbackground=BG_INPUT,
        background=BG_INPUT,
        foreground=TEXT_PRIMARY,
        insertcolor=TEXT_PRIMARY,
        bordercolor=BORDER_SUBTLE,
        lightcolor=BORDER_SUBTLE,
        darkcolor=BORDER_SUBTLE,
        borderwidth=1,
        relief="flat",
        padding=(12, 8),
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", BG_INPUT)],
        foreground=[("readonly", TEXT_PRIMARY)],
        bordercolor=[("focus", BORDER_FOCUS)],
    )

    # Minimal clean scrollbar
    style.configure(
        "Vertical.TScrollbar",
        background=BORDER_SUBTLE,
        troughcolor=BG_BASE,
        bordercolor=BG_BASE,
        arrowcolor=TEXT_SECONDARY,
        relief="flat",
    )
    style.map(
        "Vertical.TScrollbar",
        background=[("active", BORDER_STRONG)],
    )


def pair_problem(pair: str | None) -> str | None:
    """Explain why an observed pair cannot be recorded yet."""
    if pair is None:
        return "Show both hands with palms or backs clearly facing the camera."
    for hand in pair.split(" | "):
        side, view, _direction, bits = hand.split()
        if view == "B" and bits not in BACK_PATTERNS:
            return f"{side}: this back-of-hand finger pattern is excluded by the encoder."
    return None


class PairRecorder:
    """Timed capture state, independent of the camera and GUI for testing."""

    def __init__(self) -> None:
        self.pairs: list[str] = []
        self.active = False
        self.last_pair: str | None = None
        self.missing_since: float | None = None
        self._clear_hold()

    def _clear_hold(self) -> None:
        self.candidate: str | None = None
        self.anchor: tuple[tuple[float, float], ...] = ()
        self.since: float | None = None

    def start(self) -> None:
        self.pairs.clear()
        self.last_pair = None
        self.missing_since = None
        self.active = True
        self._clear_hold()

    def undo(self) -> None:
        if self.pairs:
            self.last_pair = self.pairs.pop()
            self.missing_since = None
            self.active = True
            self._clear_hold()

    def update(
        self,
        pair: str | None,
        points: tuple[tuple[float, float], ...],
        now: float,
        *,
        both_visible: bool,
    ) -> tuple[float, bool, str]:
        """Return hold progress, whether a pair was captured, and instructions."""
        if not self.active:
            return 0.0, False, "Press Start recording to capture a set of three pairs."
        # A brief disappearance must not let tracking flicker record duplicates.
        if not both_visible:
            if self.missing_since is None:
                self.missing_since = now
            if now - self.missing_since >= RELEASE_SECONDS:
                self.last_pair = None
        else:
            self.missing_since = None
        problem = pair_problem(pair)
        if problem:
            self._clear_hold()
            return 0.0, False, problem
        if pair == self.last_pair:
            self._clear_hold()
            return 0.0, False, "Pair saved. Change pose, or lower your hands briefly to repeat it."
        moved = len(points) != len(self.anchor) or any(
            (x - ax) ** 2 + (y - ay) ** 2 > MOTION_TOLERANCE**2
            for (x, y), (ax, ay) in zip(points, self.anchor)
        )
        if pair != self.candidate or moved or self.since is None:
            self.candidate, self.anchor, self.since = pair, points, now
        elapsed = now - self.since
        if elapsed < HOLD_SECONDS:
            return elapsed / HOLD_SECONDS, False, f"Hold steady… {HOLD_SECONDS - elapsed:.1f}s"
        self.pairs.append(pair)
        self.last_pair = pair
        self._clear_hold()
        if len(self.pairs) == 3:
            self.active = False
        return 1.0, True, f"Pair {len(self.pairs)} recorded."


class DecoderGUI:
    def __init__(
        self,
        root: tk.Tk,
        vocabulary: list[str],
        camera_index: int,
        swap_hands: bool,
        model: Path,
    ) -> None:
        import cv2
        import mediapipe as mp
        from camera_pair import describe

        self.cv2, self.mp, self.describe = cv2, mp, describe
        self.root, self.vocabulary, self.swap_hands = root, vocabulary, swap_hands
        self.camera_index, self.model = camera_index, model
        self.recorder = PairRecorder()
        self.history = {side: deque(maxlen=5) for side in "LR"}
        self.camera = self.detector = self.image_detector = None
        self.after_id = self.photo = self.preview_image = None
        self.closed = False
        self.last_timestamp = -1
        self.image_pairs = [None] * 3
        self.image_frames = [None] * 3
        self.image_paths = [None] * 3
        self.capture_frames = []
        self.save_errors = {}
        self.session_folder = None
        self.saving_enabled = False
        self.output_directory = Path(__file__).with_name("captures")

        root.title("VALARIAN // Optical Hand Signal Decoder")
        root.geometry(f"1060x{min(880, root.winfo_screenheight() - 100)}")
        root.minsize(760, 520)
        configure_valarian_theme(root)

        # Pinned bottom result dock with hairline top border
        results_border = tk.Frame(root, bg=BORDER_SUBTLE, padx=1, pady=1)
        results_border.pack(side="bottom", fill="x", padx=22, pady=(6, 18))
        results = ttk.Frame(results_border, style="Surface.TFrame", padding=(16, 12))
        results.pack(fill="x")
        ttk.Label(
            results,
            text="DECODED OUTPUT // 3-WORD PHRASE",
            style="DockTitle.TLabel",
        ).pack(anchor="w")
        self.words = tk.StringVar()
        self.words_entry = ttk.Entry(
            results,
            textvariable=self.words,
            state="readonly",
            font=(MONO_FONT, 18, "bold"),
        )
        self.words_entry.pack(fill="x", pady=(6, 0))

        # Scrollable main workspace
        scroll_host = ttk.Frame(root)
        scroll_host.pack(fill="both", expand=True)
        self.scroll_canvas = tk.Canvas(
            scroll_host,
            highlightthickness=0,
            bd=0,
            background=BG_BASE,
            yscrollincrement=18,
        )
        scrollbar = ttk.Scrollbar(
            scroll_host, orient="vertical", command=self.scroll_canvas.yview
        )
        scrollbar.pack(side="right", fill="y")
        self.scroll_canvas.configure(yscrollcommand=scrollbar.set)
        self.scroll_canvas.pack(side="left", fill="both", expand=True)
        outer = self.scroll_body = ttk.Frame(self.scroll_canvas, padding=(22, 18, 22, 10))
        self.scroll_window = self.scroll_canvas.create_window(
            (0, 0), window=outer, anchor="nw"
        )
        self.scroll_canvas.bind("<Configure>", self.update_scroll_area)
        outer.bind("<Configure>", self.update_scroll_area)
        self.window_system = root.tk.call("tk", "windowingsystem")
        for event in ("<MouseWheel>", "<Button-4>", "<Button-5>"):
            root.bind(event, self.scroll_wheel, add="+")

        # Header Block
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(
            header,
            text="OPTICAL TELEMETRY & POSE RECOGNITION // MEDIAPIPE",
            style="Eyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Decode three hand pairs",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        # Mode & Capture Configuration Bento Card
        config_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
        config_border.pack(fill="x", pady=(0, 12))
        self.config_card = ttk.Frame(config_border, style="Surface.TFrame", padding=(16, 12))
        self.config_card.pack(fill="x")

        modes = ttk.Frame(self.config_card, style="Surface.TFrame")
        modes.pack(fill="x", pady=(0, 6))
        self.mode = tk.StringVar(value="live")
        self.current_mode = "live"
        for text, value in (("LIVE CAMERA", "live"), ("UPLOAD PHOTOS", "photos")):
            ttk.Radiobutton(
                modes,
                text=text,
                value=value,
                variable=self.mode,
                command=self.select_mode,
            ).pack(side="left", padx=(0, 20))

        self.hint = ttk.Label(
            self.config_card,
            text="Hold both hands still for 3 seconds per pair. Words appear after pair 3.",
            style="Subtitle.TLabel",
        )
        self.hint.pack(anchor="w", pady=(0, 8))

        divider = tk.Frame(self.config_card, bg=BORDER_SUBTLE, height=1)
        divider.pack(fill="x", pady=(0, 8))

        self.settings = ttk.Frame(self.config_card, style="Surface.TFrame")
        self.settings.pack(fill="x")
        self.save_images = tk.BooleanVar(value=False)
        self.save_check = ttk.Checkbutton(
            self.settings,
            text="Save a photo for each live capture",
            variable=self.save_images,
        )
        self.save_check.pack(side="left")
        self.folder_button = ttk.Button(
            self.settings, text="Save folder…", command=self.choose_folder
        )
        self.folder_button.pack(side="left", padx=10)
        self.photos_are_mirrored = tk.BooleanVar(value=True)
        self.mirror_check = ttk.Checkbutton(
            self.settings,
            text="Photos already use selfie view (including saved captures)",
            variable=self.photos_are_mirrored,
            command=self.photo_orientation_changed,
        )
        self.destination = ttk.Label(
            self.config_card,
            text=f"Save to: {self.output_directory}",
            style="Muted.TLabel",
            wraplength=760,
        )
        self.destination.pack(anchor="w", pady=(6, 0))

        # Camera / Photo Optical Viewport Card
        self.preview_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
        self.preview_border.pack(fill="both", expand=True)
        self.preview_frame = ttk.Frame(
            self.preview_border, style="Viewport.TFrame", height=380
        )
        self.preview_frame.pack(fill="both", expand=True)
        self.preview = ttk.Label(
            self.preview_frame,
            text="OPTICAL FEED STANDBY // START RECORDING OR UPLOAD PHOTOS",
            style="Viewport.TLabel",
            anchor="center",
        )
        self.preview.place(relx=0.5, rely=0.5, anchor="center")
        self.preview_frame.bind("<Configure>", self.resize_preview)

        # Live Telemetry Readout Bar
        telemetry_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
        telemetry_border.pack(fill="x", pady=(8, 6))
        self.live = ttk.Label(
            telemetry_border,
            text="Camera opens when you start recording.",
            style="LiveTelemetry.TLabel",
            anchor="center",
        )
        self.live.pack(fill="x")

        self.status = ttk.Label(
            outer,
            text="Press Start recording when ready.",
            style="Status.TLabel",
            wraplength=760,
        )
        self.status.pack(anchor="w", pady=(2, 4))
        self.progress = ttk.Progressbar(outer, maximum=HOLD_SECONDS)
        self.progress.pack(fill="x", pady=(0, 10))

        # Sequence Slot Bento Rows
        self.slots, self.upload_buttons, self.view_buttons = [], [], []
        for index in range(3):
            row_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
            row_border.pack(fill="x", pady=3)
            row = ttk.Frame(row_border, style="Card.TFrame", padding=(12, 8))
            row.pack(fill="x")
            slot = ttk.Label(
                row,
                text=f"Pair {index + 1}: waiting",
                style="Slot.TLabel",
            )
            slot.pack(side="left", fill="x", expand=True)
            self.slots.append(slot)
            upload = ttk.Button(
                row,
                text="Upload photo…",
                command=lambda i=index: self.upload_photo(i),
            )
            view = ttk.Button(
                row, text="View", command=lambda i=index: self.view_photo(i)
            )
            self.upload_buttons.append(upload)
            self.view_buttons.append(view)

        # Action Bar
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(12, 6))
        self.start_button = ttk.Button(
            actions,
            text="Start recording",
            style="Primary.TButton",
            command=self.start,
        )
        self.start_button.pack(side="left")
        self.undo_button = ttk.Button(
            actions, text="Redo last pair", command=self.undo, state="disabled"
        )
        self.undo_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Copy pairs", command=self.copy_pairs).pack(
            side="left"
        )
        ttk.Button(actions, text="Quit", command=self.close).pack(side="right")

        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda _event: self.close())

    def update_scroll_area(self, _event=None) -> None:
        width = self.scroll_canvas.winfo_width()
        height = max(self.scroll_body.winfo_reqheight(), self.scroll_canvas.winfo_height())
        self.scroll_canvas.itemconfigure(self.scroll_window, width=width, height=height)
        self.scroll_canvas.configure(scrollregion=(0, 0, width, height))

    def scroll_wheel(self, event) -> str:
        if event.num == 4:
            units = -1
        elif event.num == 5:
            units = 1
        elif self.window_system == "aqua":
            units = -int(event.delta)
        else:
            units = -int(event.delta / 120) or (-1 if event.delta > 0 else 1)
        self.scroll_canvas.yview_scroll(units, "units")
        return "break"

    def create_detector(self, running_mode):
        options = self.mp.tasks.vision.HandLandmarkerOptions(
            base_options=self.mp.tasks.BaseOptions(model_asset_path=str(self.model)),
            running_mode=running_mode,
            num_hands=2,
        )
        return self.mp.tasks.vision.HandLandmarker.create_from_options(options)

    def choose_folder(self) -> None:
        folder = filedialog.askdirectory(
            title="Choose where to save captured photos", parent=self.root
        )
        if folder:
            self.output_directory = Path(folder)
            self.destination.config(text=f"Save to: {self.output_directory}")

    def reset_set(self) -> None:
        self.recorder = PairRecorder()
        self.image_pairs = [None] * 3
        self.image_frames = [None] * 3
        self.image_paths = [None] * 3
        self.capture_frames = []
        self.save_errors = {}
        self.session_folder = None
        self.words.set("")
        self.progress["value"] = 0
        self.destination.config(text=f"Save to: {self.output_directory}")
        for samples in self.history.values():
            samples.clear()
        self.refresh_slots()

    def select_mode(self) -> None:
        if self.mode.get() != self.current_mode:
            self.change_mode()

    def change_mode(self) -> None:
        self.current_mode = self.mode.get()
        self.stop_live()
        self.reset_set()
        self.photo = self.preview_image = None
        photos = self.mode.get() == "photos"
        self.preview.config(
            image="",
            text=(
                "Upload one photo of both hands for each pair."
                if photos
                else "Press Start recording to open the camera."
            ),
        )
        self.live.config(
            text="No photo selected."
            if photos
            else "Camera opens when you start recording."
        )
        self.hint.config(
            text=(
                "Upload pairs 1, 2 and 3. Each photo must contain both hands."
                if photos
                else "Hold both hands still for 3 seconds per pair. Words appear after pair 3."
            )
        )
        self.start_button.config(
            text="Clear photos" if photos else "Start recording", state="normal"
        )
        self.status.config(
            text=(
                "Choose a photo for each pair, in sequence."
                if photos
                else "Press Start recording when ready."
            )
        )
        if photos:
            self.save_check.pack_forget()
            self.folder_button.pack_forget()
            self.mirror_check.pack(side="left")
            self.destination.pack_forget()
        else:
            self.mirror_check.pack_forget()
            self.save_check.pack(side="left")
            self.folder_button.pack(side="left", padx=10)
            self.destination.pack(anchor="w", pady=(6, 0))

    def start(self) -> None:
        if self.mode.get() == "photos":
            self.change_mode()
            return
        # Restarting a set leaves earlier saved sets in their own folders.
        self.stop_live()
        self.reset_set()
        try:
            self.camera = self.cv2.VideoCapture(self.camera_index)
            if not self.camera.isOpened():
                raise RuntimeError(
                    "Cannot open camera. Allow camera access or try --camera 1. You can also use Upload photos."
                )
            self.detector = self.create_detector(self.mp.tasks.vision.RunningMode.VIDEO)
        except Exception as error:
            self.stop_live()
            self.status.config(text=str(error))
            return
        self.recorder.start()
        self.saving_enabled = self.save_images.get()
        self.save_check.config(state="disabled")
        self.folder_button.config(state="disabled")
        self.start_button.config(text="Restart set")
        self.after_id = self.root.after(0, self.tick)

    def undo(self) -> None:
        if self.mode.get() != "live" or not self.recorder.pairs:
            return
        if self.session_folder is not None:
            # Remove only the generated snapshot for the pair being replaced.
            path = self.session_folder / f"pair_{len(self.recorder.pairs)}.png"
            try:
                path.unlink(missing_ok=True)
            except OSError as error:
                self.status.config(text=f"Could not remove the old capture: {error}")
                return
        self.recorder.undo()
        self.save_errors.pop(len(self.recorder.pairs), None)
        if self.capture_frames:
            self.capture_frames.pop()
        self.words.set("")
        self.progress["value"] = 0
        self.save_check.config(state="disabled")
        self.folder_button.config(state="disabled")
        self.refresh_slots()

    def refresh_slots(self) -> None:
        photos = self.mode.get() == "photos"
        for index, slot in enumerate(self.slots):
            pair = (
                self.image_pairs[index]
                if photos
                else (
                    self.recorder.pairs[index]
                    if index < len(self.recorder.pairs)
                    else None
                )
            )
            slot.config(
                text=f"Pair {index + 1}: {pair or 'waiting'}",
                foreground=ACCENT_TECH if pair else TEXT_MUTED,
            )
            if photos:
                self.view_buttons[index].pack(side="right", padx=(6, 0))
                self.view_buttons[index].config(state="normal" if pair else "disabled")
                self.upload_buttons[index].pack(side="right")
                self.upload_buttons[index].config(
                    text="Replace photo…" if pair else "Upload photo…"
                )
            else:
                self.upload_buttons[index].pack_forget()
                self.view_buttons[index].pack_forget()
        self.undo_button.config(
            state="normal" if not photos and self.recorder.pairs else "disabled"
        )

    def pair_text(self) -> str:
        pairs = self.image_pairs if self.mode.get() == "photos" else self.recorder.pairs
        return "\n".join(
            f"Pair {i}: {pair}" for i, pair in enumerate(pairs, 1) if pair is not None
        )

    def copy_pairs(self) -> None:
        if self.pair_text():
            self.root.clipboard_clear()
            self.root.clipboard_append(self.pair_text())

    def decode_set(self) -> str:
        try:
            _, _, words = decode(parse_pairs(self.pair_text()), self.vocabulary)
            self.words.set(" ".join(words))
            return (
                "Decoded! Replace a photo or clear the set."
                if self.mode.get() == "photos"
                else "Decoded! Start a new set, or redo the last pair."
            )
        except ValueError as error:
            self.words.set("")
            return f"Could not decode: {error} Check the pairs or restart the set."

    def upload_photo(self, index: int) -> None:
        path = filedialog.askopenfilename(
            title=f"Choose photo for pair {index + 1}",
            parent=self.root,
            filetypes=[
                ("Hand photos", "*.png *.jpg *.jpeg *.webp *.bmp"),
                ("All files", "*"),
            ],
        )
        if path:
            self.load_photo(index, Path(path))

    def load_photo(self, index: int, path: Path) -> None:
        try:
            frame = self.cv2.imread(str(path))
            if frame is None:
                raise ValueError(
                    "Cannot read this image. Choose a PNG, JPEG, WebP, or BMP photo."
                )
            if not self.photos_are_mirrored.get():
                frame = self.cv2.flip(frame, 1)
            height, width = frame.shape[:2]
            if max(height, width) > 1600:
                scale = 1600 / max(height, width)
                frame = self.cv2.resize(
                    frame, (round(width * scale), round(height * scale))
                )
            display_pair, pair, _, _ = self.observe(frame, still=True)
            self.live.config(text=display_pair)
            self.show_preview(frame)
            problem = pair_problem(pair)
            if problem:
                raise ValueError(problem)
        except Exception as error:
            # A failed replacement leaves the previous valid photo and pair intact.
            self.status.config(text=f"Pair {index + 1} not loaded: {error}")
            return
        self.image_pairs[index] = pair
        self.image_frames[index] = frame
        self.image_paths[index] = path
        self.words.set("")
        self.refresh_slots()
        count = sum(pair is not None for pair in self.image_pairs)
        self.progress["value"] = count
        status = (
            self.decode_set()
            if count == 3
            else f"Pair {index + 1} loaded from {path.name}. {count}/3 photos ready."
        )
        self.status.config(text=status)

    def view_photo(self, index: int) -> None:
        if self.image_frames[index] is not None:
            self.show_preview(self.image_frames[index])
            self.live.config(text=self.image_pairs[index])

    def photo_orientation_changed(self) -> None:
        # Re-read the originals so the same transform is never applied twice.
        paths = list(self.image_paths)
        self.reset_set()
        for index, path in enumerate(paths):
            if path is not None:
                self.load_photo(index, path)

    def observe(self, frame, *, still=False):
        """Recognize photos independently; smooth only consecutive video frames."""
        cv2, mp = self.cv2, self.mp
        height, width = frame.shape[:2]
        image = mp.Image(
            image_format=mp.ImageFormat.SRGB,
            data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB),
        )
        if still:
            if self.image_detector is None:
                self.image_detector = self.create_detector(
                    mp.tasks.vision.RunningMode.IMAGE
                )
            result = self.image_detector.detect(image)
        else:
            self.last_timestamp = max(
                self.last_timestamp + 1, time.monotonic_ns() // 1_000_000
            )
            result = self.detector.detect_for_video(image, self.last_timestamp)
        hands = {}
        for labels, landmarks in zip(result.handedness, result.hand_landmarks):
            side = {"Left": "R", "Right": "L"}[labels[0].category_name]
            if self.swap_hands:
                side = "R" if side == "L" else "L"
            if side not in hands or labels[0].score > hands[side][0]:
                hands[side] = (labels[0].score, landmarks)
        descriptions, points = {}, []
        for side in "LR":
            if side not in hands:
                if not still:
                    self.history[side].clear()
                descriptions[side] = f"{side} -- -- -----"
                continue
            landmarks = hands[side][1]
            fields = self.describe(side, landmarks, width, height).split()
            samples = [fields] if still else self.history[side]
            if not still:
                samples.append(fields)
            bits = "".join(
                str(int(sum(int(s[3][i]) for s in samples) > len(samples) / 2))
                for i in range(5)
            )
            view = fields[1]
            if view != "?":
                votes = [s[1] for s in samples if s[1] != "?"]
                if votes.count("F") != votes.count("B"):
                    view = "F" if votes.count("F") > votes.count("B") else "B"
            descriptions[side] = f"{side} {view} {fields[2]} {bits}"
            points.extend((p.x, p.y) for p in landmarks)
            for p in landmarks:
                cv2.circle(
                    frame, (int(p.x * width), int(p.y * height)), 3, (0, 255, 0), -1
                )
        pair = " | ".join(descriptions[side] for side in "LR")
        valid = len(hands) == 2 and all(
            "?" not in text for text in descriptions.values()
        )
        return pair, pair if valid else None, tuple(points), len(hands) == 2

    def save_capture(self, frame, index: int) -> str:
        if self.session_folder is None:
            self.output_directory.mkdir(parents=True, exist_ok=True)
            self.session_folder = Path(
                tempfile.mkdtemp(prefix="set-", dir=self.output_directory)
            )
        path = self.session_folder / f"pair_{index + 1}.png"
        if not self.cv2.imwrite(str(path), frame):
            raise OSError(f"Could not save {path}")
        return str(path)

    def show_preview(self, frame) -> None:
        self.preview_image = frame
        self.resize_preview()

    def resize_preview(self, _event=None) -> None:
        if self.preview_image is None:
            return
        frame = self.preview_image
        height, width = frame.shape[:2]
        scale = min(
            max(1, self.preview_frame.winfo_width()) / width,
            max(1, self.preview_frame.winfo_height()) / height,
        )
        preview = self.cv2.resize(
            frame, (max(1, round(width * scale)), max(1, round(height * scale)))
        )
        encoded, png = self.cv2.imencode(".png", preview)
        if not encoded:
            raise RuntimeError("Could not render the camera preview.")
        self.photo = tk.PhotoImage(data=png.tobytes())
        self.preview.config(image=self.photo, text="")

    def tick(self) -> None:
        self.after_id = None
        if self.closed or self.mode.get() != "live" or self.camera is None:
            return
        try:
            ok, frame = self.camera.read()
            if not ok:
                raise RuntimeError(
                    "Could not read a camera frame. Check the camera and restart, or use Upload photos."
                )
            frame = self.cv2.flip(frame, 1)
            clean_frame = frame.copy()
            display_pair, pair, points, visible = self.observe(frame)
            self.live.config(text=display_pair)
            progress, captured, status = self.recorder.update(
                pair, points, time.monotonic(), both_visible=visible
            )
            if captured:
                self.capture_frames.append(clean_frame)
                save_error = None
                if self.saving_enabled:
                    try:
                        self.save_capture(
                            clean_frame, len(self.recorder.pairs) - 1
                        )
                        self.save_errors.pop(len(self.recorder.pairs) - 1, None)
                    except OSError as error:
                        save_error = str(error)
                        self.save_errors[len(self.recorder.pairs) - 1] = save_error
                    if self.save_errors:
                        missing = ", ".join(
                            str(index + 1) for index in sorted(self.save_errors)
                        )
                        self.destination.config(
                            text=f"Photo save failed for pair(s) {missing}: {next(iter(self.save_errors.values()))}"
                        )
                    else:
                        self.destination.config(
                            text=f"Saved captures: {self.session_folder}"
                        )
                self.refresh_slots()
                self.root.bell()
                if len(self.recorder.pairs) == 3:
                    status = self.decode_set()
                    self.start_button.config(text="Record new set")
                    self.save_check.config(state="normal")
                    self.folder_button.config(state="normal")
                if save_error:
                    status += f" Photo was not saved: {save_error}"
                elif len(self.recorder.pairs) == 3 and self.save_errors:
                    status += " Some capture photos could not be saved; see the save status above."
            if self.recorder.active or captured or not self.recorder.pairs:
                self.status.config(text=status)
                self.progress["value"] = progress * HOLD_SECONDS
            self.show_preview(frame)
        except Exception as error:
            self.status.config(text=f"Camera error: {error}")
            self.recorder.active = False
            self.undo_button.config(state="disabled")
            self.stop_live()
            return
        self.after_id = self.root.after(15, self.tick)

    def stop_live(self) -> None:
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
            self.after_id = None
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        if self.detector is not None:
            self.detector.close()
            self.detector = None
        self.last_timestamp = -1
        self.save_check.config(state="normal")
        self.folder_button.config(state="normal")

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stop_live()
        if self.image_detector is not None:
            self.image_detector.close()
            self.image_detector = None
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument(
        "--swap-hands",
        action="store_true",
        help="reverse L/R if the camera already mirrors its output",
    )
    parser.add_argument(
        "--word-list",
        type=Path,
        default=Path(__file__).with_name("durhack_word_list.csv"),
        help="same CSV, in the same order, used for encoding",
    )
    args = parser.parse_args()
    try:
        vocabulary = load_words(args.word_list)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    root = tk.Tk()
    root.withdraw()
    try:
        from camera_pair import MODEL_URL

        model = Path(__file__).with_name("hand_landmarker.task")
        if not model.exists():
            print("Downloading hand model (first run only)…")
            with urlopen(MODEL_URL, timeout=60) as response:
                model.write_bytes(response.read())
        app = DecoderGUI(root, vocabulary, args.camera, args.swap_hands, model)
    except Exception as error:
        messagebox.showerror("Cannot start decoder", str(error), parent=root)
        root.destroy()
        return
    root.deiconify()
    try:
        root.mainloop()
    finally:
        app.close()


if __name__ == "__main__":
    main()
