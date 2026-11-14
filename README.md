# durhack26

Hand pose encoder and renderer.

Show one live hand pair from your webcam:

```sh
python3 -m pip install mediapipe opencv-python numpy
python3 camera_pair.py
```

The first run downloads the MediaPipe hand model. Allow camera access when
prompted. Use `--camera 1` to select another camera; press Q or Esc to quit.
The window shows `L F/B N/E/S/W 00000 | R F/B N/E/S/W 00000` and a camera
preview. Missing hands show dashes. Directions refer to the mirrored preview
(north is up). Finger bits and palm/back are estimates; keep your palms roughly
parallel to the camera and fingers visible for best results. This shows the
observed pose, including patterns the word encoder excludes.

```sh
python3 make_hand.py "L F N 00000 | R B E 10101"
```

Open the generated hands.svg in a browser. Python 3; no extra packages.
Finger bits: thumb, index, middle, ring, pinky.

encoder.py requires a separate word-list CSV with a single word column,
provided via --word-list. The data file is excluded from this repository.

Render all three encoded hand pairs:

```sh
python3 encode_and_make_hands.py WORD1 WORD2 WORD3 --word-list /path/to/words.csv -o encoded_hands.svg
```

Rebuild the pose assets from the bundled original GIF with
`python3 extract_hand_frames.py` (requires Pillow).

Decode three text pairs back into words:

```sh
python3 decoder.py "Pair 1: L F N 00000 | R F N 00000
Pair 2: L F E 10101 | R B E 00101
Pair 3: L B S 10011 | R F W 00011"
```

Alternatively use `python3 decoder.py --input poses.txt`, or pipe pair text into
stdin. Use `--word-list /path/to/words.csv` if needed. Decoding requires exactly
the same word list in the same order as encoding.

Record and decode three pairs in a webcam GUI:

```sh
python3 -m pip install mediapipe opencv-python numpy
python3 decoder_gui.py
```

Click **Start recording**, show both hands, and hold the pose still for three
seconds. The progress bar resets if your hands move, the recognized pose changes,
or a hand disappears. Each completed hold fills one pair slot; after all three
pairs, the decoded three words appear automatically. After each capture, change
pose before holding again. To record the same pair twice in a row, lower a hand
out of view for at least half a second, then show the pair again.

Use **Redo last pair** to replace the most recent capture, **Restart set** to
start over, or **Copy pairs** to copy the captured text for `decoder.py`.
Unknown palm/back views and finger patterns excluded by the encoder are not
recorded. The live preview uses the same hand recognition and mirrored directions
as `camera_pair.py`. `--camera 1`, `--swap-hands`, and
`--word-list /path/to/words.csv` are supported. The GUI also needs Python's Tkinter
(included with many Python installations).
