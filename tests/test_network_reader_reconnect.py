import socket
import unittest
from unittest.mock import Mock, patch

from bridge.network_reader import NetworkReader


class Clock:
    def __init__(self, now=100.0):
        self.now = now

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_socket(*, connect_error=None, recv_effect=socket.timeout()):
    sock = Mock()
    if connect_error is not None:
        sock.connect.side_effect = connect_error
    if isinstance(recv_effect, BaseException):
        sock.recv.side_effect = recv_effect
    else:
        sock.recv.return_value = recv_effect
    return sock


class NetworkReaderReconnectTests(unittest.TestCase):
    def test_initial_connect_failure_is_retried_after_backoff(self):
        clock = Clock()
        failed = make_socket(connect_error=OSError("offline"))
        connected = make_socket()

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch("bridge.network_reader.socket.socket", side_effect=[failed, connected]) as factory,
        ):
            reader = NetworkReader("car.local", 1234)
            started = reader.connect()
            failed.close.assert_called_once()
            self.assertTrue(started)
            self.assertIsNone(reader.sock)

            clock.advance(reader.RECONNECT_INITIAL_DELAY - 0.1)
            self.assertIsNone(reader.read_frame())
            self.assertEqual(factory.call_count, 1)

            clock.advance(0.1)
            self.assertIsNone(reader.read_frame())
            self.assertIs(reader.sock, connected)
            self.assertEqual(factory.call_count, 2)

    def test_eof_closes_socket_and_schedules_reconnect(self):
        clock = Clock()
        disconnected = make_socket(recv_effect=b"")

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch("bridge.network_reader.socket.socket", return_value=disconnected) as factory,
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())

            self.assertIsNone(reader.read_frame())

            disconnected.close.assert_called_once()
            self.assertIsNone(reader.sock)
            self.assertGreater(reader._next_retry_at, clock.now)
            self.assertIsNone(reader.read_frame())
            self.assertEqual(factory.call_count, 1)

    def test_receive_exception_closes_socket_and_schedules_reconnect(self):
        clock = Clock()
        broken = make_socket(recv_effect=OSError("connection reset"))

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch("bridge.network_reader.socket.socket", return_value=broken),
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())

            self.assertIsNone(reader.read_frame())

            broken.close.assert_called_once()
            self.assertIsNone(reader.sock)
            self.assertGreater(reader._next_retry_at, clock.now)

    def test_successful_reconnect_resets_backoff(self):
        clock = Clock()
        first_failure = make_socket(connect_error=OSError("offline"))
        second_failure = make_socket(connect_error=OSError("still offline"))
        connected = make_socket()

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch(
                "bridge.network_reader.socket.socket",
                side_effect=[first_failure, second_failure, connected],
            ),
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())

            clock.advance(reader.RECONNECT_INITIAL_DELAY)
            self.assertIsNone(reader.read_frame())
            grown_delay = reader._retry_delay
            self.assertGreater(grown_delay, reader.RECONNECT_INITIAL_DELAY)

            clock.now = reader._next_retry_at
            self.assertIsNone(reader.read_frame())

            self.assertIs(reader.sock, connected)
            self.assertEqual(reader._retry_delay, reader.RECONNECT_INITIAL_DELAY)
            self.assertEqual(reader._next_retry_at, 0.0)

    def test_backoff_is_capped(self):
        clock = Clock()
        failed_sockets = [make_socket(connect_error=OSError("offline")) for _ in range(8)]

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch("bridge.network_reader.socket.socket", side_effect=failed_sockets),
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())

            for _ in range(7):
                clock.now = reader._next_retry_at
                self.assertIsNone(reader.read_frame())
                self.assertLessEqual(
                    reader._next_retry_at - clock.now,
                    reader.RECONNECT_MAX_DELAY,
                )

            self.assertEqual(reader._retry_delay, reader.RECONNECT_MAX_DELAY)

    def test_partial_buffer_is_cleared_when_connection_is_lost(self):
        clock = Clock()
        disconnected = make_socket(recv_effect=b"")
        reconnected = make_socket()

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch(
                "bridge.network_reader.socket.socket",
                side_effect=[disconnected, reconnected],
            ),
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())
            reader._buf = b"\xAA\x55\x01"

            self.assertIsNone(reader.read_frame())
            self.assertEqual(reader._buf, b"")

            clock.now = reader._next_retry_at
            self.assertIsNone(reader.read_frame())
            self.assertIs(reader.sock, reconnected)
            self.assertEqual(reader._buf, b"")

    def test_no_connect_attempt_before_retry_deadline(self):
        clock = Clock()
        failed = make_socket(connect_error=OSError("offline"))

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch("bridge.network_reader.socket.socket", return_value=failed) as factory,
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())

            for _ in range(5):
                self.assertIsNone(reader.read_frame())
            self.assertEqual(factory.call_count, 1)

            clock.now = reader._next_retry_at - 0.001
            self.assertIsNone(reader.read_frame())
            self.assertEqual(factory.call_count, 1)

    def test_reconnect_uses_a_new_socket_instance(self):
        clock = Clock()
        disconnected = make_socket(recv_effect=b"")
        reconnected = make_socket()

        with (
            patch("bridge.network_reader.time.monotonic", clock),
            patch(
                "bridge.network_reader.socket.socket",
                side_effect=[disconnected, reconnected],
            ) as factory,
        ):
            reader = NetworkReader("car.local", 1234)
            self.assertTrue(reader.connect())
            self.assertIsNone(reader.read_frame())

            clock.now = reader._next_retry_at
            self.assertIsNone(reader.read_frame())

            disconnected.close.assert_called_once()
            self.assertIs(reader.sock, reconnected)
            self.assertEqual(factory.call_count, 2)


if __name__ == "__main__":
    unittest.main()
