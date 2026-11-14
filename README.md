# durhack26

Hand pose encoder and renderer.

```sh
python3 make_hand.py "L F N 00000 | R B E 10101"
```

Open the generated hands.svg in a browser. Python 3; no extra packages.
Finger bits: thumb, index, middle, ring, pinky.

encoder.py requires a separate word-list CSV with a single word column,
provided via --word-list. The data file is excluded from this repository.
