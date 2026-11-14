#!/usr/bin/env python3
"""Render two hands from bundled Wikimedia finger-binary poses. No dependencies.

Usage: python3 make_hand.py 'L F N 00000 | R B E 10101' -o hands.svg
Bits: thumb, index, middle, ring, pinky; 1 = raised, 0 = folded.
F = light palm, B = dark back; N/E/S/W = wrist-to-fingertip direction.
"""
from __future__ import annotations

import argparse
import html
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ASSETS = Path(__file__).resolve().parent / 'assets' / 'hands'
ROTATIONS = {'N': 0, 'E': 90, 'S': 180, 'W': 270}
ET.register_namespace('', 'http://www.w3.org/2000/svg')


def parse_pair(text: str) -> list[tuple[str, str, str, str]]:
    text = re.sub(r'^\s*Pair\s+\d+\s*:\s*', '', text, flags=re.I)
    parts = text.strip().split('|')
    pattern = re.compile(r'\s*([LR])\s+([FB])\s+([NESW])\s+([01]{5})\s*', re.I)
    matches = [pattern.fullmatch(part) for part in parts]
    if len(matches) != 2 or any(match is None for match in matches):
        raise ValueError('Expected L/R F/B N/E/S/W and five bits for each hand, separated by |')
    hands = [tuple(match.groups()) for match in matches]
    hands = [(side.upper(), view.upper(), direction.upper(), bits)
             for side, view, direction, bits in hands]
    if {hand[0] for hand in hands} != {'L', 'R'}:
        raise ValueError('A pair must contain one left and one right hand')
    return hands


def draw_hand(side: str, view: str, direction: str, bits: str) -> str:
    path = ASSETS / f'{view}_{bits}.svg'
    if not path.exists():
        raise FileNotFoundError(f'Missing {path}. Run python3 extract_hand_frames.py to rebuild assets.')
    pose = ET.fromstring(path.read_text(encoding='utf-8'))
    pose.set('x', '-96')
    pose.set('y', '-124')
    pose.set('width', '192')
    pose.set('height', '248')
    # Source is a left palm (thumb on viewer's right). Back view reverses it.
    mirror = -1 if (side == 'R') != (view == 'B') else 1
    return (f'<g transform="translate(160 185) rotate({ROTATIONS[direction]})">'
            f'<g transform="scale({mirror} 1)">{ET.tostring(pose, encoding="unicode")}</g></g>')


def raised_fingers(bits: str) -> str:
    """Return the names of the fingers marked as raised in thumb-to-pinky order."""
    names = ('thumb', 'index', 'middle', 'ring', 'pinky')
    raised = [name for name, bit in zip(names, bits) if bit == '1']
    return 'Raised: ' + (', '.join(raised) if raised else 'none')


def make_svg(pair: str) -> str:
    cards = []
    for x, (side, view, direction, bits) in zip((0, 320), parse_pair(pair)):
        title = f'{side} · {"palm" if view == "F" else "back"} · {direction}'
        cards.append(
            f'<g transform="translate({x} 0)">'
            '<rect x="10" y="10" width="300" height="350" rx="18" fill="#faf7f2" stroke="#ded9d0"/>'
            f'<text x="160" y="38" text-anchor="middle" font-family="sans-serif" font-size="17" fill="#333">{html.escape(title)}</text>'
            + draw_hand(side, view, direction, bits)
            + f'<text x="160" y="340" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#666">{html.escape(raised_fingers(bits))}</text></g>')
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="640" height="370" viewBox="0 0 640 370">'
            '<title>Hand pair</title><desc>Finger binary artwork by LucasBrown, CC0; dark fill denotes back of hand.</desc>'
            '<rect width="640" height="370" fill="#eeeae4"/>' + ''.join(cards) + '</svg>')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pair', nargs='?', default='L F N 00000 | R B E 10101')
    parser.add_argument('-o', '--output', default='hands.svg')
    args = parser.parse_args()
    try:
        svg = make_svg(args.pair)
    except (ValueError, FileNotFoundError) as error:
        parser.error(str(error))
    Path(args.output).write_text(svg, encoding='utf-8')
    print(f'Wrote {Path(args.output).resolve()}')


if __name__ == '__main__':
    main()
