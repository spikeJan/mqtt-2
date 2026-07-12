#!/usr/bin/env python3
"""数据导出脚本 — CSV和Excel格式"""

import sqlite3, csv, os, sys
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "car_data.db")
EXPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "exports")


def export_sensor_csv(conn, output_path, start=None, end=None):
    conditions, params = [], []
    if start:
        conditions.append("timestamp >= ?"); params.append(start)
    if end:
        conditions.append("timestamp <= ?"); params.append(end)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(f"SELECT * FROM sensor_readings {where} ORDER BY timestamp").fetchall()
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "时间", "Roll(°)", "Pitch(°)", "Yaw(°)", "速度", "舵机1(°)", "CO(ppm)", "CO2(ppm)"])
        for r in rows:
            w.writerow([r["id"], r["timestamp"], r["roll"], r["pitch"], r["yaw"],
                        r["speed"], r["servo1"], r["co"], r["co2"]])
    return len(rows)


def export_alerts_csv(conn, output_path, start=None, end=None):
    conditions, params = [], []
    if start:
        conditions.append("timestamp >= ?"); params.append(start)
    if end:
        conditions.append("timestamp <= ?"); params.append(end)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(f"SELECT * FROM alerts {where} ORDER BY timestamp").fetchall()
    with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["ID", "时间", "级别", "消息", "已确认"])
        for r in rows:
            w.writerow([r["id"], r["timestamp"], r["level"], r["message"], r["acknowledged"]])
    return len(rows)


def export_sensor_excel(conn, output_path, start=None, end=None):
    try:
        import openpyxl
    except ImportError:
        print("openpyxl未安装: pip install openpyxl")
        return 0

    conditions, params = [], []
    if start:
        conditions.append("timestamp >= ?"); params.append(start)
    if end:
        conditions.append("timestamp <= ?"); params.append(end)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(f"SELECT * FROM sensor_readings {where} ORDER BY timestamp").fetchall()
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "传感器数据"
    ws.append(["ID", "时间", "Roll", "Pitch", "Yaw", "速度", "舵机1", "CO(ppm)", "CO2(ppm)"])
    for r in rows:
        ws.append([r["id"], r["timestamp"], r["roll"], r["pitch"], r["yaw"],
                   r["speed"], r["servo1"], r["co"], r["co2"]])

    alert_rows = conn.execute(f"SELECT * FROM alerts {where} ORDER BY timestamp").fetchall()
    ws2 = wb.create_sheet("告警记录")
    ws2.append(["ID", "时间", "级别", "消息", "已确认"])
    for r in alert_rows:
        ws2.append([r["id"], r["timestamp"], r["level"], r["message"], r["acknowledged"]])

    wb.save(output_path)
    return len(rows)


def main():
    os.makedirs(EXPORT_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    csv_path = os.path.join(EXPORT_DIR, f"sensor_data_{ts}.csv")
    n = export_sensor_csv(conn, csv_path)
    print(f"传感器: {csv_path} ({n}条)")

    alert_csv = os.path.join(EXPORT_DIR, f"alerts_{ts}.csv")
    n2 = export_alerts_csv(conn, alert_csv)
    print(f"告警: {alert_csv} ({n2}条)")

    xlsx_path = os.path.join(EXPORT_DIR, f"car_data_{ts}.xlsx")
    n3 = export_sensor_excel(conn, xlsx_path)
    print(f"Excel: {xlsx_path} ({n3}条)")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
