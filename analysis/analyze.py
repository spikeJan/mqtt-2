#!/usr/bin/env python3
"""数据分析主脚本 — 读取SQLite数据,生成统计报告"""

import sqlite3
import os
import sys
import json
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "car_data.db")


def get_connection(db_path=None):
    path = db_path or DB_PATH
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def analyze_sensors(conn, start_time=None, end_time=None):
    conditions = []
    params = []
    if start_time:
        conditions.append("timestamp >= ?")
        params.append(start_time)
    if end_time:
        conditions.append("timestamp <= ?")
        params.append(end_time)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    rows = conn.execute(f"SELECT * FROM sensor_readings {where} ORDER BY timestamp").fetchall()
    if not rows:
        return {"error": "选定时间范围内无数据"}

    rolls = [r["roll"] for r in rows if r["roll"] is not None]
    pitchs = [r["pitch"] for r in rows if r["pitch"] is not None]
    yaws = [r["yaw"] for r in rows if r["yaw"] is not None]
    speeds = [r["speed"] for r in rows if r["speed"] is not None]
    cos = [r["co"] for r in rows if r["co"] is not None]
    co2s = [r["co2"] for r in rows if r["co2"] is not None]

    time_span_hours = 0
    if len(rows) >= 2:
        t1 = datetime.fromisoformat(rows[0]["timestamp"])
        t2 = datetime.fromisoformat(rows[-1]["timestamp"])
        time_span_hours = (t2 - t1).total_seconds() / 3600

    return {
        "record_count": len(rows),
        "time_span_hours": round(time_span_hours, 2),
        "roll": {"avg": round(sum(rolls) / len(rolls), 1) if rolls else 0,
                  "min": round(min(rolls), 1) if rolls else 0,
                  "max": round(max(rolls), 1) if rolls else 0},
        "pitch": {"avg": round(sum(pitchs) / len(pitchs), 1) if pitchs else 0,
                   "min": round(min(pitchs), 1) if pitchs else 0,
                   "max": round(max(pitchs), 1) if pitchs else 0},
        "yaw": {"avg": round(sum(yaws) / len(yaws), 1) if yaws else 0,
                "min": round(min(yaws), 1) if yaws else 0,
                "max": round(max(yaws), 1) if yaws else 0},
        "speed": {"avg": round(sum(speeds) / len(speeds), 1) if speeds else 0,
                  "min": min(speeds) if speeds else 0,
                  "max": max(speeds) if speeds else 0},
        "co": {"avg": round(sum(cos) / len(cos), 1) if cos else 0,
                "min": min(cos) if cos else 0,
                "max": max(cos) if cos else 0},
        "co2": {"avg": round(sum(co2s) / len(co2s), 1) if co2s else 0,
                 "min": min(co2s) if co2s else 0,
                 "max": max(co2s) if co2s else 0},
    }


def analyze_alerts(conn, start_time=None, end_time=None):
    conditions, params = [], []
    if start_time:
        conditions.append("timestamp >= ?"); params.append(start_time)
    if end_time:
        conditions.append("timestamp <= ?"); params.append(end_time)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""

    total = conn.execute(f"SELECT COUNT(*) as cnt FROM alerts {where}").fetchone()["cnt"]
    by_level = conn.execute(f"SELECT level, COUNT(*) as cnt FROM alerts {where} GROUP BY level").fetchall()
    recent = conn.execute(f"SELECT * FROM alerts {where} ORDER BY timestamp DESC LIMIT 10").fetchall()

    return {
        "total": total,
        "by_level": {r["level"]: r["cnt"] for r in by_level},
        "recent": [{"timestamp": r["timestamp"], "level": r["level"], "message": r["message"]} for r in recent],
    }


def generate_suggestions(sensor_summary, alert_summary):
    suggestions = []
    co = sensor_summary.get("co", {})
    co2 = sensor_summary.get("co2", {})
    roll = sensor_summary.get("roll", {})
    speed = sensor_summary.get("speed", {})
    time_span = sensor_summary.get("time_span_hours", 0)

    if co.get("max", 0) > 35:
        suggestions.append({"severity": "high", "title": "CO浓度超标!",
                            "desc": f"一氧化碳峰值 {co['max']} ppm，超出安全限值。立即停止作业，检查管道燃烧源。"})
    elif co.get("max", 0) > 20:
        suggestions.append({"severity": "mid", "title": "CO浓度偏高",
                            "desc": f"一氧化碳峰值 {co['max']} ppm，接近警戒值，建议加强通风。"})

    if co2.get("max", 0) > 1000:
        suggestions.append({"severity": "high", "title": "CO2浓度超标!",
                            "desc": f"二氧化碳峰值 {co2['max']} ppm，超出安全限值。管道通风不良，立即处理。"})
    elif co2.get("max", 0) > 800:
        suggestions.append({"severity": "mid", "title": "CO2浓度偏高",
                            "desc": f"二氧化碳峰值 {co2['max']} ppm，空气质量下降，注意通风。"})

    roll_max = max(abs(roll.get("min", 0)), abs(roll.get("max", 0)))
    if roll_max > 30:
        suggestions.append({"severity": "mid", "title": "车身倾斜过大",
                            "desc": f"翻滚角最大 {roll_max:.1f}°，可能有侧翻风险。检查管道坡度。"})

    if speed.get("max", 0) > 70:
        suggestions.append({"severity": "low", "title": "速度偏高",
                            "desc": "最高速度接近上限80，高速下传感器精度可能下降。"})

    if time_span > 1.5:
        suggestions.append({"severity": "low", "title": "连续作业提醒",
                            "desc": f"已连续工作 {time_span:.1f}小时，建议适当休息。"})

    suggestions.append({"severity": "low", "title": "综合评估",
                        "desc": f"共 {sensor_summary.get('record_count', 0)} 条记录。"
                                f"气体指标{'安全' if co.get('max', 0) < 20 and co2.get('max', 0) < 800 else '需关注'}。"
                                f"姿态{'稳定' if roll_max < 30 else '有倾斜风险'}。"})
    return suggestions


def main():
    conn = get_connection()
    print("=" * 50)
    print("  管道探测小车 - 数据分析报告")
    print("=" * 50)

    sensor_summary = analyze_sensors(conn)
    alert_summary = analyze_alerts(conn)

    print(f"\n传感器数据: {sensor_summary.get('record_count', 0)} 条记录")
    if "roll" in sensor_summary:
        r = sensor_summary["roll"]
        print(f"  Roll:  avg {r['avg']}° / min {r['min']}° / max {r['max']}°")
    if "co" in sensor_summary:
        c = sensor_summary["co"]
        print(f"  CO:   峰值 {c['max']} ppm")
    if "co2" in sensor_summary:
        c = sensor_summary["co2"]
        print(f"  CO2:  峰值 {c['max']} ppm")
    if "speed" in sensor_summary:
        s = sensor_summary["speed"]
        print(f"  速度:  avg {s['avg']} / max {s['max']}")

    suggestions = generate_suggestions(sensor_summary, alert_summary)
    print(f"\n分析建议:")
    for s in suggestions:
        icon = {"high": "!!", "mid": "! ", "low": "  "}.get(s["severity"], "  ")
        print(f"  {icon} [{s['severity']}] {s['title']}: {s['desc'][:60]}")

    conn.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
