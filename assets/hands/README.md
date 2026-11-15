# Finger binary artwork

Original: https://commons.wikimedia.org/wiki/File:Finger_binary_hand_only.gif
Direct download: https://upload.wikimedia.org/wikipedia/commons/1/1b/Finger_binary_hand_only.gif
Author: LucasBrown, 26 April 2024.
License: CC0 1.0 (public domain dedication): https://creativecommons.org/publicdomain/zero/1.0/

32 animation frames extracted to PNG and losslessly vectorized as pixel rectangles in SVG.
F files preserve the light original; B files replace white with dark slate.
B is a color convention for backhand, using the same artwork rather than a distinct anatomical drawing.
Filename bits run thumb, index, middle, ring, pinky. GIF frame index is
sum(bit[finger] * 2**finger). Source orientation: left palm, fingers north.

Normal rendering: `python3 make_hand.py "L F N 00000 | R B E 10101"`
The main script needs only Python's standard library and bundles the SVG artwork
into its output, which can be moved independently of the assets directory.
Rebuild assets: `python3 extract_hand_frames.py` (requires Pillow).
