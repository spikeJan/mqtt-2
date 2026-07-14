# PipeCar Dashboard — 管道探测小车数据展板

基于 MQTT + WebSocket 的实时传感器数据展板系统，用于**管道探测小车**的远程监控。STM32 小车通过 TCP 发送传感器数据，PC 端解析后通过 MQTT 推送到手机浏览器实时展示。

## 快速开始

双击 exe 即用，无需安装任何环境：

| Exe | 场景 |
|-----|------|
| `PipeCarDashboard.exe` | 真实模式 — 连接小车 TCP |
| `PipeCarDashboard_sim.exe` | 模拟模式 — 随机数据测试 |

启动后自动打开浏览器 → `http://localhost:8080`，手机连同一 WiFi 也能访问。

## 系统架构

```
小车 STM32 ──TCP:1234──> PC 桥接 ──MQTT:1884──> Mosquitto ──WS:9001──> 手机浏览器
                                              │
                                        SQLite 数据库
```

## 功能

- **实时仪表盘** — 速度表、传感器卡片、告警横幅
- **时序曲线图** — Roll/Pitch/Yaw/Speed/CO/CO2 历史趋势
- **视频监控** — RTSP 摄像头 MJPEG 流 + 云台角度显示
- **数据导出** — 按时间范围导出 CSV
- **离线分析** — 统计摘要、异常检测
- **PWA** — 可添加到手机主屏幕，像原生 App 一样使用

## 传感器数据

| 字段 | 说明 |
|------|------|
| Roll / Pitch / Yaw | 三轴姿态角 |
| Speed | 速度 (0-80) |
| Servo1 / Servo2 | 双舵机角度 (0-180°) |
| CO / CO2 | 一氧化碳 / 二氧化碳 (ppm) |

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | Vue 3 + Vite + Vant 4 + ECharts 5 + mqtt.js |
| 桥接 | Python (paho-mqtt, tkinter, socket) |
| 消息 | Mosquitto MQTT Broker (原生 WebSocket) |
| 存储 | SQLite |
| 打包 | PyInstaller |
| 小车 | STM32F405 + LwIP |

## 项目结构

```
├── launcher.py / launcher_sim.py   # 一体化启动器源码
├── dashboard/                      # Vue3 前端
├── bridge/                         # 独立桥接程序（含 RTSP）
├── mosquitto/                      # 便携 MQTT Broker
├── stm32/                          # 小车固件参考代码
├── analysis/                       # 离线分析工具
├── database/schema.sql             # 数据库定义
└── dist/                           # 构建产物 (.exe)
```

## 开发

### Python 源码环境

根目录 `requirements.txt` 会一次安装 Python 桥接和分析工具所需依赖。Windows 示例：

```bat
python -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

运行 Python 单元测试：

```bat
python -B -m unittest discover -s tests -v
```

FFmpeg 是视频功能调用的外部程序，Mosquitto 是 MQTT Broker，二者均不由 pip 安装。Python CI 只验证依赖安装、导入、语法和单元测试，不验证 STM32、摄像头、真实 MQTT、Vue 或 Windows exe。

```bash
# 源码运行模拟模式
python launcher_sim.py

# 源码运行真实模式
python launcher.py

# 分体调试（三个终端）
cd mosquitto && mosquitto.exe -c mosquitto_portable.conf   # MQTT
cd dashboard && npm run dev                                 # 前端
cd bridge && python main.py                                 # 桥接
```

## 构建 Exe

```bash
pip install pyinstaller paho-mqtt

# 真实模式
python -m PyInstaller PipeCarDashboard.spec --noconfirm

# 模拟模式
python -m PyInstaller PipeCarDashboard_sim.spec --workpath build_sim --noconfirm
```

## License

MIT
