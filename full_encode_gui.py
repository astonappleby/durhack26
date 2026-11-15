#!/usr/bin/env python3
"""Choose three words and preview their encoded hand poses in a desktop GUI."""
from __future__ import annotations

import argparse
import csv
from functools import lru_cache
from pathlib import Path
import sys
import tkinter as tk
from tkinter import messagebox, ttk
import xml.etree.ElementTree as ET

from encoder import HAND_RADIX, encode, load_words
from make_hand import ASSETS, ROTATIONS, raised_fingers


# Valarian-inspired Bright Architectural Monochrome Palette
BG_BASE = "#F4F6F9"       # Crisp cool alabaster window background
BG_SURFACE = "#FFFFFF"    # Pure white bento card surface
BG_ELEVATED = "#EEF2F6"   # Soft technical slate for stages & secondary controls
BG_INPUT = "#F8FAFC"      # Bright input & card surface
BG_HOVER = "#E2E8F0"      # Subtle interactive hover state
BORDER_SUBTLE = "#CBD5E1" # Crisp 1px structural hairline border
BORDER_FOCUS = "#0284C7"  # Active focus border
BORDER_STRONG = "#94A3B8" # Corner reticle & strong structural border
TEXT_PRIMARY = "#0F172A"  # Deep stark slate-black
TEXT_SECONDARY = "#334155"
TEXT_MUTED = "#64748B"
ACCENT_PRIMARY = "#0F172A"
ACCENT_TECH = "#0284C7"

HAND_COLOR_MAP = {
    "#000000": "#0F172A",  # Crisp deep-slate outline & finger creases
    "#ffffff": "#FFFFFF",  # Pure white light palm fill
    "#69778b": "#64748B",  # Tactical steel-slate back-of-hand fill
}

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
    style.configure("Card.TFrame", background=BG_INPUT)

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
        background=BG_BASE,
        foreground=TEXT_SECONDARY,
        font=(SANS_FONT, 10),
    )
    style.configure(
        "Badge.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=(MONO_FONT, 8, "bold"),
        padding=(10, 5),
    )
    style.configure(
        "FieldLabel.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_MUTED,
        font=(MONO_FONT, 8, "bold"),
    )
    style.configure(
        "Status.TLabel",
        background=BG_SURFACE,
        foreground=TEXT_SECONDARY,
        font=(MONO_FONT, 9),
    )

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
        padding=(10, 7),
    )
    style.map(
        "TEntry",
        fieldbackground=[("readonly", BG_SURFACE), ("focus", BG_SURFACE)],
        foreground=[("readonly", TEXT_PRIMARY)],
        bordercolor=[("focus", BORDER_FOCUS)],
        lightcolor=[("focus", BORDER_FOCUS)],
        darkcolor=[("focus", BORDER_FOCUS)],
    )

    # High-contrast stark obsidian primary button (Valarian signature CTA)
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

    # Clean hairline secondary button
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
        padding=(14, 8),
    )
    style.map(
        "TButton",
        background=[("active", BG_HOVER), ("pressed", BORDER_SUBTLE), ("disabled", BG_INPUT)],
        foreground=[("disabled", TEXT_MUTED)],
        bordercolor=[("active", BORDER_STRONG), ("disabled", BORDER_SUBTLE)],
    )


class WordPicker(ttk.Frame):
    """Entry with a filtered, keyboard accessible vocabulary dropdown."""

    def __init__(
        self,
        parent: tk.Misc,
        index: int,
        words: list[str],
        on_submit=None,
    ) -> None:
        super().__init__(parent, style="Surface.TFrame")
        self.words = words
        self.on_submit = on_submit
        self.value = tk.StringVar()
        self.columnconfigure(0, weight=1)

        label_row = ttk.Frame(self, style="Surface.TFrame")
        label_row.grid(row=0, column=0, sticky="ew", pady=(0, 4))
        ttk.Label(
            label_row,
            text=f"WORD 0{index}",
            style="FieldLabel.TLabel",
        ).pack(side="left")

        self.entry = ttk.Entry(self, textvariable=self.value, width=22, font=(MONO_FONT, 10))
        self.entry.grid(row=1, column=0, sticky="ew")

        self.listbox = tk.Listbox(
            self,
            height=5,
            exportselection=False,
            background=BG_SURFACE,
            foreground=TEXT_PRIMARY,
            selectbackground=BG_ELEVATED,
            selectforeground=ACCENT_TECH,
            highlightthickness=1,
            highlightbackground=BORDER_SUBTLE,
            highlightcolor=BORDER_FOCUS,
            relief="flat",
            borderwidth=0,
            activestyle="none",
            font=(MONO_FONT, 9),
        )
        self.entry.bind("<KeyRelease>", self._typed)
        self.entry.bind("<Down>", self._focus_list)
        self.entry.bind("<Return>", self._entry_return)
        self.entry.bind("<Escape>", lambda _e: self.listbox.grid_remove())
        self.listbox.bind("<ButtonRelease-1>", self._choose)
        self.listbox.bind("<Double-Button-1>", self._choose)
        self.listbox.bind("<Return>", self._choose)
        self.listbox.bind("<Escape>", self._escape_list)
        self.listbox.bind("<Up>", self._up_in_list)

    def _typed(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        query = self.value.get().strip().lower()
        matches = [word for word in self.words if word.startswith(query)][:30] if query else []
        self.listbox.delete(0, "end")
        for word in matches:
            self.listbox.insert("end", word)
        if matches and not (len(matches) == 1 and matches[0] == query):
            self.listbox.grid(row=2, column=0, sticky="ew", pady=(4, 0))
        else:
            self.listbox.grid_remove()

    def _entry_return(self, _event: tk.Event) -> str:
        query = self.value.get().strip().lower()
        if self.listbox.size() and query not in self.words:
            self.value.set(self.listbox.get(0))
            self.listbox.grid_remove()
        else:
            self.listbox.grid_remove()
            if self.on_submit is not None:
                self.on_submit()
        return "break"

    def _focus_list(self, _event: tk.Event) -> str:
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_clear(0, "end")
            self.listbox.selection_set(0)
            self.listbox.activate(0)
        return "break"

    def _up_in_list(self, _event: tk.Event) -> str | None:
        selected = self.listbox.curselection()
        if not selected or selected[0] == 0:
            self.entry.focus_set()
            return "break"
        return None

    def _escape_list(self, _event: tk.Event) -> str:
        self.listbox.grid_remove()
        self.entry.focus_set()
        return "break"

    def _choose(self, _event: tk.Event) -> str:
        selected = self.listbox.curselection()
        if selected:
            self.value.set(self.listbox.get(selected[0]))
            self.listbox.grid_remove()
            self.entry.focus_set()
            self.entry.icursor("end")
        return "break"


class EncoderGUI:
    def __init__(self, root: tk.Tk, vocabulary: list[str]) -> None:
        self.root = root
        self.vocabulary = vocabulary
        root.title("VALARIAN // Hand Pose Encoder")
        root.geometry("860x900")
        root.minsize(640, 660)
        configure_valarian_theme(root)

        outer = ttk.Frame(root, padding=(24, 20, 24, 20))
        outer.pack(fill="both", expand=True)

        # Header Block
        header = ttk.Frame(outer)
        header.pack(fill="x", pady=(0, 14))
        header_left = ttk.Frame(header)
        header_left.pack(side="left", fill="x", expand=True)
        ttk.Label(
            header_left,
            text="OPTICAL ENCODING SYSTEM // BASE-244",
            style="Eyebrow.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header_left,
            text="Encode three words",
            style="Title.TLabel",
        ).pack(anchor="w", pady=(2, 2))
        ttk.Label(
            header_left,
            text="Type to search the valid word list, then choose a suggestion to synthesize the 6-hand pose sequence.",
            style="Subtitle.TLabel",
        ).pack(anchor="w")

        badge_frame = tk.Frame(header, bg=BORDER_SUBTLE, padx=1, pady=1)
        badge_frame.pack(side="right", anchor="ne")
        ttk.Label(
            badge_frame,
            text=f"VOCAB // {len(vocabulary):,} WORDS",
            style="Badge.TLabel",
        ).pack()

        # Bento Control Panel (1px hairline border)
        control_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
        control_border.pack(fill="x", pady=(0, 14))
        control_panel = ttk.Frame(control_border, style="Surface.TFrame", padding=(16, 14))
        control_panel.pack(fill="x")

        pickers_grid = ttk.Frame(control_panel, style="Surface.TFrame")
        pickers_grid.pack(fill="x")
        self.pickers: list[WordPicker] = []
        for index in range(1, 4):
            pickers_grid.columnconfigure(index - 1, weight=1, uniform="word_col")
            picker = WordPicker(pickers_grid, index, vocabulary, on_submit=self.render)
            pad_left = 0 if index == 1 else 8
            pad_right = 0 if index == 3 else 8
            picker.grid(row=0, column=index - 1, sticky="new", padx=(pad_left, pad_right))
            self.pickers.append(picker)

        divider = tk.Frame(control_panel, bg=BORDER_SUBTLE, height=1)
        divider.pack(fill="x", pady=(14, 12))

        actions = ttk.Frame(control_panel, style="Surface.TFrame")
        actions.pack(fill="x")
        ttk.Button(
            actions,
            text="SHOW ENCODED HANDS",
            style="Primary.TButton",
            command=self.render,
        ).pack(side="left")
        ttk.Button(
            actions,
            text="CHANGE WORDS",
            command=self.edit,
        ).pack(side="left", padx=(8, 0))

        self.status = ttk.Label(
            actions,
            text="STATUS // READY FOR INPUT",
            style="Status.TLabel",
        )
        self.status.pack(side="right", padx=(12, 0))

        # Canvas Viewport framed with 1px structural border
        preview_border = tk.Frame(outer, bg=BORDER_SUBTLE, padx=1, pady=1)
        preview_border.pack(fill="both", expand=True)
        self.preview = tk.Canvas(
            preview_border,
            background=BG_ELEVATED,
            highlightthickness=0,
            bd=0,
        )
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<Configure>", self._resize)
        self.hands: list[str] | None = None
        self.last_code: str | None = None

    def render(self) -> None:
        words = [picker.value.get().strip().lower() for picker in self.pickers]
        try:
            number, code, hands = encode(words, self.vocabulary)
        except ValueError as error:
            messagebox.showerror("Choose three valid words", str(error), parent=self.root)
            return
        self.hands = hands
        self.last_code = code
        for picker in self.pickers:
            picker.listbox.grid_remove()
        self.root.update_idletasks()
        self.status.config(
            text=f"PHRASE: {' · '.join(words).upper()}   //   DENARY: {number:,}   //   BASE-{HAND_RADIX}: [{code}]"
        )
        self._resize()

    def edit(self) -> None:
        self.hands = None
        self.last_code = None
        self.status.config(text="Edit any word above, then show the updated hands.")
        self._resize()
        self.pickers[0].entry.focus_set()

    def _draw_corner_ticks(
        self, x1: float, y1: float, x2: float, y2: float, length: float, color: str
    ) -> None:
        """Draw Valarian-style precision corner reticle ticks on the canvas."""
        for cx, dx in ((x1, length), (x2, -length)):
            for cy, dy in ((y1, length), (y2, -length)):
                self.preview.create_line(cx, cy, cx + dx, cy, fill=color, width=1)
                self.preview.create_line(cx, cy, cx, cy + dy, fill=color, width=1)

    def _draw_empty_state(self, width: int, height: int) -> None:
        """Render a clean architectural telemetry card when no words are encoded yet."""
        cx, cy = width / 2, height / 2
        box_w = min(width - 48, 520)
        box_h = min(height - 48, 220)
        if box_w < 120 or box_h < 80:
            return
        x1, y1 = cx - box_w / 2, cy - box_h / 2
        x2, y2 = cx + box_w / 2, cy + box_h / 2

        self.preview.create_rectangle(
            x1, y1, x2, y2, fill=BG_SURFACE, outline=BORDER_SUBTLE, width=1
        )
        self._draw_corner_ticks(x1, y1, x2, y2, 10, BORDER_STRONG)

        self.preview.create_text(
            cx,
            cy - 26,
            text="AWAITING SEQUENCE INPUT",
            font=(MONO_FONT, 10, "bold"),
            fill=ACCENT_TECH,
        )
        self.preview.create_text(
            cx,
            cy + 2,
            text="Select three vocabulary words above and click SHOW ENCODED HANDS.",
            font=(SANS_FONT, 10),
            fill=TEXT_SECONDARY,
        )
        self.preview.create_text(
            cx,
            cy + 28,
            text="3 PAIRS  ·  6 HAND POSES  ·  244 STATES PER HAND",
            font=(MONO_FONT, 8),
            fill=TEXT_MUTED,
        )

    def _resize(self, _event: tk.Event | None = None) -> None:
        width = self.preview.winfo_width()
        height = self.preview.winfo_height()
        if width < 2:
            return
        self.preview.delete("all")
        if not self.hands:
            self._draw_empty_state(width, height)
            return

        # Fit all three pairs into the available window without clipping.
        scale = max(0.05, min((width - 24) / 640, (height - 24) / 1110))
        left = (width - 640 * scale) / 2
        top = (height - 1110 * scale) / 2
        for i, description in enumerate(self.hands):
            pair, side_index = divmod(i, 2)
            self._draw_hand_card(
                left + side_index * 320 * scale,
                top + pair * 370 * scale,
                scale,
                "R" if side_index else "L",
                description,
                pair_index=pair + 1,
            )

    def _draw_hand_card(
        self,
        x: float,
        y: float,
        scale: float,
        side: str,
        description: str,
        pair_index: int = 1,
    ) -> None:
        """Draw the bundled SVG rectangles with the full_encode transforms."""
        view, direction, bits = description.split()
        x1, y1 = x + 10 * scale, y + 10 * scale
        x2, y2 = x + 310 * scale, y + 360 * scale

        # Outer White Bento Card
        self.preview.create_rectangle(
            x1, y1, x2, y2, fill=BG_SURFACE, outline=BORDER_SUBTLE, width=1
        )
        self._draw_corner_ticks(x1, y1, x2, y2, max(4, 10 * scale), BORDER_STRONG)

        # Inner Hand Viewport Stage
        stage_x1, stage_y1 = x + 26 * scale, y + 58 * scale
        stage_x2, stage_y2 = x + 294 * scale, y + 312 * scale
        self.preview.create_rectangle(
            stage_x1,
            stage_y1,
            stage_x2,
            stage_y2,
            fill=BG_INPUT,
            outline=BORDER_SUBTLE,
            width=1,
        )

        # Header Telemetry
        side_label = "LEFT" if side == "L" else "RIGHT"
        view_label = "PALM" if view == "F" else "BACK"
        header_y = y + 34 * scale
        self.preview.create_text(
            x + 26 * scale,
            header_y,
            text=f"PAIR 0{pair_index} // {side_label}",
            anchor="w",
            font=(MONO_FONT, max(7, round(10 * scale)), "bold"),
            fill=TEXT_MUTED,
        )
        badge_color = ACCENT_TECH if view == "F" else TEXT_PRIMARY
        self.preview.create_text(
            x + 294 * scale,
            header_y,
            text=f"{side} · {view_label} · {direction}",
            anchor="e",
            font=(MONO_FONT, max(8, round(11 * scale)), "bold"),
            fill=badge_color,
        )

        mirror = -1 if (side == "R") != (view == "B") else 1
        turns = ROTATIONS[direction] // 90

        def transform(px: float, py: float) -> tuple[float, float]:
            # SVG source is 24 by 31, displayed at 192 by 248.
            px, py = (px * 8 - 96) * mirror, py * 8 - 124
            for _ in range(turns):
                px, py = -py, px
            return x + (160 + px) * scale, y + (185 + py) * scale

        for rx, ry, rw, rh, fill in pose_rectangles(view, bits):
            ax, ay = transform(rx, ry)
            bx, by = transform(rx + rw, ry + rh)
            mapped_fill = HAND_COLOR_MAP.get(fill.lower(), fill)
            self.preview.create_rectangle(
                min(ax, bx),
                min(ay, by),
                max(ax, bx),
                max(ay, by),
                fill=mapped_fill,
                outline="",
                width=0,
            )

        # Footer Telemetry (Binary + Raised Fingers)
        self.preview.create_text(
            x + 26 * scale,
            y + 336 * scale,
            text=f"[{bits}]",
            anchor="w",
            font=(MONO_FONT, max(7, round(9 * scale)), "bold"),
            fill=ACCENT_TECH,
        )
        self.preview.create_text(
            x + 294 * scale,
            y + 336 * scale,
            text=raised_fingers(bits),
            anchor="e",
            width=210 * scale,
            font=(SANS_FONT, max(7, round(9 * scale))),
            fill=TEXT_SECONDARY,
        )


@lru_cache(maxsize=64)
def pose_rectangles(view: str, bits: str) -> tuple:
    """Read the pixel rectangles from the same SVG assets used by full_encode."""
    pose = ET.parse(ASSETS / f"{view}_{bits}.svg").getroot()
    return tuple(
        (
            float(rect.get("x", "0")),
            float(rect.get("y", "0")),
            float(rect.get("width")),
            float(rect.get("height")),
            rect.get("fill", "#000000"),
        )
        for rect in pose
        if rect.tag.rsplit("}", 1)[-1] == "rect"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--word-list",
        type=Path,
        default=Path(__file__).with_name("durhack_word_list.csv"),
        help="CSV word list (default: durhack_word_list.csv beside this script)",
    )
    args = parser.parse_args()
    try:
        vocabulary = load_words(args.word_list)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))
    root = tk.Tk()
    EncoderGUI(root, vocabulary)
    root.mainloop()


if __name__ == "__main__":
    main()
