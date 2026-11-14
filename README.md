# durhack26

Hand pose encoder and renderer.

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
