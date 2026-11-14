#!/usr/bin/env python3
"""Encode three words and render their six hand poses as one SVG image.

Usage: python3 encode_and_make_hands.py WORD1 WORD2 WORD3 -o hands.svg
"""
from __future__ import annotations

import argparse
import csv
import html
from pathlib import Path

from encoder import encode, load_words
from make_hand import draw_hand, raised_fingers


def make_svg(hands: list[str]) -> str:
    """Render the six encoded hand descriptions as three stacked pairs."""
    if len(hands) != 6:
        raise ValueError("Exactly six encoded hand descriptions are required.")

    rows: list[str] = []
    for pair_index in range(3):
        y = pair_index * 370
        row_hands = hands[pair_index * 2 : pair_index * 2 + 2]
        cards: list[str] = []
        for x, (side, description) in zip((0, 320), zip(("L", "R"), row_hands)):
            view, direction, bits = description.split()
            title = f'{side} · {"palm" if view == "F" else "back"} · {direction}'
            cards.append(
                f'<g transform="translate({x} 0)">'
                '<rect x="10" y="10" width="300" height="350" rx="18" '
                'fill="#faf7f2" stroke="#ded9d0"/>'
                f'<text x="160" y="38" text-anchor="middle" font-family="sans-serif" '
                f'font-size="17" fill="#333">{html.escape(title)}</text>'
                + draw_hand(side, view, direction, bits)
                + '<text x="160" y="340" text-anchor="middle" font-family="sans-serif" '
                f'font-size="12" fill="#666">{html.escape(raised_fingers(bits))}</text></g>'
            )
        rows.append(f'<g transform="translate(0 {y})">' + ''.join(cards) + '</g>')

    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="640" height="1110" '
        'viewBox="0 0 640 1110">'
        '<title>Three encoded hand pairs</title>'
        '<desc>Finger binary artwork by LucasBrown, CC0; dark fill denotes back of hand.</desc>'
        '<rect width="640" height="1110" fill="#eeeae4"/>'
        + ''.join(rows)
        + '</svg>'
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("words", nargs=3, metavar="WORD")
    parser.add_argument(
        "--word-list",
        type=Path,
        default=Path(__file__).with_name("durhack_word_list.csv"),
        help="CSV word list (default: durhack_word_list.csv beside this script)",
    )
    parser.add_argument("-o", "--output", type=Path, default=Path("encoded_hands.svg"))
    args = parser.parse_args()

    words = [word.strip().lower() for word in args.words]
    try:
        vocabulary = load_words(args.word_list)
        number, code, hands = encode(words, vocabulary)
        svg = make_svg(hands)
        args.output.write_text(svg, encoding="utf-8")
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))

    print(f"Words: {' '.join(words)}")
    print(f"Denary: {number}")
    print(f"Hand codes (base 244): {code}")
    print(f"Wrote {args.output.resolve()}")


if __name__ == "__main__":
    main()
