#!/usr/bin/env python3
"""Show one live hand pair. Install: pip install mediapipe opencv-python numpy."""

import argparse
from collections import deque
from pathlib import Path
import time
from urllib.request import urlopen

import cv2
import mediapipe as mp
import numpy as np


MODEL_URL = (
    'https://storage.googleapis.com/mediapipe-models/hand_landmarker/'
    'hand_landmarker/float16/1/hand_landmarker.task'
)


def palm_view(side, landmarks):
    """Classify palm winding in the camera image using corrected L/R labels."""
    wrist, index, pinky = landmarks[0], landmarks[5], landmarks[17]
    ax, ay = index.x - wrist.x, index.y - wrist.y
    bx, by = pinky.x - wrist.x, pinky.y - wrist.y
    area = ax * by - ay * bx
    # Normalize for hand size; an edge-on palm has no reliable facing direction.
    scale = max(np.hypot(ax, ay) * np.hypot(bx, by), 1e-9)
    if abs(area) / scale < 0.12:
        return '?'
    front = area < 0 if side == 'L' else area > 0
    return 'F' if front else 'B'


def finger_bits(landmarks, width, height):
    """Measure extension in a palm-relative frame, using pixel coordinates.

    Pixel scaling matters: normalized camera x/y have different units on a
    non-square frame. Avoid inferred depth, which can wobble as a hand rotates.
    """
    points = np.array([(p.x * width, p.y * height) for p in landmarks])
    forward = points[9] - points[0]
    palm_length = max(np.linalg.norm(forward), 1e-9)
    forward /= palm_length
    across = np.array([-forward[1], forward[0]])
    local = np.column_stack(((points - points[0]) @ across,
                             (points - points[0]) @ forward)) / palm_length

    def distance(a, b):
        return np.linalg.norm(local[a] - local[b])

    # The thumb extends sideways away from the little-finger side of the palm.
    radial = local[5] - local[17]
    palm_width = max(np.linalg.norm(radial), 1e-9)
    radial /= palm_width
    thumb_reach = np.dot(local[4] - local[2], radial)
    thumb_path = distance(2, 3) + distance(3, 4)
    thumb = (thumb_reach > 0.25 * palm_width
             and distance(2, 4) > 0.8 * thumb_path
             and distance(4, 5) > 0.45 * palm_width)
    bits = str(int(thumb))
    for base in (5, 9, 13, 17):
        # Follow each finger's own axis to allow fingers to spread sideways.
        axis = local[base] - local[0]
        axis /= max(np.linalg.norm(axis), 1e-9)
        pip, tip = base + 1, base + 3
        reach = np.dot(local[tip] - local[pip], axis)
        length = np.dot(local[tip] - local[base], axis)
        path = sum(distance(i, i + 1) for i in range(base, tip))
        straightness = distance(base, tip) / max(path, 1e-9)
        bits += str(int(reach > 0.12 and length > 0.35 and straightness > 0.75))
    return bits


def describe(side, landmarks, width, height):
    """Estimate view, screen direction and thumb-to-pinky extension bits."""
    bits = finger_bits(landmarks, width, height)
    wrist, middle = landmarks[0], landmarks[9]
    dx, dy = (middle.x - wrist.x) * width, (middle.y - wrist.y) * height
    direction = ('E' if dx > 0 else 'W') if abs(dx) > abs(dy) else ('S' if dy > 0 else 'N')
    return f"{side} {palm_view(side, landmarks)} {direction} {bits}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--camera', type=int, default=0)
    parser.add_argument('--swap-hands', action='store_true',
                        help='reverse L/R if the camera already mirrors its output')
    args = parser.parse_args()
    model = Path(__file__).with_name('hand_landmarker.task')
    if not model.exists():
        print('Downloading hand model (first run only)...')
        with urlopen(MODEL_URL, timeout=60) as response:
            data = response.read()
        model.write_bytes(data)

    options = mp.tasks.vision.HandLandmarkerOptions(
        base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
        running_mode=mp.tasks.vision.RunningMode.VIDEO,
        num_hands=2,
    )
    camera = cv2.VideoCapture(args.camera)
    history = {side: deque(maxlen=5) for side in 'LR'}
    try:
        if not camera.isOpened():
            raise RuntimeError('Cannot open camera. Allow camera access or try --camera 1.')
        with mp.tasks.vision.HandLandmarker.create_from_options(options) as detector:
            while True:
                ok, frame = camera.read()
                if not ok:
                    raise RuntimeError('Could not read a camera frame.')
                # Display a selfie view. The Tasks model labels on this flipped
                # input need reversing to refer to the user's anatomical hands.
                frame = cv2.flip(frame, 1)
                height, width = frame.shape[:2]
                image = mp.Image(image_format=mp.ImageFormat.SRGB,
                                 data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                result = detector.detect_for_video(image, time.monotonic_ns() // 1_000_000)
                hands = {}
                for labels, landmarks in zip(result.handedness, result.hand_landmarks):
                    side = {'Left': 'R', 'Right': 'L'}[labels[0].category_name]
                    if args.swap_hands:
                        side = 'R' if side == 'L' else 'L'
                    if side not in hands or labels[0].score > hands[side][0]:
                        hands[side] = (labels[0].score, describe(side, landmarks, width, height))
                    for p in landmarks:
                        cv2.circle(frame, (int(p.x * width), int(p.y * height)), 3, (0, 255, 0), -1)
                descriptions = {}
                for side in 'LR':
                    if side not in hands:
                        history[side].clear()
                        descriptions[side] = f'{side} -- -- -----'
                        continue
                    fields = hands[side][1].split()
                    history[side].append(fields)
                    # Vote for each finger independently so one noisy fingertip
                    # does not change an otherwise stable multi-finger pose.
                    samples = history[side]
                    bits = ''.join(str(int(sum(int(s[3][i]) for s in samples) > len(samples) / 2))
                                   for i in range(5))
                    view = fields[1]
                    if view != '?':
                        votes = [s[1] for s in samples if s[1] != '?']
                        if votes.count('F') != votes.count('B'):
                            view = 'F' if votes.count('F') > votes.count('B') else 'B'
                    descriptions[side] = f'{side} {view} {fields[2]} {bits}'
                pair = ' | '.join(descriptions[s] for s in 'LR')
                banner = np.zeros((95, width, 3), dtype=np.uint8)
                scale = min(0.75, (width - 20) / max(cv2.getTextSize(pair, cv2.FONT_HERSHEY_SIMPLEX, 1, 2)[0][0], 1))
                cv2.putText(banner, pair, (10, 35), cv2.FONT_HERSHEY_SIMPLEX, scale, (255, 255, 255), 2)
                cv2.putText(banner, 'Show both hands | Q / Esc: quit', (10, 75),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (180, 180, 180), 1)
                cv2.imshow('Live hand pair', np.vstack((banner, frame)))
                if cv2.waitKey(1) & 0xFF in (ord('q'), 27):
                    break
                if cv2.getWindowProperty('Live hand pair', cv2.WND_PROP_VISIBLE) < 1:
                    break
    finally:
        camera.release()
        cv2.destroyAllWindows()


if __name__ == '__main__':
    main()
