import contextlib
import http.client
import socket
import socketserver
import tempfile
import threading
import time
import unittest
from http.server import HTTPServer as StandardHTTPServer
from http.server import ThreadingHTTPServer as StandardThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

from bridge import rtsp_streamer


JPEG = b"\xff\xd8test-frame\xff\xd9"


class RTSPStreamerHTTPTests(unittest.TestCase):
    def setUp(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self._temp_dir.name)
        self.dist = self.root / "dist"
        self.dist_evil = self.root / "dist_evil"
        (self.dist / "assets").mkdir(parents=True)
        self.dist_evil.mkdir()
        (self.dist / "index.html").write_bytes(b"INDEX")
        (self.dist / "assets" / "app.js").write_bytes(b"APP")
        (self.dist_evil / "secret.txt").write_bytes(b"SECRET")
        (self.root / "outside.txt").write_bytes(b"OUTSIDE")

    def tearDown(self):
        rtsp_streamer.set_frame(None)
        rtsp_streamer.set_dist_dir(None)
        self._temp_dir.cleanup()

    @contextlib.contextmanager
    def _running_server(self):
        baseline_threads = {thread.ident for thread in threading.enumerate()}

        def make_single_server(address, handler):
            return StandardHTTPServer(("127.0.0.1", address[1]), handler)

        def make_threaded_server(address, handler):
            server = StandardThreadingHTTPServer(("127.0.0.1", address[1]), handler)
            server.daemon_threads = True
            return server

        with (
            patch.object(
                rtsp_streamer,
                "HTTPServer",
                side_effect=make_single_server,
                create=True,
            ),
            patch.object(
                rtsp_streamer,
                "ThreadingHTTPServer",
                side_effect=make_threaded_server,
                create=True,
            ),
        ):
            server = rtsp_streamer.start_mjpeg_server(
                host="127.0.0.1",
                port=0,
                dist_dir=str(self.dist),
            )

        try:
            yield server
        finally:
            server.shutdown()
            server.server_close()
            deadline = time.monotonic() + 2.0
            while time.monotonic() < deadline:
                remaining = [
                    thread
                    for thread in threading.enumerate()
                    if thread.ident not in baseline_threads and thread.is_alive()
                ]
                if not remaining:
                    break
                time.sleep(0.01)
            self.assertFalse(
                remaining,
                f"HTTP test threads did not exit: {[thread.name for thread in remaining]}",
            )

    def _request(self, server, path, timeout=1.0):
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=timeout,
        )
        try:
            connection.request("GET", path)
            response = connection.getresponse()
            return response.status, response.read()
        finally:
            connection.close()

    def _open_controlled_mjpeg(self, server):
        entered = threading.Event()
        release = threading.Event()

        def controlled_frame():
            if not entered.is_set():
                entered.set()
                release.wait(timeout=2.0)
                raise ConnectionResetError("controlled MJPEG client closed")
            return JPEG

        frame_patch = patch.object(rtsp_streamer, "get_frame", side_effect=controlled_frame)
        frame_patch.start()
        connection = http.client.HTTPConnection(
            "127.0.0.1",
            server.server_address[1],
            timeout=1.0,
        )
        try:
            connection.request("GET", "/camera/mjpeg")
            response = connection.getresponse()
            self.assertEqual(response.status, 200)
            self.assertTrue(entered.wait(timeout=1.0), "MJPEG handler did not enter its stream loop")
        except Exception:
            release.set()
            connection.close()
            frame_patch.stop()
            raise
        return connection, response, entered, release, frame_patch

    def _assert_responsive_while_mjpeg_open(self, path, expected_body):
        with self._running_server() as server:
            connection, response, _, release, frame_patch = self._open_controlled_mjpeg(server)
            try:
                try:
                    status, body = self._request(server, path, timeout=0.5)
                except (TimeoutError, socket.timeout, OSError) as exc:
                    self.fail(f"request {path} was blocked by the MJPEG client: {exc}")
                self.assertEqual(status, 200)
                self.assertEqual(body, expected_body)
            finally:
                release.set()
                response.close()
                connection.close()
                frame_patch.stop()

    def test_http_server_uses_threaded_request_handling(self):
        with self._running_server() as server:
            self.assertIsInstance(server, socketserver.ThreadingMixIn)
            self.assertTrue(server.daemon_threads)

    def test_snapshot_remains_responsive_while_mjpeg_client_is_connected(self):
        self._assert_responsive_while_mjpeg_open("/camera/snapshot", JPEG)

    def test_static_file_remains_responsive_while_mjpeg_client_is_connected(self):
        self._assert_responsive_while_mjpeg_open("/index.html", b"INDEX")

    def test_normal_static_file_inside_dist_is_served(self):
        with self._running_server() as server:
            status, body = self._request(server, "/index.html")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"INDEX")

    def test_parent_traversal_outside_dist_is_rejected(self):
        with self._running_server() as server:
            status, body = self._request(server, "/../outside.txt")
        self.assertIn(status, (403, 404))
        self.assertNotIn(b"OUTSIDE", body)

    def test_percent_encoded_parent_traversal_is_rejected(self):
        with self._running_server() as server:
            status, body = self._request(
                server,
                "/%2E%2E%5Cdist_evil%5Csecret.txt",
            )
        self.assertIn(status, (403, 404))
        self.assertNotIn(b"SECRET", body)

    def test_same_prefix_sibling_directory_is_rejected(self):
        with self._running_server() as server:
            status, body = self._request(server, "/../dist_evil/secret.txt")
        self.assertIn(status, (403, 404))
        self.assertNotIn(b"SECRET", body)

    def test_nested_file_inside_dist_is_allowed(self):
        with self._running_server() as server:
            status, body = self._request(server, "/assets/app.js")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"APP")

    def test_static_file_query_string_is_ignored_for_path_resolution(self):
        with self._running_server() as server:
            status, body = self._request(server, "/assets/app.js?cache=1")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"APP")

    def test_spa_fallback_does_not_escape_dist(self):
        with self._running_server() as server:
            route_status, route_body = self._request(server, "/client/route")
            escape_status, escape_body = self._request(
                server,
                "/../dist_evil/missing-route",
            )
        self.assertEqual(route_status, 200)
        self.assertEqual(route_body, b"INDEX")
        self.assertIn(escape_status, (403, 404))
        self.assertNotIn(b"SECRET", escape_body)


if __name__ == "__main__":
    unittest.main()
