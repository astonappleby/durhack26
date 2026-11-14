#!/usr/bin/env python3
"""Record three webcam hand pairs with three-second holds and decode the words."""
from __future__ import annotations

import argparse
from collections import deque
import csv
from pathlib import Path
import time
import tkinter as tk
from tkinter import messagebox, ttk
from urllib.request import urlopen

from decoder import decode, parse_pairs
from encoder import BACK_PATTERNS, load_words


HOLD_SECONDS = 3.0
MOTION_TOLERANCE = 0.035  # Fraction of the camera frame, measured from hold start.
RELEASE_SECONDS = 0.4


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

    def update(self, pair: str | None, points: tuple[tuple[float, float], ...],
               now: float, *, both_visible: bool) -> tuple[float, bool, str]:
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
        moved = (len(points) != len(self.anchor) or any(
            (x - ax) ** 2 + (y - ay) ** 2 > MOTION_TOLERANCE ** 2
            for (x, y), (ax, ay) in zip(points, self.anchor)
        ))
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
    def __init__(self, root: tk.Tk, vocabulary: list[str], camera_index: int,
                 swap_hands: bool, model: Path) -> None:
        # Keep the timing logic importable without loading camera dependencies.
        import cv2
        import mediapipe as mp
        from camera_pair import describe

        self.cv2, self.mp, self.describe = cv2, mp, describe
        self.root, self.vocabulary, self.swap_hands = root, vocabulary, swap_hands
        self.recorder = PairRecorder()
        self.history = {side: deque(maxlen=5) for side in "LR"}
        self.camera = None
        self.detector = None
        self.after_id = None
        self.photo = None
        self.closed = False
        self.last_timestamp = -1

        root.title("Decode hand signals")
        root.geometry("1000x900")
        root.minsize(740, 760)
        outer = ttk.Frame(root, padding=18)
        outer.pack(fill="both", expand=True)
        ttk.Label(outer, text="Decode three hand pairs", font=("TkDefaultFont", 21, "bold")).pack(anchor="w")
        ttk.Label(outer, text="Hold both hands still for 3 seconds per pair. Words appear after pair 3.").pack(anchor="w", pady=(4, 10))
        self.preview_frame = ttk.Frame(outer, height=440)
        self.preview_frame.pack(fill="both", expand=True)
        self.preview = ttk.Label(self.preview_frame, anchor="center")
        self.preview.place(relx=0.5, rely=0.5, anchor="center")
        self.live = ttk.Label(outer, text="Opening camera…", font=("TkFixedFont", 12))
        self.live.pack(pady=(10, 4))
        self.status = ttk.Label(outer, text="Press Start recording when ready.", wraplength=700)
        self.status.pack(anchor="w", pady=4)
        self.progress = ttk.Progressbar(outer, maximum=HOLD_SECONDS)
        self.progress.pack(fill="x", pady=(0, 10))
        self.slots = []
        for index in range(1, 4):
            slot = ttk.Label(outer, text=f"Pair {index}: waiting", font=("TkFixedFont", 12))
            slot.pack(anchor="w", pady=3)
            self.slots.append(slot)
        actions = ttk.Frame(outer)
        actions.pack(fill="x", pady=12)
        self.start_button = ttk.Button(actions, text="Start recording", command=self.start)
        self.start_button.pack(side="left")
        self.undo_button = ttk.Button(actions, text="Redo last pair", command=self.undo, state="disabled")
        self.undo_button.pack(side="left", padx=8)
        ttk.Button(actions, text="Copy pairs", command=self.copy_pairs).pack(side="left")
        ttk.Button(actions, text="Quit", command=self.close).pack(side="right")
        ttk.Label(outer, text="Decoded words", font=("TkDefaultFont", 12, "bold")).pack(anchor="w")
        self.words = tk.StringVar()
        ttk.Entry(outer, textvariable=self.words, state="readonly",
                  font=("TkDefaultFont", 21)).pack(fill="x", pady=(6, 0))
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.bind("<Escape>", lambda _event: self.close())

        try:
            self.camera = cv2.VideoCapture(camera_index)
            if not self.camera.isOpened():
                raise RuntimeError("Cannot open camera. Allow camera access or try --camera 1.")
            options = mp.tasks.vision.HandLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                num_hands=2,
            )
            self.detector = mp.tasks.vision.HandLandmarker.create_from_options(options)
        except Exception:
            self.release_camera()
            raise
        self.after_id = root.after(0, self.tick)

    def start(self) -> None:
        self.recorder.start()
        self.words.set("")
        self.progress["value"] = 0
        for samples in self.history.values():
            samples.clear()
        self.refresh_slots()
        self.start_button.config(text="Restart set")

    def undo(self) -> None:
        self.recorder.undo()
        self.words.set("")
        self.progress["value"] = 0
        self.refresh_slots()

    def refresh_slots(self) -> None:
        for index, slot in enumerate(self.slots):
            pair = self.recorder.pairs[index] if index < len(self.recorder.pairs) else "waiting"
            slot.config(text=f"Pair {index + 1}: {pair}")
        self.undo_button.config(state="normal" if self.recorder.pairs else "disabled")

    def copy_pairs(self) -> None:
        if self.recorder.pairs:
            self.root.clipboard_clear()
            self.root.clipboard_append(self.pair_text())

    def pair_text(self) -> str:
        return "\n".join(f"Pair {i}: {pair}" for i, pair in enumerate(self.recorder.pairs, 1))

    def observe(self, frame):
        """Use camera_pair's classifications and the same five-frame voting."""
        cv2, mp = self.cv2, self.mp
        height, width = frame.shape[:2]
        image = mp.Image(image_format=mp.ImageFormat.SRGB,
                         data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        self.last_timestamp = max(self.last_timestamp + 1, time.monotonic_ns() // 1_000_000)
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
                self.history[side].clear()
                descriptions[side] = f"{side} -- -- -----"
                continue
            landmarks = hands[side][1]
            fields = self.describe(side, landmarks, width, height).split()
            samples = self.history[side]
            samples.append(fields)
            bits = "".join(str(int(sum(int(s[3][i]) for s in samples) > len(samples) / 2))
                           for i in range(5))
            view = fields[1]
            if view != "?":
                votes = [s[1] for s in samples if s[1] != "?"]
                if votes.count("F") != votes.count("B"):
                    view = "F" if votes.count("F") > votes.count("B") else "B"
            descriptions[side] = f"{side} {view} {fields[2]} {bits}"
            points.extend((p.x, p.y) for p in landmarks)
            for p in landmarks:
                cv2.circle(frame, (int(p.x * width), int(p.y * height)), 3, (0, 255, 0), -1)
        pair = " | ".join(descriptions[side] for side in "LR")
        valid = len(hands) == 2 and all("?" not in text for text in descriptions.values())
        return pair, pair if valid else None, tuple(points), len(hands) == 2

    def tick(self) -> None:
        self.after_id = None
        if self.closed:
            return
        try:
            ok, frame = self.camera.read()
            if not ok:
                raise RuntimeError("Could not read a camera frame. Check the camera and restart the GUI.")
            frame = self.cv2.flip(frame, 1)
            display_pair, pair, points, visible = self.observe(frame)
            self.live.config(text=display_pair)
            progress, captured, status = self.recorder.update(
                pair, points, time.monotonic(), both_visible=visible)
            if captured:
                self.refresh_slots()
                self.root.bell()
                if len(self.recorder.pairs) == 3:
                    try:
                        _, _, words = decode(parse_pairs(self.pair_text()), self.vocabulary)
                        self.words.set(" ".join(words))
                        status = "Decoded! Start a new set, or redo the last pair."
                    except ValueError as error:
                        self.words.set("")
                        status = f"Could not decode: {error} Redo the last pair or restart the set."
                    self.start_button.config(text="Record new set")
            # Preserve the result/error while continuing the camera preview.
            if self.recorder.active or captured or not self.recorder.pairs:
                self.status.config(text=status)
                self.progress["value"] = progress * HOLD_SECONDS
            height, width = frame.shape[:2]
            scale = min(max(1, self.preview_frame.winfo_width()) / width,
                        max(1, self.preview_frame.winfo_height()) / height)
            preview = self.cv2.resize(frame, (max(1, round(width * scale)),
                                              max(1, round(height * scale))))
            encoded, png = self.cv2.imencode(".png", preview)
            if not encoded:
                raise RuntimeError("Could not render the camera preview.")
            self.photo = tk.PhotoImage(data=png.tobytes())
            self.preview.config(image=self.photo)
        except Exception as error:
            self.status.config(text=f"Camera error: {error}")
            self.start_button.config(state="disabled")
            self.undo_button.config(state="disabled")
            self.release_camera()
            return
        self.after_id = self.root.after(15, self.tick)

    def release_camera(self) -> None:
        if self.camera is not None:
            self.camera.release()
            self.camera = None
        if self.detector is not None:
            self.detector.close()
            self.detector = None

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        if self.after_id is not None:
            self.root.after_cancel(self.after_id)
        self.release_camera()
        self.root.destroy()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--camera", type=int, default=0)
    parser.add_argument("--swap-hands", action="store_true",
                        help="reverse L/R if the camera already mirrors its output")
    parser.add_argument("--word-list", type=Path,
                        default=Path(__file__).with_name("durhack_word_list.csv"),
                        help="same CSV, in the same order, used for encoding")
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
