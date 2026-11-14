# durhack26

Encode three words as a sequence of three hand-pose pairs, then use a webcam to
read the poses and recover the words. Built for DurHack 2026 with Python,
MediaPipe, OpenCV, and Tkinter.

The encoder GUI lets you search a vocabulary and preview all six hand poses. The
decoder GUI watches both hands, captures each pair after a three-second steady
hold, and displays the three words once the sequence is complete. It also accepts
three uploaded photos and can save a photo of each live capture. Command-line
tools support text encoding, decoding, and SVG rendering.

## Quick start

### 1. Set up Python

Clone the repository and create a virtual environment:

```sh
git clone https://github.com/astonappleby/durhack26.git
cd durhack26
python3 -m venv .venv
```

Activate it on macOS or Linux:

```sh
source .venv/bin/activate
```

Or in Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Install the webcam dependencies:

```sh
python -m pip install mediapipe opencv-python numpy
```

Both desktop GUIs need Tkinter. Check that it is available with
`python -m tkinter`; this should open a small test window. If it is missing,
install Tkinter for your Python distribution. The text encoder, text decoder,
and SVG renderers use only Python's standard library.

### 2. Use the included word list

The repository includes `durhack_word_list.csv`, containing **30,000 words**.
Both GUIs and the word-based command-line tools load it automatically, so no
separate vocabulary download or configuration is needed.

To supply a custom vocabulary, use a UTF-8 CSV with exactly one column, headed
`word`, and one nonempty, unique word per row. For example:

```csv
word
apple
river
castle
```

Words are trimmed and converted to lowercase when loaded. Duplicate words after
that normalization are rejected. The vocabulary can contain up to **59,536**
words.

**Encoding and decoding must use the same vocabulary in the same row order.**
Changing the order changes the meaning of the hand sequence. To use a different
file, pass `--word-list /path/to/words.csv` to either GUI or any word-based
command-line tool.

### 3. Encode three words

```sh
python full_encode_gui.py
```

Type into each word field to search the vocabulary. Choose a suggestion by
double-clicking it, or press Down followed by Enter. Click **Show encoded hands**
to display the three pairs. Read them from top to bottom, with your left and
right hands matching the labelled cards. **Change words** clears the preview so
you can edit the phrase.

The complete six-hand sequence represents the complete three-word phrase.
Individual pairs do not each represent one word.

### 4. Decode with your webcam

```sh
python decoder_gui.py
```

1. Select **Live camera**, click **Start recording**, and allow camera access if prompted.
2. Show both hands in the first pair's poses and hold still for **three seconds**.
   The countdown and progress bar show when the pair will be captured.
3. Change to the second pair and hold again, then repeat for the third pair.
4. Read the three words in **Decoded words** after the final capture.

The controls and preview are scrollable with your mouse wheel, trackpad, or the
right-hand scrollbar. **Decoded words** stays visible at the bottom of the window,
including on smaller screens.

The hold timer resets when the recognized pose changes, a hand disappears, or
hand landmarks move beyond the stability tolerance. Missing hands, unclear
palm/back views, and back-of-hand patterns excluded by the encoder are not
recorded.

After a capture, change pose to begin the next hold. If consecutive pairs are
identical, lower at least one hand out of view for **half a second**, then show
the same pair again. This prevents one long hold from filling multiple slots.

| Control | Action |
| --- | --- |
| **Redo last pair** | Remove the most recent capture and record it again. |
| **Restart set** / **Record new set** | Clear the sequence and begin three new captures. |
| **Copy pairs** | Copy the captured pair descriptions for use with the text decoder. |
| **Quit** / Esc | Close the GUI and release the camera. |

To save the three hand positions, tick **Save a photo for each live capture**
before starting. Use **Save folder…** to choose a destination; the default is
`captures/` beside the script. Each recording set gets a separate `set-…` folder
with `pair_1.png`, `pair_2.png`, and `pair_3.png`. The photos use the mirrored
camera view without the green tracking dots. Redoing a pair replaces its saved
photo; starting a new set keeps the earlier set's folder. The save setting and
destination are fixed until the set is complete or restarted.

### 5. Decode from photos

In the decoder GUI, select **Upload photos**. Use the **Upload photo…** button
beside each pair to choose a PNG, JPEG, WebP, or BMP image containing both hands.
Assign the pictures to pairs 1, 2, and 3 in their original sequence; they can be
uploaded in any order. The words appear automatically once all three pairs have
been recognized. There is no hold timer in photo mode, and the webcam stays off.

Use **View** to inspect a loaded photo, **Replace photo…** to correct a pair, or
**Clear photos** to start over. A photo that cannot be recognized leaves that
slot unchanged and shows an explanation.

Leave **Photos already use selfie view** checked for photos saved by this GUI
or other mirrored images. Uncheck it for ordinary, unmirrored camera photos;
the app mirrors them before recognition. Changing this setting reprocesses all
loaded photos. Switching between photo and live modes clears the current set.

The first decoder or camera run downloads `hand_landmarker.task` beside the
scripts. This requires an internet connection and write access to the project directory.
Subsequent runs reuse the model. Camera frames are processed locally.

To select a different camera or reverse the hand labels:

```sh
python decoder_gui.py --camera 1
python decoder_gui.py --swap-hands
```

## Hand-pose notation

Each pair describes one left hand and one right hand:

```text
Pair 1: L F N 00000 | R B E 10101
```

| Field | Meaning |
| --- | --- |
| `L` / `R` | Your anatomical left or right hand. |
| `F` / `B` | Palm or back of the hand facing the observer. |
| `N` / `E` / `S` / `W` | Wrist-to-knuckles direction: up, right, down, or left. |
| Five bits | Thumb, index, middle, ring, pinky; `1` means extended and `0` means curled. |

Camera directions refer to the **mirrored preview**, with north at the top.
Missing hands appear as dashes, and an uncertain palm/back view appears as `?`.

## Command-line tools

Run these commands from the project directory with the virtual environment
active. Each command that accepts a word list defaults to
`durhack_word_list.csv` beside its script.

### Encode words as text

```sh
python encoder.py apple river castle
```

Prints the combined decimal value, six base-244 hand codes, and three labelled
pairs. The words must exist in your vocabulary.

### Render all three pairs as an SVG

```sh
python full_encode.py apple river castle -o encoded_hands.svg
```

Open `encoded_hands.svg` in a browser. The output embeds its artwork and can be
shared independently of the repository.

### Decode pairs from a file

Save just the three `Pair 1:`, `Pair 2:`, and `Pair 3:` lines from the encoder,
or use the decoder GUI's **Copy pairs** button, to create `poses.txt`. Then run:

```sh
python decoder.py --input poses.txt
```

The decoder also accepts quoted multiline pair text as its positional argument,
or pair text piped into standard input. It requires exactly three pairs, each
containing one left and one right hand.

### Inspect live hand recognition

```sh
python camera_pair.py
```

Displays the current pair and webcam preview without collecting a sequence.
Use `--camera 1` to select another camera or `--swap-hands` to reverse the labels.
Press Q or Esc to quit. This diagnostic view can show patterns that the word
encoder excludes.

### Render a single pair

```sh
python make_hand.py "L F N 00000 | R B E 10101" -o hands.svg
```

This renderer does not need a word list or camera dependencies.

## How the encoding works

Each hand has four directions and 32 finger patterns for each visible side.
Three back-of-hand patterns are excluded: `01100` (index and middle), `00100`
(middle only), and `10100` (thumb and middle). This leaves **244 states per hand**:

```text
4 × 32 palm states + 4 × 29 back states = 244
```

The encoder packs the three vocabulary indices into one number using the
vocabulary size as its base. It then expresses that number as six base-244
digits, ordered left then right within pairs 1, 2, and 3. The decoder reverses
those steps. A sequence outside the vocabulary's range is rejected.

The webcam recognizer estimates landmarks with MediaPipe, measures finger
extension and palm orientation, and smooths finger and palm/back classifications
across five frames. Recognition is approximate: keep both hands visible, fingers
separated, and palms or backs roughly parallel to the camera.

## Project files

| File | Purpose |
| --- | --- |
| `full_encode_gui.py` | Search three words and preview the encoded poses. |
| `decoder_gui.py` | Decode three photos or steady live pairs, with optional capture photos. |
| `camera_pair.py` | Live hand tracking and pose classification. |
| `encoder.py` / `decoder.py` | Text conversion and shared encoding logic. |
| `durhack_word_list.csv` | Shared default vocabulary of 30,000 words. |
| `full_encode.py` | Render the full sequence as an SVG. |
| `make_hand.py` | Render one pair using the bundled hand artwork. |
| `extract_hand_frames.py` | Rebuild the SVG and PNG pose assets from the source GIF. |
| `test_decoder_gui.py` | Capture-timing and encoder/decoder integration tests. |
| `assets/hands/` | Source artwork and bundled SVG poses. |

The vocabulary is tracked in Git. The downloaded hand model, the default
`captures/` folder, and SVG/PNG outputs in the project root are ignored.

## Optional development tests

`test_decoder_gui.py` contains 16 automated checks added with the decoder GUI.
They feed simulated poses, hand positions, and timestamps into the capture logic
to check its behavior. You do not need to run them to use the application.

```sh
python -m unittest -v test_decoder_gui
```

The tests cover the three-second hold, movement and tracking resets, repeated
poses, excluded patterns, redo/restart behavior, and an encoder-to-decoder round
trip. They also check photo ordering, mirror settings, invalid photo handling,
independent photo recognition, and snapshot file handling. They use simulated
inputs and do not open a camera or GUI, so they do not measure live webcam
recognition accuracy. Check that manually with
`camera_pair.py` or `decoder_gui.py`. Tkinter must still be importable because
the tests import the GUI module.

## Troubleshooting

| Problem | What to check |
| --- | --- |
| Word-list file is missing | Restore the included `durhack_word_list.csv` from the repository or supply a custom file with `--word-list`. |
| A word is rejected | Choose a word present in the loaded CSV; check for duplicate or empty rows if the list fails to load. |
| Camera will not open | Allow camera access for Python or your terminal, close other camera apps, and try `--camera 1`. |
| Left and right are reversed | Restart with `--swap-hands`. |
| Countdown keeps resetting | Improve lighting, keep both hands fully visible, avoid overlapping fingers, and hold palms/backs toward the camera. |
| The same pair will not record twice | Lower a hand out of view for half a second between captures. |
| Decoding fails or gives unexpected words | Check every pose, pair order, and the vocabulary file and row order. Redo the last pair or restart the set. |
| Tkinter cannot be imported or a GUI will not open | Use a Python installation with Tk support and run in a desktop session. |
| An uploaded photo is not recognized | Ensure both hands are visible, use a supported image format, and check **Photos already use selfie view** matches the image. |
| Capture photos cannot be saved | Check the save status above the preview and choose a writable folder before restarting the set. |
| Model download fails | Check your internet connection and permission to write `hand_landmarker.task` in the project directory, then retry. |

## Artwork credits

The hand illustrations are derived from LucasBrown's
[Finger binary hand only](https://commons.wikimedia.org/wiki/File:Finger_binary_hand_only.gif)
artwork, dedicated to the public domain under
[CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/). The dark back-of-hand
variants use recolored copies of the same artwork. See
[the asset notes](assets/hands/README.md) for attribution and extraction details.

To rebuild the assets from the bundled GIF:

```sh
python -m pip install Pillow
python extract_hand_frames.py
```
