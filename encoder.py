"""Encode three words as three pairs of hand poses using only Python's standard library."""

import argparse
import csv
from pathlib import Path


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
    if len(words) ** 3 > 2**48:
        raise ValueError("Word list is too large for six hands (48 bits).")
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

    binary = format(number, "048b")
    hands = []
    for offset in range(0, 48, 8):
        chunk = binary[offset : offset + 8]
        orientation = "FB"[int(chunk[0])]
        direction = "NESW"[int(chunk[1:3], 2)]
        hands.append(f"{orientation} {direction} {chunk[3:]}")
    return number, binary, hands


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
        number, binary, hands = encode(words, vocabulary)
    except (OSError, ValueError, csv.Error) as error:
        parser.error(str(error))

    print(f"Words: {' '.join(words)}")
    print(f"Denary: {number}")
    print(f"Binary (48 bits): {binary}")
    print("Hand representation:")
    for pair in range(3):
        print(f"Pair {pair + 1}: L {hands[pair * 2]} | R {hands[pair * 2 + 1]}")
    print()
    print("L/R: left/right hand; F/B: palm/back visible to observer.")
    print("N/E/S/W: wrist-to-knuckles direction in a fixed compass frame.")
    print("Finger bits: thumb, index, middle, ring, little; 1=extended, 0=curled.")


if __name__ == "__main__":
    main()