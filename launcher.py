#!/usr/bin/env python3
"""
管道探测小车 - 一体化启动器
双击运行: MQTT Broker + HTTP仪表盘 + TCP数据桥接
"""
import os, sys, time, json, socket, struct, threading, subprocess, webbrowser, sqlite3, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

LOG_FILE = Path(os.getcwd()) / "launcher_debug.log"

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── 配置 ──
MQTT_PORT = 1884
WS_PORT   = 9001
HTTP_PORT = 8080
CAR_HOST  = "192.168.0.233"
CAR_PORT  = 1234

BASE_DIR       = Path(sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))
DIST_DIR       = BASE_DIR / "dashboard" / "dist"
MOSQUITTO_EXE  = BASE_DIR / "mosquitto" / "mosquitto.exe"
MOSQUITTO_CONF = BASE_DIR / "mosquitto" / "mosquitto_portable.conf"
DB_PATH        = BASE_DIR / "database" / "car_data.db"

mosquitto_proc = None
bridge_connected = False
stop_flag = threading.Event()

# ══════════════════════ 服务函数 ══════════════════════

def kill_port(port):
    if sys.platform != "win32":
        return
    try:
        r = subprocess.run(f'netstat -ano | findstr :{port}', shell=True,
                           capture_output=True, text=True, timeout=5)
        pids = set()
        for line in r.stdout.strip().split("\n"):
            parts = line.split()
            if len(parts) >= 5 and "LISTENING" in line:
                pid = parts[-1]
                if pid != "0":
                    pids.add(pid)
        for pid in pids:
            subprocess.run(f"taskkill /F /PID {pid}", shell=True,
                           capture_output=True, timeout=5)
            log(f"已结束占用端口{port}的进程 PID:{pid}")
    except Exception as e:
        log(f"端口{port}清理异常: {e}")


def start_mqtt_broker():
    global mosquitto_proc
    if not MOSQUITTO_EXE.exists():
        log(f"未找到 mosquitto.exe: {MOSQUITTO_EXE}")
        return False
    try:
        mosquitto_proc = subprocess.Popen(
            [str(MOSQUITTO_EXE), "-c", str(MOSQUITTO_CONF)],
            cwd=str(MOSQUITTO_EXE.parent),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
        )
        log(f"Mosquitto 已启动 (PID {mosquitto_proc.pid})")
        return True
    except Exception as e:
        log(f"Mosquitto 启动失败: {e}")
        return False


def stop_mqtt_broker():
    global mosquitto_proc
    if mosquitto_proc:
        try:
            mosquitto_proc.terminate()
            mosquitto_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            mosquitto_proc.kill()
        except Exception:
            pass
        log("Mosquitto 已停止")
        mosquitto_proc = None


def init_database():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS sensor_readings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            roll REAL, pitch REAL, yaw REAL,
            speed INTEGER, servo1 INTEGER,
            co INTEGER, co2 INTEGER
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            level INTEGER, message TEXT
        )
    """)
    conn.commit()
    conn.close()
    log(f"数据库就绪: {DB_PATH}")


class StaticHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIST_DIR), **kwargs)
    def log_message(self, format, *args):
        pass


def start_http_server():
    if not DIST_DIR.exists():
        log(f"前端文件不存在: {DIST_DIR}")
        return
    server = HTTPServer(("0.0.0.0", HTTP_PORT), StaticHandler)
    log(f"HTTP 仪表盘: http://0.0.0.0:{HTTP_PORT}")
    server.serve_forever()


# ══════════════════════ 数据桥接 ══════════════════════

def run_bridge(status_callback=None):
    """TCP连接小车, 解析29字节二进制帧, 发布到MQTT, 写入SQLite"""
    global bridge_connected
    import paho.mqtt.client as mqtt

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    for i in range(30):
        try:
            mqttc.connect("127.0.0.1", MQTT_PORT)
            break
        except Exception:
            if i == 0:
                log("Bridge 等待 MQTT Broker...")
            time.sleep(1)
    else:
        log("Bridge MQTT 连接失败")
        return

    mqttc.loop_start()
    try:
        db_conn = sqlite3.connect(str(DB_PATH))
    except Exception:
        db_conn = None

    # ── 连接小车 ──
    sock = None
    for attempt in range(10):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            sock.connect((CAR_HOST, CAR_PORT))
            log(f"已连接小车 {CAR_HOST}:{CAR_PORT}")
            bridge_connected = True
            if status_callback:
                status_callback("connected")
            break
        except Exception as e:
            log(f"连接小车重试 {attempt + 1}/10: {e}")
            try:
                sock.close()
            except Exception:
                pass
            sock = None
            time.sleep(2)

    if sock is None:
        log("无法连接小车，桥接线程退出")
        if status_callback:
            status_callback("no_car")
        return

    buf = b""
    while not stop_flag.is_set():
        try:
            data = sock.recv(4096)
            if not data:
                log("小车连接断开，尝试重连...")
                bridge_connected = False
                if status_callback:
                    status_callback("disconnected")
                break
            buf += data
        except socket.timeout:
            continue
        except Exception as e:
            log(f"TCP读取异常: {e}")
            bridge_connected = False
            if status_callback:
                status_callback("disconnected")
            break

        # 帧格式(29字节): AA55 | seq | 0x04 | roll(4) pitch(4) yaw(4) |
        #   speed(2) servo1(2) servo2(2) co(2) co2(2) | checksum | 0D0A
        while len(buf) >= 29:
            idx = buf.find(b'\xAA\x55')
            if idx < 0:
                buf = buf[-1:]
                break
            if idx > 0:
                buf = buf[idx:]
            if len(buf) < 29:
                break
            if buf[3] != 0x04 or buf[27] != 0x0D or buf[28] != 0x0A:
                buf = buf[1:]
                continue
            if (sum(buf[2:26]) & 0xFF) != buf[26]:
                buf = buf[1:]
                continue

            try:
                roll, pitch, yaw, speed, servo1, servo2, co, co2 = \
                    struct.unpack_from("<fffHHHHH", buf, 4)
            except struct.error:
                buf = buf[1:]
                continue

            now = time.time()
            data = {
                "timestamp": round(now, 2),
                "roll": round(roll, 2), "pitch": round(pitch, 2), "yaw": round(yaw, 2),
                "speed": speed, "servo1": servo1,
                "co": co, "co2": co2,
            }
            mqttc.publish("car/sensors/all", json.dumps(data))
            for k, v in data.items():
                if k != "timestamp":
                    mqttc.publish(f"car/sensors/{k}", str(v))
            gimbal = {"horizontal": servo1, "vertical": servo1 // 2}
            mqttc.publish("car/sensors/gimbal", json.dumps(gimbal))

            try:
                db_conn.execute(
                    "INSERT INTO sensor_readings (timestamp,roll,pitch,yaw,speed,servo1,co,co2) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (now, roll, pitch, yaw, speed, servo1, co, co2))
                db_conn.commit()
            except Exception:
                pass
            buf = buf[29:]

    try:
        sock.close()
    except Exception:
        pass


# ══════════════════════ GUI ══════════════════════

def create_info_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("PipeCar Dashboard")
    root.geometry("440x330")
    root.resizable(False, False)
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 440) // 2
    y = (root.winfo_screenheight() - 330) // 2
    root.geometry(f"+{x}+{y}")

    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(main_frame, text="管道探测小车 - 数据展板",
              font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(0, 15))

    # ── 访问地址 ──
    url_frame = ttk.LabelFrame(main_frame, text="访问地址", padding=10)
    url_frame.pack(fill="x", pady=(0, 10))

    ttk.Label(url_frame, text="本机访问:",
              font=("Consolas", 10)).grid(row=0, column=0, sticky="w")
    ttk.Label(url_frame, text=f"http://localhost:{HTTP_PORT}",
              font=("Consolas", 10, "bold"), foreground="#2563eb").grid(
        row=0, column=1, sticky="w", padx=(10, 0))

    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        ip_text = f"http://{local_ip}:{HTTP_PORT}"
    except Exception:
        ip_text = "无法获取"

    ttk.Label(url_frame, text="手机/平板:",
              font=("Consolas", 10)).grid(row=1, column=0, sticky="w", pady=(5, 0))
    ttk.Label(url_frame, text=ip_text,
              font=("Consolas", 10, "bold"), foreground="#2563eb").grid(
        row=1, column=1, sticky="w", padx=(10, 0), pady=(5, 0))

    ttk.Label(url_frame, text="查看本机IP: 命令行输入 ipconfig",
              font=("Microsoft YaHei UI", 8), foreground="#666").grid(
        row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

    # ── 服务状态 ──
    status_frame = ttk.LabelFrame(main_frame, text="服务状态", padding=10)
    status_frame.pack(fill="x", pady=(0, 10))

    mqtt_label = ttk.Label(status_frame, text="● MQTT Broker 已启动",
                           font=("Microsoft YaHei UI", 9), foreground="#16a34a")
    mqtt_label.pack(anchor="w")

    http_label = ttk.Label(status_frame, text="● HTTP 仪表盘 已启动",
                           font=("Microsoft YaHei UI", 9), foreground="#16a34a")
    http_label.pack(anchor="w", pady=(2, 0))

    bridge_label = ttk.Label(status_frame, text="◌ 正在连接小车...",
                             font=("Microsoft YaHei UI", 9), foreground="#d97706")
    bridge_label.pack(anchor="w", pady=(2, 0))

    def update_bridge_status(state):
        if state == "connected":
            bridge_label.configure(text=f"● TCP 小车已连接 ({CAR_HOST}:{CAR_PORT})",
                                   foreground="#16a34a")
        elif state == "no_car":
            bridge_label.configure(text="✕ 小车未连接，仪表盘无数据",
                                   foreground="#dc2626")
        elif state == "disconnected":
            bridge_label.configure(text="✕ 小车连接断开，仪表盘无数据",
                                   foreground="#dc2626")

    # ── 按钮 ──
    btn_frame = ttk.Frame(main_frame)
    btn_frame.pack(fill="x", pady=(5, 0))

    def open_browser():
        webbrowser.open(f"http://localhost:{HTTP_PORT}")

    def stop_all():
        log("用户点击停止")
        stop_flag.set()
        stop_mqtt_broker()
        root.destroy()

    ttk.Button(btn_frame, text="打开仪表盘", command=open_browser).pack(side="left")
    ttk.Button(btn_frame, text="停止服务", command=stop_all).pack(side="right")

    root.protocol("WM_DELETE_WINDOW", stop_all)

    # 启动桥接（后台线程），通过回调更新状态
    threading.Thread(target=run_bridge, args=(update_bridge_status,), daemon=True).start()

    # 启动后自动弹出浏览器
    root.after(500, open_browser)

    root.mainloop()


# ══════════════════════ 主入口 ══════════════════════

def main():
    log("=" * 50)
    log("管道探测小车 - 一体化数据展板")
    log("=" * 50)

    kill_port(MQTT_PORT)
    kill_port(WS_PORT)
    kill_port(HTTP_PORT)

    init_database()

    if not start_mqtt_broker():
        log("ERROR: MQTT Broker 启动失败")
        sys.exit(1)
    time.sleep(2)

    threading.Thread(target=start_http_server, daemon=True).start()
    time.sleep(1)

    log("服务就绪，显示窗口")
    create_info_window()
    stop_flag.set()
    stop_mqtt_broker()


if __name__ == "__main__":
    main()
