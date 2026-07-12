#!/usr/bin/env python3
"""
管道探测小车 - 一体化启动器
启动 MQTT Broker (含原生WebSocket) + HTTP静态服务 + 数据桥接
双击 .exe 即可运行，无需安装任何环境
"""

import os, sys, time, json, socket, threading, subprocess, webbrowser, sqlite3, datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# ── 调试日志 ──
LOG_FILE = Path(os.getcwd()) / "launcher_debug.log"

def log(msg):
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

# ── 配置 ──
MQTT_PORT = 1884
WS_PORT = 9001
HTTP_PORT = 8080

BASE_DIR = Path(sys._MEIPASS if getattr(sys, 'frozen', False) else os.path.dirname(os.path.abspath(__file__)))
DIST_DIR = BASE_DIR / "dashboard" / "dist"
MOSQUITTO_EXE = BASE_DIR / "mosquitto" / "mosquitto.exe"
MOSQUITTO_CONF = BASE_DIR / "mosquitto" / "mosquitto_portable.conf"
SCHEMA_PATH = BASE_DIR / "database" / "schema.sql"
DB_PATH = BASE_DIR / "database" / "car_data.db"

mosquitto_proc = None


def kill_port(port):
    """杀掉占用指定端口的进程 (Windows)"""
    if sys.platform != "win32":
        return
    try:
        r = subprocess.run(
            f'netstat -ano | findstr :{port}', shell=True,
            capture_output=True, text=True, timeout=5
        )
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

    mosquitto_dir = str(MOSQUITTO_EXE.parent)
    try:
        mosquitto_proc = subprocess.Popen(
            [str(MOSQUITTO_EXE), "-c", str(MOSQUITTO_CONF)],
            cwd=mosquitto_dir,
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
    """初始化 SQLite 数据库"""
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


# ── HTTP 静态文件服务 ──
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
    log(f"仪表盘: http://0.0.0.0:{HTTP_PORT}")
    server.serve_forever()


# ── 数据桥接 (模拟模式) ──
def start_sensor_bridge():
    import paho.mqtt.client as mqtt

    mqttc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    for i in range(30):
        try:
            mqttc.connect("127.0.0.1", MQTT_PORT)
            break
        except Exception:
            if i == 0:
                log("Bridge 等待 MQTT Broker 就绪...")
            time.sleep(1)
    else:
        log("Bridge MQTT 连接失败, 跳过数据桥接")
        return

    mqttc.loop_start()

    try:
        db_conn = sqlite3.connect(str(DB_PATH))
    except Exception as e:
        log(f"Bridge 数据库连接失败: {e}")
        db_conn = None

    import random, math
    seq, t = 0, 0.0
    log("数据桥接已启动 (模拟模式)")

    while True:
        t += 0.1
        seq = (seq + 1) & 0xFF

        now = time.time()
        data = {
            "timestamp": now,
            "roll": round(math.sin(t * 0.5) * 15, 2),
            "pitch": round(math.cos(t * 0.3) * 10, 2),
            "yaw": round((t * 30) % 360, 2),
            "speed": random.randint(0, 80),
            "servo1": random.randint(0, 180),
            "co": random.randint(0, 50),
            "co2": random.randint(300, 800),
        }

        mqttc.publish("car/sensors/all", json.dumps(data))
        for k, v in data.items():
            if k != "timestamp":
                mqttc.publish(f"car/sensors/{k}", str(v))

        # 云台角度 (双轴)
        gimbal_data = {"horizontal": data["servo1"], "vertical": data["servo1"] // 2}
        mqttc.publish("car/sensors/gimbal", json.dumps(gimbal_data))

        if db_conn and seq % 10 == 0:
            try:
                db_conn.execute(
                    "INSERT INTO sensor_readings (timestamp,roll,pitch,yaw,speed,servo1,co,co2) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (now, data["roll"], data["pitch"], data["yaw"],
                     data["speed"], data["servo1"], data["co"], data["co2"])
                )
                if seq % 100 == 0:
                    db_conn.commit()
            except Exception:
                pass

        time.sleep(0.1)


# ── 主函数 ──
def main():
    log("=" * 50)
    log("管道探测小车 - 一体化数据展板")
    log("=" * 50)

    log(f"运行模式: {'exe打包' if getattr(sys, 'frozen', False) else 'Python源码'}")
    log(f"基础目录: {BASE_DIR}")

    # 0. 清理残留端口
    kill_port(MQTT_PORT)
    kill_port(WS_PORT)
    kill_port(HTTP_PORT)

    # 1. 初始化数据库
    init_database()

    # 2. MQTT Broker (自带 WebSocket, 端口9001)
    if not start_mqtt_broker():
        log("ERROR: MQTT Broker 启动失败")
        sys.exit(1)
    time.sleep(2)

    # 3. 数据桥接 (后台线程)
    threading.Thread(target=start_sensor_bridge, daemon=True).start()

    # 4. HTTP 服务器 (后台线程)
    threading.Thread(target=start_http_server, daemon=True).start()
    time.sleep(1)

    log("")
    log("=" * 50)
    log(f"仪表盘: http://localhost:{HTTP_PORT}")
    try:
        local_ip = socket.gethostbyname(socket.gethostname())
        log(f"手机访问: http://{local_ip}:{HTTP_PORT}")
    except Exception:
        pass
    log("=" * 50)
    log("按 Ctrl+C 停止所有服务")
    log("")

    webbrowser.open(f"http://localhost:{HTTP_PORT}")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        log("正在停止...")
    finally:
        stop_mqtt_broker()


if __name__ == "__main__":
    main()
