"""数据库写入模块"""

import sqlite3
import logging
import os

logger = logging.getLogger(__name__)

SCHEMA_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "schema.sql")


class DBWriter:
    def __init__(self, db_path="car_data.db"):
        self.db_path = db_path
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        logger.info(f"数据库 {self.db_path} 已连接")
        return True

    def _init_schema(self):
        if os.path.exists(SCHEMA_PATH):
            with open(SCHEMA_PATH, "r", encoding="utf-8") as f:
                self.conn.executescript(f.read())
            self.conn.commit()

    def disconnect(self):
        if self.conn:
            self.conn.close()

    def insert_sensor(self, data):
        self.conn.execute(
            """INSERT INTO sensor_readings
               (timestamp, roll, pitch, yaw, speed, servo1, co, co2)
               VALUES (datetime(?, 'unixepoch'), ?, ?, ?, ?, ?, ?, ?)""",
            (
                data.get("timestamp"),
                data.get("roll"),
                data.get("pitch"),
                data.get("yaw"),
                data.get("speed"),
                data.get("servo1"),
                data.get("co"),
                data.get("co2"),
            ),
        )
        self.conn.commit()

    def insert_alert(self, data):
        self.conn.execute(
            "INSERT INTO alerts (timestamp, level, message) VALUES (datetime(?, 'unixepoch'), ?, ?)",
            (data.get("timestamp"), data.get("level_str", "info"), data.get("message", "")),
        )
        self.conn.commit()

    def insert_image_meta(self, data):
        self.conn.execute(
            "INSERT INTO images (timestamp, filename, pipe_section, defect_detected) VALUES (datetime(?, 'unixepoch'), ?, ?, ?)",
            (data.get("timestamp"), data.get("filename", ""), data.get("pipe_section", ""),
             data.get("defect_detected", 0)),
        )
        self.conn.commit()
