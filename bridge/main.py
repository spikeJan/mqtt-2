#!/usr/bin/env python3
"""PC桥接主程序 — 网口(TCP)→MQTT→SQLite + RTSP转码"""

import time
import logging
import yaml
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from network_reader import NetworkReader, SimulatedReader
from mqtt_publisher import MQTTPublisher
from db_writer import DBWriter
from rtsp_streamer import start_mjpeg_server, RTSPSnapshotGrabber

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger("bridge")


def load_config(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config_path = os.path.join(os.path.dirname(__file__), "config.yaml")
    config = load_config(config_path)

    # ── 1. 数据读取器: 模拟 或 真实网口 ──
    use_sim = os.environ.get("SIMULATE", "").lower() in ("1", "true", "yes")
    if use_sim:
        reader = SimulatedReader()
        logger.info("*** 使用模拟数据模式 ***")
    else:
        net_cfg = config["network"]
        reader = NetworkReader(net_cfg["host"], net_cfg["port"], net_cfg.get("timeout", 2))

    # ── 2. MQTT 发布器 ──
    mqtt_cfg = config["mqtt"]
    mqtt_pub = MQTTPublisher(mqtt_cfg["broker"], mqtt_cfg["port"])

    # ── 3. 数据库写入器 ──
    db_cfg = config["database"]
    db_path = os.path.join(os.path.dirname(__file__), db_cfg["path"])
    db_writer = DBWriter(db_path)

    # ── 4. HTTP静态文件服务 (总是启动,不依赖摄像头) ──
    cam_cfg = config.get("camera", {})
    rtsp_url = cam_cfg.get("rtsp_url", "")
    mjpeg_port = cam_cfg.get("mjpeg_port", 8080)
    rtsp_grabber = None

    dist_dir = os.path.join(os.path.dirname(__file__), "..", "dashboard", "dist")
    mjpeg_srv = start_mjpeg_server(host="0.0.0.0", port=mjpeg_port, dist_dir=os.path.abspath(dist_dir))

    if rtsp_url and not use_sim:
        rtsp_grabber = RTSPSnapshotGrabber(rtsp_url, fps=cam_cfg.get("fps", 8))
        rtsp_grabber.start()
    else:
        logger.info("RTSP未配置或模拟模式,跳过摄像头")

    # ── 5. 连接所有模块 ──
    if not reader.connect():
        logger.error("数据源连接失败,退出")
        return 1
    if not mqtt_pub.connect():
        logger.error("MQTT连接失败,退出")
        reader.disconnect()
        return 1
    if not db_writer.connect():
        logger.error("数据库连接失败,退出")
        reader.disconnect()
        mqtt_pub.disconnect()
        return 1

    logger.info("桥接程序已启动,等待数据...")

    # ── 6. 主循环 ──
    try:
        while True:
            frame = reader.read_frame()
            if frame is None:
                time.sleep(0.01)
                continue

            data_type = frame.get("type")
            if data_type in (0x01, 0x04):
                mqtt_pub.publish_sensor(frame)
                db_writer.insert_sensor(frame)
            elif data_type == 0x02:
                mqtt_pub.publish_alert(frame)
                db_writer.insert_alert(frame)
                logger.warning(f"告警: [{frame.get('level_str')}] {frame.get('message')}")
            elif data_type == 0x03:
                mqtt_pub.publish_image(frame)
                db_writer.insert_image_meta(frame)

    except KeyboardInterrupt:
        logger.info("桥接程序已停止")
    finally:
        reader.disconnect()
        mqtt_pub.disconnect()
        db_writer.disconnect()
        if rtsp_grabber:
            rtsp_grabber.stop()

    return 0


if __name__ == "__main__":
    sys.exit(main())
