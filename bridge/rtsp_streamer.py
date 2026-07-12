"""RTSP拉流 → MJPEG HTTP服务 — 让手机浏览器能看摄像头画面, 同时提供静态网页"""

import threading
import logging
import os
import mimetypes
from http.server import HTTPServer, BaseHTTPRequestHandler

logger = logging.getLogger(__name__)

# 全局帧缓存
_latest_jpeg = None
_lock = threading.Lock()
_capture_running = False

# 静态文件目录
_DIST_DIR = None


def set_dist_dir(path):
    global _DIST_DIR
    _DIST_DIR = path


def set_frame(jpeg_bytes):
    global _latest_jpeg
    with _lock:
        _latest_jpeg = jpeg_bytes


def get_frame():
    with _lock:
        return _latest_jpeg


class MJPEGHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/camera/mjpeg':
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            try:
                while True:
                    frame = get_frame()
                    if frame:
                        self.wfile.write(b'--frame\r\n')
                        self.wfile.write(b'Content-Type: image/jpeg\r\n')
                        self.wfile.write(f'Content-Length: {len(frame)}\r\n\r\n'.encode())
                        self.wfile.write(frame)
                        self.wfile.write(b'\r\n')
                    else:
                        import time as _time
                        _time.sleep(0.05)
            except (BrokenPipeError, ConnectionResetError):
                pass
        elif self.path == '/camera/snapshot':
            frame = get_frame()
            if frame:
                self.send_response(200)
                self.send_header('Content-Type', 'image/jpeg')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(frame)
            else:
                self.send_response(204)
                self.end_headers()
        else:
            # 提供静态文件
            self._serve_static()

    def _serve_static(self):
        if not _DIST_DIR:
            self.send_response(404)
            self.end_headers()
            return

        path = self.path.lstrip('/')
        if path == '':
            path = 'index.html'

        file_path = os.path.join(_DIST_DIR, path)
        file_path = os.path.normpath(file_path)
        if not file_path.startswith(os.path.normpath(_DIST_DIR)):
            self.send_response(403)
            self.end_headers()
            return

        if not os.path.isfile(file_path):
            # SPA fallback: 非文件路径返回 index.html
            file_path = os.path.join(_DIST_DIR, 'index.html')

        try:
            with open(file_path, 'rb') as f:
                content = f.read()
            content_type, _ = mimetypes.guess_type(file_path)
            if content_type is None:
                content_type = 'application/octet-stream'

            self.send_response(200)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(content)))
            self.send_header('Cache-Control', 'no-cache')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(content)
        except Exception:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # 静默HTTP日志


def start_mjpeg_server(host='0.0.0.0', port=8080, dist_dir=None):
    """启动MJPEG HTTP服务器(后台线程), 可选提供静态文件"""
    if dist_dir:
        set_dist_dir(dist_dir)
    server = HTTPServer(('', port), MJPEGHandler)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    logger.info(f"MJPEG流服务已启动: http://{host}:{port}/camera/mjpeg")
    if dist_dir:
        logger.info(f"静态网页服务: http://{host}:{port}/")
    return server


class RTSPSnapshotGrabber:
    """使用FFmpeg从RTSP拉流,定时抓帧给MJPEG服务"""

    def __init__(self, rtsp_url, fps=8):
        self.rtsp_url = rtsp_url
        self.fps = fps
        self._running = False
        self._thread = None
        self._proc = None

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        logger.info(f"RTSP拉流已启动: {self.rtsp_url}")

    def stop(self):
        self._running = False
        if self._proc:
            try: self._proc.terminate()
            except Exception: pass
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self):
        import subprocess, time

        # FFmpeg: RTSP TCP拉流 → MJPEG输出到stdout
        cmd = [
            "ffmpeg",
            "-rtsp_transport", "tcp",
            "-i", self.rtsp_url,
            "-f", "image2pipe",
            "-vcodec", "mjpeg",
            "-q:v", "5",
            "-r", str(self.fps),
            "-an",
            "-loglevel", "error",
            "-"
        ]

        while self._running:
            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                break
            except FileNotFoundError:
                logger.error("FFmpeg 未安装,无法拉RTSP流. 请安装FFmpeg并添加到PATH")
                return
            except Exception as e:
                logger.warning(f"FFmpeg启动失败,3秒后重试: {e}")
                time.sleep(3)

        if not self._proc:
            return

        # 从FFmpeg stdout读取JPEG帧(jpeg帧以FF D8开头, FF D9结尾)
        buf = b''
        while self._running:
            try:
                chunk = self._proc.stdout.read(4096)
                if not chunk:
                    logger.warning("FFmpeg流结束,3秒后重试...")
                    self._proc.terminate()
                    time.sleep(3)
                    # 重新启动
                    try:
                        self._proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, bufsize=0)
                    except Exception:
                        self._running = False
                        break
                    buf = b''
                    continue
                buf += chunk
                # 提取完整的JPEG帧
                while True:
                    start = buf.find(b'\xFF\xD8')
                    end = buf.find(b'\xFF\xD9', start + 2)
                    if start >= 0 and end > start:
                        jpeg = buf[start:end + 2]
                        set_frame(jpeg)
                        buf = buf[end + 2:]
                    else:
                        if start >= 0 and end < 0 and len(buf) > 1024 * 1024:
                            # 避免单帧过大导致缓冲区爆炸
                            buf = buf[-65536:]
                        break
            except Exception:
                time.sleep(0.1)

        if self._proc:
            try: self._proc.terminate()
            except Exception: pass
        logger.info("RTSP拉流已停止")
