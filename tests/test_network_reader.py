import socket
import struct
import unittest

from bridge.network_reader import NetworkReader


DEFAULT_VALUES = {
    "roll": 1.25,
    "pitch": -2.5,
    "yaw": 123.75,
    "speed": 31,
    "servo1": 120,
    "servo2": 17,
    "co": 88,
    "co2": 999,
}


def build_0x04_frame(*, seq=42, tail=b"\x0D\x0A", bad_checksum=False, **overrides):
    values = {**DEFAULT_VALUES, **overrides}
    payload = struct.pack(
        "<fffHHHHH",
        values["roll"],
        values["pitch"],
        values["yaw"],
        values["speed"],
        values["servo1"],
        values["servo2"],
        values["co"],
        values["co2"],
    )
    prefix = b"\xAA\x55" + bytes((seq, 0x04)) + payload
    checksum = sum(prefix[2:]) & 0xFF
    if bad_checksum:
        checksum = (checksum + 1) & 0xFF
    return prefix + bytes((checksum,)) + tail


class FakeSocket:
    def __init__(self, *chunks):
        self._chunks = list(chunks)

    def recv(self, _size):
        if self._chunks:
            return self._chunks.pop(0)
        raise socket.timeout

    def close(self):
        pass


class NetworkReader0x04Tests(unittest.TestCase):
    def make_reader(self, *chunks):
        reader = NetworkReader("memory", 0)
        reader.sock = FakeSocket(*chunks)
        return reader

    def assert_frame_values(self, result, *, seq=42, **overrides):
        expected = {**DEFAULT_VALUES, **overrides}
        self.assertIsNotNone(result)
        self.assertEqual(result["type"], 0x04)
        self.assertEqual(result["seq"], seq)
        for key in ("roll", "pitch", "yaw"):
            self.assertAlmostEqual(result[key], expected[key], places=2)
        for key in ("speed", "servo1", "servo2", "co", "co2"):
            self.assertEqual(result[key], expected[key])

    def test_valid_0x04_frame_consumes_all_29_bytes(self):
        reader = self.make_reader(build_0x04_frame())

        result = reader.read_frame()

        self.assert_frame_values(result)
        self.assertEqual(reader._buf, b"")

    def test_invalid_0x04_tail_is_rejected(self):
        reader = self.make_reader(build_0x04_frame(tail=b"\xDE\xAD"))

        result = reader.read_frame()

        self.assertIsNone(result)

    def test_fragmented_0x04_frame_waits_for_tail(self):
        frame = build_0x04_frame()
        reader = self.make_reader(
            frame[:5],
            frame[5:20],
            frame[20:28],
            frame[28:],
        )

        self.assertIsNone(reader.read_frame())
        self.assertIsNone(reader.read_frame())
        self.assertIsNone(reader.read_frame())
        result = reader.read_frame()

        self.assert_frame_values(result)
        self.assertEqual(reader._buf, b"")

    def test_two_concatenated_0x04_frames_are_parsed_separately(self):
        first = build_0x04_frame(seq=42)
        second = build_0x04_frame(seq=43, speed=32, servo2=18)
        reader = self.make_reader(first + second)

        first_result = reader.read_frame()
        second_result = reader.read_frame()

        self.assert_frame_values(first_result, seq=42)
        self.assert_frame_values(second_result, seq=43, speed=32, servo2=18)
        self.assertEqual(reader._buf, b"")

    def test_noise_before_valid_0x04_frame_is_skipped(self):
        reader = self.make_reader(b"\x00\xFFnoise" + build_0x04_frame())

        result = reader.read_frame()

        self.assert_frame_values(result)
        self.assertEqual(reader._buf, b"")

    def test_bad_tail_followed_by_valid_frame_recovers(self):
        bad = build_0x04_frame(seq=41, tail=b"\xDE\xAD")
        valid = build_0x04_frame(seq=42)
        reader = self.make_reader(bad + valid)

        result = reader.read_frame()

        self.assert_frame_values(result, seq=42)
        self.assertEqual(reader._buf, b"")

    def test_bad_checksum_followed_by_valid_frame_recovers(self):
        bad = build_0x04_frame(seq=41, bad_checksum=True)
        valid = build_0x04_frame(seq=42)
        reader = self.make_reader(bad + valid)

        result = reader.read_frame()

        self.assert_frame_values(result, seq=42)
        self.assertEqual(reader._buf, b"")

    def test_legacy_27_byte_frame_is_not_accepted_in_strict_29_mode(self):
        # This PR follows the competition's strict 29-byte format. The test
        # fixes that boundary only; it does not permanently deprecate 27-byte frames.
        legacy = build_0x04_frame(seq=41, speed=30, servo2=16)[:-2]
        valid = build_0x04_frame(
            seq=42,
            roll=2.75,
            pitch=-3.5,
            yaw=45.25,
            speed=32,
            servo1=121,
            servo2=18,
            co=89,
            co2=1000,
        )
        reader = self.make_reader(legacy + valid)

        result = reader.read_frame()

        self.assert_frame_values(
            result,
            seq=42,
            roll=2.75,
            pitch=-3.5,
            yaw=45.25,
            speed=32,
            servo1=121,
            servo2=18,
            co=89,
            co2=1000,
        )
        self.assertEqual(reader._buf, b"")


if __name__ == "__main__":
    unittest.main()
