"""Exercise timed capture and decoder integration without opening a camera."""
import unittest
from collections import deque
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock

from decoder import decode, parse_pairs
from decoder_gui import DecoderGUI, HOLD_SECONDS, PairRecorder, pair_problem
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


class PhotoModeTests(unittest.TestCase):
    def setUp(self):
        # Stub widgets and image IO so these checks need no desktop or webcam.
        self.app = DecoderGUI.__new__(DecoderGUI)
        self.app.cv2 = Mock()
        self.frame = Mock(shape=(480, 640, 3))
        self.app.cv2.imread.return_value = self.frame
        self.app.mode = Mock()
        self.app.mode.get.return_value = "photos"
        self.app.photos_are_mirrored = Mock()
        self.app.photos_are_mirrored.get.return_value = True
        self.app.image_pairs = [None] * 3
        self.app.image_frames = [None] * 3
        self.app.image_paths = [None] * 3
        self.app.words = Mock()
        self.app.status = Mock()
        self.app.live = Mock()
        self.app.progress = {}
        self.app.show_preview = Mock()
        self.app.refresh_slots = Mock()
        self.app.vocabulary = [f"word{i}" for i in range(1000)]
        self.app.observe = Mock(return_value=(PAIR, PAIR, POINTS, True))

    def test_three_photos_decode_in_slot_order_without_timer(self):
        expected = [self.app.vocabulary[i] for i in (20, 500, 999)]
        _, _, hands = encode(expected, self.app.vocabulary)
        for index in (2, 0, 1):
            pair = f"L {hands[index * 2]} | R {hands[index * 2 + 1]}"
            self.app.observe.return_value = pair, pair, POINTS, True
            self.app.load_photo(index, Path(f"pair_{index + 1}.png"))
        self.app.words.set.assert_called_with(" ".join(expected))
        self.assertEqual(self.app.progress["value"], 3)
        self.app.cv2.flip.assert_not_called()
        self.app.observe.assert_called_with(self.frame, still=True)

    def test_unmirrored_photo_is_flipped_once(self):
        self.app.photos_are_mirrored.get.return_value = False
        self.app.cv2.flip.return_value = self.frame
        self.app.load_photo(0, Path("camera.jpg"))
        self.app.cv2.flip.assert_called_once_with(self.frame, 1)

    def test_unreadable_image_preserves_previous_pair_and_result(self):
        self.app.image_pairs[0] = PAIR
        self.app.cv2.imread.return_value = None
        self.app.load_photo(0, Path("broken.png"))
        self.assertEqual(self.app.image_pairs[0], PAIR)
        self.app.words.set.assert_not_called()
        self.assertIn("Cannot read", self.app.status.config.call_args.kwargs["text"])

    def test_unrecognized_or_excluded_photo_is_not_accepted(self):
        for pair in (None, "L B N 01100 | R F N 00000"):
            with self.subTest(pair=pair):
                self.app.observe.return_value = "unclear", pair, POINTS, pair is not None
                self.app.load_photo(1, Path("unclear.png"))
                self.assertIsNone(self.app.image_pairs[1])

    def test_independent_photo_detection_ignores_video_history(self):
        del self.app.observe  # Exercise the real recognition method.
        landmarks = [SimpleNamespace(x=0.2, y=0.3)] * 21
        result = SimpleNamespace(
            handedness=[[SimpleNamespace(category_name=label, score=0.99)]
                        for label in ("Right", "Left")],
            hand_landmarks=[landmarks, landmarks])
        self.app.mp = Mock()
        self.app.image_detector = Mock()
        self.app.image_detector.detect.return_value = result
        self.app.detector = Mock()
        self.app.swap_hands = False
        self.app.history = {side: deque([[side, "B", "N", "11111"]] * 5, maxlen=5)
                            for side in "LR"}
        self.app.describe = lambda side, *_: f"{side} F N 00000"
        observed = self.app.observe(self.frame, still=True)
        self.assertEqual(observed[1], PAIR)
        self.app.detector.detect_for_video.assert_not_called()
        self.assertEqual(self.app.history["L"][0], ["L", "B", "N", "11111"])


class CapturePhotoTests(unittest.TestCase):
    def test_three_photos_use_one_folder_and_new_sets_keep_previous_files(self):
        app = DecoderGUI.__new__(DecoderGUI)
        app.cv2 = Mock()
        def write_image(path, _frame):
            Path(path).write_bytes(b"simulated image")
            return True
        app.cv2.imwrite.side_effect = write_image
        with tempfile.TemporaryDirectory() as directory:
            app.output_directory = Path(directory) / "captures"
            app.session_folder = None
            paths = [Path(app.save_capture(object(), i)) for i in range(3)]
            self.assertEqual({path.name for path in paths}, {"pair_1.png", "pair_2.png", "pair_3.png"})
            self.assertEqual(len({path.parent for path in paths}), 1)
            app.session_folder = None
            new_path = Path(app.save_capture(object(), 0))
            self.assertNotEqual(new_path.parent, paths[0].parent)
            self.assertTrue(all(path.exists() for path in paths))

    def test_image_write_failure_is_reported(self):
        app = DecoderGUI.__new__(DecoderGUI)
        app.cv2 = Mock()
        app.cv2.imwrite.return_value = False
        with tempfile.TemporaryDirectory() as directory:
            app.output_directory = Path(directory)
            app.session_folder = None
            with self.assertRaisesRegex(OSError, "Could not save"):
                app.save_capture(object(), 0)


if __name__ == "__main__":
    unittest.main()
