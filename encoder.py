"""Encode three words as three pairs of hand poses using only Python's standard library."""

import argparse
import csv
from pathlib import Path


FINGER_PATTERNS = [
    "".join(str((number >> finger) & 1) for finger in range(5))
    for number in range(32)
]
# Finger order is thumb, index, middle, ring, pinky. Exclude the UK offensive
# back-of-hand V sign (index + middle), middle finger alone, and thumb + middle.
BANNED_BACK_PATTERNS = {"01100", "00100", "10100"}
FRONT_STATES = 4 * len(FINGER_PATTERNS)
BACK_PATTERNS = [bits for bits in FINGER_PATTERNS if bits not in BANNED_BACK_PATTERNS]
HAND_RADIX = FRONT_STATES + 4 * len(BACK_PATTERNS)  # 244 states per hand
HAND_CODES = HAND_RADIX**6


def _describe_hand(code: int) -> str:
    """Convert one base-244 digit into its pose description."""
    if code < FRONT_STATES:
        view = "F"
        direction_index, pattern_index = divmod(code, 32)
        bits = FINGER_PATTERNS[pattern_index]
    else:
        view = "B"
        direction_index, pattern_index = divmod(code - FRONT_STATES, len(BACK_PATTERNS))
        bits = BACK_PATTERNS[pattern_index]
    return f"{view} {'NESW'[direction_index]} {bits}"


def load_words(path: Path) -> list[str]:
    with path.open(newline="", encoding="utf-8-sig") as source:
        reader = csv.DictReader(source)
        if reader.fieldnames != ["word"]:
            raise ValueError("Word list must have one column headed 'word'.")
        words = [row["word"].strip().lower() for row in reader]
    if not words or any(not word for word in words):
        raise ValueError("Word list must contain nonempty words.")
    if len(set(words)) != len(words):
        raise ValueError("Word list contains duplicate words.")
    if len(words) ** 3 > HAND_CODES:
        raise ValueError(f"Word list is too large for six hands ({HAND_CODES:,} allowed codes).")
    return words


def encode(words: list[str], vocabulary: list[str]) -> tuple[int, str, list[str]]:
    if len(words) != 3:
        raise ValueError("Exactly three words are required.")
    indices = {word: index for index, word in enumerate(vocabulary)}
    number = 0
    for word in words:
        if word not in indices:
            raise ValueError(f"Unknown word: {word!r}")
        number = number * len(vocabulary) + indices[word]

    digits = [0] * 6
    remaining = number
    for index in range(5, -1, -1):
        remaining, digits[index] = divmod(remaining, HAND_RADIX)
    code = " ".join(str(digit) for digit in digits)
    hands = [_describe_hand(digit) for digit in digits]
    return number, code, hands


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("words", nargs=3, metavar="WORD")
    parser.add_argument(
        "--word-list",
        type=Path,
        default=Path(__file__).with_name("durhack_word_list.csv"),
        help="CSV word list (default: durhack_word_list.csv beside this script)",
    )
    args = parser.parse_args()
    words = [word.strip().lower() for word in args.words]
    try:
        vocabulary = load_words(args.word_list)
        number, code, hands = encode(words, vocabulary)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))

    print(f"Words: {' '.join(words)}")
    print(f"Denary: {number}")
    print(f"Hand codes (base {HAND_RADIX}): {code}")
    print("Hand representation:")
    for pair in range(3):
        print(f"Pair {pair + 1}: L {hands[pair * 2]} | R {hands[pair * 2 + 1]}")
    print()
    print("L/R: left/right hand; F/B: palm/back visible to observer.")
    print("N/E/S/W: wrist-to-knuckles direction in a fixed compass frame.")
    print("Finger bits: thumb, index, middle, ring, little; 1=extended, 0=curled.")


if __name__ == "__main__":
    main()
