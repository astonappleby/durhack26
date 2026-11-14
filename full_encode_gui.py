#!/usr/bin/env python3
"""Choose three words and preview their encoded hand poses in a desktop GUI."""
from __future__ import annotations

import argparse
import csv
from functools import lru_cache
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

from encoder import encode, load_words
from make_hand import ASSETS, ROTATIONS, raised_fingers
import xml.etree.ElementTree as ET


class WordPicker(ttk.Frame):
    """Entry with a filtered, keyboard accessible vocabulary dropdown."""

    def __init__(self, parent: tk.Misc, index: int, words: list[str]) -> None:
        super().__init__(parent)
        self.words = words
        self.value = tk.StringVar()
        self.columnconfigure(1, weight=1)
        ttk.Label(self, text=f"Word {index}", width=9).grid(row=0, column=0, sticky="w")
        self.entry = ttk.Entry(self, textvariable=self.value, width=28)
        self.entry.grid(row=0, column=1, sticky="ew")
        self.listbox = tk.Listbox(self, height=5, exportselection=False)
        self.entry.bind("<KeyRelease>", self._typed)
        self.entry.bind("<Down>", self._focus_list)
        self.listbox.bind("<Double-Button-1>", self._choose)
        self.listbox.bind("<Return>", self._choose)

    def _typed(self, event: tk.Event) -> None:
        if event.keysym in ("Up", "Down", "Return", "Escape", "Tab"):
            return
        query = self.value.get().strip().lower()
        matches = [word for word in self.words if word.startswith(query)][:30] if query else []
        self.listbox.delete(0, "end")
        for word in matches:
            self.listbox.insert("end", word)
        if matches:
            self.listbox.grid(row=1, column=1, sticky="ew", pady=(4, 0))
        else:
            self.listbox.grid_remove()

    def _focus_list(self, _event: tk.Event) -> str:
        if self.listbox.size():
            self.listbox.focus_set()
            self.listbox.selection_set(0)
        return "break"

    def _choose(self, _event: tk.Event) -> str:
        selected = self.listbox.curselection()
        if selected:
            self.value.set(self.listbox.get(selected[0]))
            self.listbox.grid_remove()
            self.entry.focus_set()
        return "break"


class EncoderGUI:
    def __init__(self, root: tk.Tk, vocabulary: list[str]) -> None:
        self.root = root
        self.vocabulary = vocabulary
        root.title("Full Encode · Hand Pose Preview")
        root.geometry("760x850")
        root.minsize(560, 600)

        outer = ttk.Frame(root, padding=20)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Encode three words", font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Type to search the valid word list, then choose a suggestion.").pack(anchor="w", pady=(4, 16))

        self.pickers = []
        for index in range(1, 4):
            picker = WordPicker(outer, index, vocabulary)
            picker.pack(fill="x", pady=5)
            self.pickers.append(picker)

        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=(12, 8))
        ttk.Button(actions, text="Show encoded hands", command=self.render).pack(side="left")
        ttk.Button(actions, text="Change words", command=self.edit).pack(side="left", padx=8)
        self.status = ttk.Label(outer, text="")
        self.status.pack(anchor="w", pady=(0, 8))

        self.preview = tk.Canvas(outer, background="#eeeae4", highlightthickness=0)
        self.preview.pack(fill="both", expand=True)
        self.preview.bind("<Configure>", self._resize)
        self.hands: list[str] | None = None

    def render(self) -> None:
        words = [picker.value.get().strip().lower() for picker in self.pickers]
        try:
            number, _code, hands = encode(words, self.vocabulary)
        except ValueError as error:
            messagebox.showerror("Choose three valid words", str(error), parent=self.root)
            return
        self.hands = hands
        for picker in self.pickers:
            picker.listbox.grid_remove()
        self.root.update_idletasks()
        self.status.config(text=f"Words: {' · '.join(words)}     Denary: {number}")
        self._resize()

    def edit(self) -> None:
        self.preview.delete("all")
        self.hands = None
        self.status.config(text="Edit any word above, then show the updated hands.")
        self.pickers[0].entry.focus_set()

    def _resize(self, _event: tk.Event | None = None) -> None:
        if not self.hands or self.preview.winfo_width() < 2:
            return
        self.preview.delete("all")
        width = self.preview.winfo_width()
        # Fit all three pairs into the available window without clipping.
        scale = max(0.05, min((width - 16) / 640,
                             (self.preview.winfo_height() - 16) / 1110))
        left = (width - 640 * scale) / 2
        for i, description in enumerate(self.hands):
            pair, side_index = divmod(i, 2)
            self._draw_hand_card(left + side_index * 320 * scale,
                                 8 + pair * 370 * scale, scale,
                                 "R" if side_index else "L", description)

    def _draw_hand_card(self, x: float, y: float, scale: float,
                        side: str, description: str) -> None:
        """Draw the bundled SVG rectangles with the full_encode transforms."""
        view, direction, bits = description.split()
        self.preview.create_rectangle(x + 10 * scale, y + 10 * scale,
                                      x + 310 * scale, y + 360 * scale,
                                      fill="#faf7f2", outline="#ded9d0")
        title = f'{side} · {"palm" if view == "F" else "back"} · {direction}'
        self.preview.create_text(x + 160 * scale, y + 38 * scale,
                                 text=title, font=("TkDefaultFont", max(8, round(13 * scale))))
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
            self.preview.create_rectangle(min(ax, bx), min(ay, by),
                                          max(ax, bx), max(ay, by),
                                          fill=fill, outline="", width=0)
        self.preview.create_text(x + 160 * scale, y + 340 * scale,
                                 text=raised_fingers(bits), width=290 * scale,
                                 font=("TkDefaultFont", max(7, round(9 * scale))), fill="#666")


@lru_cache(maxsize=64)
def pose_rectangles(view: str, bits: str) -> tuple:
    """Read the pixel rectangles from the same SVG assets used by full_encode."""
    pose = ET.parse(ASSETS / f"{view}_{bits}.svg").getroot()
    return tuple((float(rect.get("x", "0")), float(rect.get("y", "0")),
                  float(rect.get("width")), float(rect.get("height")),
                  rect.get("fill", "#000000"))
                 for rect in pose if rect.tag.rsplit("}", 1)[-1] == "rect")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--word-list", type=Path, default=Path(__file__).with_name("durhack_word_list.csv"),
                        help="CSV word list (default: durhack_word_list.csv beside this script)")
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
