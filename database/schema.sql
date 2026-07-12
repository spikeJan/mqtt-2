-- 管道探测小车数据记录系统

CREATE TABLE IF NOT EXISTS sensor_readings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    roll REAL,              -- 翻滚角
    pitch REAL,             -- 俯仰角
    yaw REAL,               -- 偏航角
    speed INTEGER,          -- 速度 0-80
    servo1 INTEGER,         -- 舵机1角度 0-180
    co INTEGER,             -- 一氧化碳 ppm
    co2 INTEGER             -- 二氧化碳 ppm
);
CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_readings(timestamp);

CREATE TABLE IF NOT EXISTS alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    level TEXT NOT NULL,
    message TEXT NOT NULL,
    acknowledged INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_alerts_ts ON alerts(timestamp);

CREATE TABLE IF NOT EXISTS images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    filename TEXT,
    pipe_section TEXT,
    defect_detected INTEGER DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_images_ts ON images(timestamp);

CREATE TABLE IF NOT EXISTS reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    start_time DATETIME,
    end_time DATETIME,
    summary TEXT,
    filename TEXT
);
