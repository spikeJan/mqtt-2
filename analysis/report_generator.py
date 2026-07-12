#!/usr/bin/env python3
"""分析报告生成器 - 综合传感器+告警数据生成完整报告"""

import sqlite3
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from analyze import get_connection, analyze_sensors, analyze_alerts, generate_suggestions

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "car_data.db")
REPORT_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "database", "reports")


def generate_html_report(conn, start_time=None, end_time=None):
    """生成HTML格式的分析报告"""
    sensor = analyze_sensors(conn, start_time, end_time)
    alerts = analyze_alerts(conn, start_time, end_time)
    suggestions = generate_suggestions(sensor, alerts)

    t = sensor.get("temperature", {})
    h = sensor.get("humidity", {})
    d = sensor.get("distance", {})

    html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>管道探测小车 - 分析报告</title>
<style>
  body {{ font-family: 'PingFang SC', 'Microsoft YaHei', sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; background: #f5f5f5; }}
  .header {{ background: linear-gradient(135deg, #1989fa, #409eff); color: #fff; padding: 24px; border-radius: 12px; margin-bottom: 20px; }}
  .header h1 {{ margin: 0; font-size: 22px; }}
  .header p {{ margin: 4px 0 0; opacity: .8; font-size: 13px; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin-bottom: 20px; }}
  .card {{ background: #fff; border-radius: 10px; padding: 16px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .card .label {{ font-size: 12px; color: #999; }}
  .card .value {{ font-size: 24px; font-weight: 700; color: #1989fa; }}
  .section {{ background: #fff; border-radius: 10px; padding: 16px; margin-bottom: 12px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }}
  .section h3 {{ margin: 0 0 12px; font-size: 16px; }}
  .sug {{ display: flex; gap: 10px; padding: 10px; margin-bottom: 8px; border-radius: 8px; }}
  .sug.high {{ background: #fde2e2; border-left: 4px solid #f56c6c; }}
  .sug.mid {{ background: #fef0d0; border-left: 4px solid #e6a23c; }}
  .sug.low {{ background: #e8f8e8; border-left: 4px solid #67c23a; }}
  .sug .icon {{ font-size: 20px; }}
  .sug .title {{ font-weight: 600; font-size: 14px; }}
  .sug .desc {{ font-size: 12px; color: #666; margin-top: 2px; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
  th, td {{ padding: 8px 12px; text-align: left; border-bottom: 1px solid #eee; }}
  th {{ background: #fafafa; font-weight: 600; }}
  .footer {{ text-align: center; color: #999; font-size: 12px; margin-top: 24px; }}
</style>
</head>
<body>
<div class="header">
  <h1>管道探测小车 数据分析报告</h1>
  <p>生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
</div>

<div class="grid">
  <div class="card"><div class="label">总记录数</div><div class="value">{sensor.get('record_count', 0)}</div></div>
  <div class="card"><div class="label">工作时长(h)</div><div class="value">{sensor.get('time_span_hours', 0)}</div></div>
  <div class="card"><div class="label">探测距离(m)</div><div class="value">{d.get('total_m', 0)}</div></div>
  <div class="card"><div class="label">告警总数</div><div class="value">{alerts.get('total', 0)}</div></div>
</div>

<div class="section">
  <h3>温度统计</h3>
  <p>平均: {t.get('avg', '--')}°C / 最低: {t.get('min', '--')}°C / 最高: {t.get('max', '--')}°C</p>
</div>

<div class="section">
  <h3>湿度统计</h3>
  <p>平均: {h.get('avg', '--')}% / 最低: {h.get('min', '--')}% / 最高: {h.get('max', '--')}%</p>
</div>

<div class="section">
  <h3>分析建议</h3>
  {''.join(f'<div class="sug {s["severity"]}"><div class="icon">{"🔴" if s["severity"]=="high" else "🟡" if s["severity"]=="mid" else "🟢"}</div><div><div class="title">{s["title"]}</div><div class="desc">{s["desc"]}</div></div></div>' for s in suggestions)}
</div>

<div class="footer">管道探测小车 MQTT数据展板 · 自动生成</div>
</body>
</html>"""
    return html


def main():
    os.makedirs(REPORT_DIR, exist_ok=True)
    conn = get_connection()

    # 生成HTML报告
    html = generate_html_report(conn)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    html_path = os.path.join(REPORT_DIR, f"report_{ts}.html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML报告已生成: {html_path}")

    # 生成JSON摘要
    sensor = analyze_sensors(conn)
    alerts = analyze_alerts(conn)
    suggestions = generate_suggestions(sensor, alerts)
    json_path = os.path.join(REPORT_DIR, f"summary_{ts}.json")
    summary = {"sensor_summary": sensor, "alert_summary": alerts, "suggestions": suggestions,
               "generated_at": datetime.now().isoformat()}
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"JSON摘要已生成: {json_path}")

    # 存入数据库reports表
    conn.execute(
        "INSERT INTO reports (start_time, end_time, summary, filename) VALUES (?, ?, ?, ?)",
        (None, None, json.dumps(summary, ensure_ascii=False), html_path),
    )
    conn.commit()
    conn.close()
    print("报告已存入数据库")

    return 0


if __name__ == "__main__":
    sys.exit(main())
