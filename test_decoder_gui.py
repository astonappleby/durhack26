"""Exercise timed capture and decoder integration without opening a camera."""
import unittest

from decoder import decode, parse_pairs
from decoder_gui import HOLD_SECONDS, PairRecorder, pair_problem
from encoder import encode


PAIR = "L F N 00000 | R F N 00000"
OTHER = "L F N 10000 | R F N 00000"
POINTS = ((0.2, 0.3),) * 42


class PairRecorderTests(unittest.TestCase):
    def setUp(self):
        self.recorder = PairRecorder()
        self.recorder.start()

    def update(self, pair=PAIR, now=0.0, points=POINTS, visible=True):
        return self.recorder.update(pair, points, now, both_visible=visible)

    def capture(self, pair, start):
        self.update(pair, now=start)
        return self.update(pair, now=start + HOLD_SECONDS)

    def test_requires_full_three_seconds_and_blocks_repeated_hold(self):
        self.update()
        progress, captured, _ = self.update(now=2.99)
        self.assertFalse(captured)
        self.assertLess(progress, 1)
        self.assertTrue(self.update(now=3)[1])
        self.assertFalse(self.update(now=30)[1])
        self.assertEqual(self.recorder.pairs, [PAIR])

    def test_pose_change_restarts_hold(self):
        self.update()
        self.update(OTHER, now=2)
        self.assertFalse(self.update(OTHER, now=3)[1])
        self.assertTrue(self.update(OTHER, now=5)[1])
        self.assertEqual(self.recorder.pairs, [OTHER])

    def test_movement_with_same_pose_restarts_hold(self):
        moved = ((0.3, 0.3),) * 42
        self.update()
        self.update(now=2, points=moved)
        self.assertFalse(self.update(now=3, points=moved)[1])
        self.assertTrue(self.update(now=5, points=moved)[1])

    def test_missing_or_ambiguous_hand_restarts_hold(self):
        for visible in (False, True):
            with self.subTest(visible=visible):
                self.recorder.start()
                self.update()
                self.update(None, now=2, visible=visible)
                self.update(now=3)
                self.assertFalse(self.update(now=5)[1])
                self.assertTrue(self.update(now=6)[1])

    def test_deliberate_release_allows_identical_consecutive_pairs(self):
        self.capture(PAIR, 0)
        self.update(None, now=4, visible=False)
        self.update(None, now=4.5, visible=False)
        self.assertTrue(self.capture(PAIR, 5)[1])
        self.assertEqual(self.recorder.pairs, [PAIR, PAIR])

    def test_tracking_flicker_does_not_unlock_same_pair(self):
        self.capture(PAIR, 0)
        self.update(None, now=4, visible=False)
        self.update(None, now=4.1, visible=False)
        self.update(now=4.2)
        self.assertFalse(self.update(now=8)[1])
        self.assertEqual(len(self.recorder.pairs), 1)

    def test_invalid_back_pattern_is_not_recorded(self):
        invalid = "L B N 01100 | R F N 00000"
        self.assertIsNotNone(pair_problem(invalid))
        self.assertFalse(self.capture(invalid, 0)[1])
        self.assertEqual(self.recorder.pairs, [])

    def test_stops_at_three_and_supports_redo_and_restart(self):
        for index, pair in enumerate((PAIR, OTHER, PAIR)):
            self.assertTrue(self.capture(pair, index * 4)[1])
        self.assertFalse(self.recorder.active)
        self.capture(OTHER, 20)
        self.assertEqual(len(self.recorder.pairs), 3)
        self.recorder.undo()
        self.assertTrue(self.recorder.active)
        self.assertEqual(self.recorder.pairs, [PAIR, OTHER])
        self.assertFalse(self.update(PAIR, now=30)[1])
        self.assertTrue(self.capture(OTHER, 31)[1])
        self.recorder.start()
        self.assertEqual(self.recorder.pairs, [])
        self.assertIsNone(self.recorder.last_pair)

    def test_encoder_camera_text_decoder_round_trip(self):
        vocabulary = [f"word{i}" for i in range(1000)]
        expected = [vocabulary[i] for i in (20, len(vocabulary) // 2, len(vocabulary) - 1)]
        _, _, hands = encode(expected, vocabulary)
        for index in range(3):
            pair = f"L {hands[index * 2]} | R {hands[index * 2 + 1]}"
            self.assertTrue(self.capture(pair, index * 5)[1])
        text = "\n".join(f"Pair {i}: {pair}" for i, pair in enumerate(self.recorder.pairs, 1))
        self.assertEqual(decode(parse_pairs(text), vocabulary)[2], expected)


if __name__ == "__main__":
    unittest.main()
