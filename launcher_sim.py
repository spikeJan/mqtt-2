#!/usr/bin/env python3
"""
管道探测小车 - 模拟模式启动器
双击运行: MQTT Broker + HTTP仪表盘 + 模拟数据生成
"""
import os, sys, time, json, socket, threading, subprocess, webbrowser, sqlite3, datetime, random, math
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

MQTT_PORT = 1884
WS_PORT   = 9001
HTTP_PORT = 8080

BASE_DIR       = Path(sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))
DIST_DIR       = BASE_DIR / "dashboard" / "dist"
MOSQUITTO_EXE  = BASE_DIR / "mosquitto" / "mosquitto.exe"
MOSQUITTO_CONF = BASE_DIR / "mosquitto" / "mosquitto_portable.conf"
DB_PATH        = BASE_DIR / "database" / "car_data.db"

mosquitto_proc = None
stop_flag = threading.Event()


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


def run_bridge_sim():
    """模拟模式: 生成随机传感器数据发布到MQTT"""
    import paho.mqtt.client as mqtt
    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    for i in range(30):
        try:
            mqttc.connect("127.0.0.1", MQTT_PORT)
            break
        except Exception:
            if i == 0:
                log("等待 MQTT Broker...")
            time.sleep(1)
    else:
        log("MQTT 连接失败")
        return

    mqttc.loop_start()
    try:
        db_conn = sqlite3.connect(str(DB_PATH))
    except Exception:
        db_conn = None

    log("模拟数据生成已启动")
    seq, t = 0, 0.0

    while not stop_flag.is_set():
        t += 0.1
        seq = (seq + 1) & 0xFF
        now = time.time()
        data = {
            "timestamp": round(now, 2),
            "roll":  round(math.sin(t * 0.5) * 15, 2),
            "pitch": round(math.cos(t * 0.3) * 10, 2),
            "yaw":   round((t * 30) % 360, 2),
            "speed": random.randint(0, 80),
            "servo1": random.randint(0, 180),
            "co":    random.randint(0, 50),
            "co2":   random.randint(300, 800),
        }
        mqttc.publish("car/sensors/all", json.dumps(data))
        for k, v in data.items():
            if k != "timestamp":
                mqttc.publish(f"car/sensors/{k}", str(v))
        gimbal = {"horizontal": data["servo1"], "vertical": data["servo1"] // 2}
        mqttc.publish("car/sensors/gimbal", json.dumps(gimbal))

        if seq % 10 == 0:
            try:
                db_conn.execute(
                    "INSERT INTO sensor_readings (timestamp,roll,pitch,yaw,speed,servo1,co,co2) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (now, data["roll"], data["pitch"], data["yaw"],
                     data["speed"], data["servo1"], data["co"], data["co2"]))
                if seq % 100 == 0:
                    db_conn.commit()
            except Exception:
                pass
        time.sleep(0.1)


def create_info_window():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("PipeCar Dashboard - 模拟模式")
    root.geometry("440x310")
    root.resizable(False, False)
    root.update_idletasks()
    x = (root.winfo_screenwidth() - 440) // 2
    y = (root.winfo_screenheight() - 310) // 2
    root.geometry(f"+{x}+{y}")

    main_frame = ttk.Frame(root, padding=20)
    main_frame.pack(fill="both", expand=True)

    ttk.Label(main_frame, text="管道探测小车 - 模拟数据展板",
              font=("Microsoft YaHei UI", 14, "bold")).pack(pady=(0, 8))

    ttk.Label(main_frame, text="使用随机生成的模拟传感器数据，无需连接小车",
              font=("Microsoft YaHei UI", 9), foreground="#666").pack(pady=(0, 12))

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

    status_frame = ttk.LabelFrame(main_frame, text="服务状态", padding=10)
    status_frame.pack(fill="x", pady=(0, 10))

    ttk.Label(status_frame, text="● MQTT Broker 已启动",
              font=("Microsoft YaHei UI", 9), foreground="#16a34a").pack(anchor="w")
    ttk.Label(status_frame, text="● HTTP 仪表盘 已启动",
              font=("Microsoft YaHei UI", 9), foreground="#16a34a").pack(anchor="w", pady=(2, 0))
    ttk.Label(status_frame, text="● 模拟数据生成中 (10Hz)",
              font=("Microsoft YaHei UI", 9), foreground="#16a34a").pack(anchor="w", pady=(2, 0))

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
    root.after(500, open_browser)
    root.mainloop()


def main():
    log("=" * 50)
    log("管道探测小车 - 模拟模式")
    log("=" * 50)

    kill_port(MQTT_PORT)
    kill_port(WS_PORT)
    kill_port(HTTP_PORT)

    init_database()

    if not start_mqtt_broker():
        log("ERROR: MQTT Broker 启动失败")
        sys.exit(1)
    time.sleep(2)

    threading.Thread(target=run_bridge_sim, daemon=True).start()
    threading.Thread(target=start_http_server, daemon=True).start()
    time.sleep(1)

    log("模拟模式就绪")
    create_info_window()
    stop_flag.set()
    stop_mqtt_broker()


if __name__ == "__main__":
    main()
