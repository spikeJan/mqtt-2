"""网口(TCP)数据读取与解析 — RS485 协议 v2 二进制帧解析(小端序)"""

import socket
import struct
import time
import logging

logger = logging.getLogger(__name__)

# 帧头
FRAME_HEADER = b'\xAA\x55'

# 帧类型 -> (数据区长度, 有无帧尾, 总帧长)
# 0x01: 姿态包 Roll(4)+Pitch(4)+Yaw(4)+status(2)=14, 有帧尾DDEE, 21字节
# 0x02: 轮子包 Speed(4)+Servo(4)=8, 有帧尾DDEE, 15字节
# 0x04: 全量传感器帧 Roll(4)+Pitch(4)+Yaw(4)+Speed(2)+Servo1(2)+Servo2(2)+CO(2)+CO2(2)=22, 无帧尾, 27字节
FRAME_TYPES = {
    0x01: {"data_len": 14, "has_tail": True,  "format": "<fff",   "keys": ["roll", "pitch", "yaw"]},
    0x02: {"data_len": 8,  "has_tail": True,  "format": "<ii",    "keys": ["speed", "servo1"]},
    0x04: {"data_len": 22, "has_tail": False, "format": "<fffHHHHH", "keys": ["roll", "pitch", "yaw", "speed", "servo1", "servo2", "co", "co2"]},
}

FRAME_TAIL = b'\xDD\xEE'
HEADER_LEN = 4       # AA 55 + seq + type
MIN_HEADER = 4        # 至少需要4字节才能读取type


class NetworkReader:
    """通过TCP Socket连接小车网口,读取二进制传感器帧"""

    def __init__(self, host, port, timeout=2):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.sock = None
        self._buf = b''

    def connect(self):
        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(self.timeout)
            self.sock.connect((self.host, self.port))
            logger.info(f"网口 {self.host}:{self.port} 已连接")
            return True
        except (socket.error, OSError) as e:
            logger.error(f"网口连接失败: {e}")
            return False

    def disconnect(self):
        if self.sock:
            try: self.sock.close()
            except Exception: pass
            self.sock = None
            logger.info("网口已断开")

    def read_frame(self):
        """从缓冲区查找并解析一个完整帧,返回字典或None"""
        if not self.sock:
            return None

        try:
            data = self.sock.recv(4096)
            if not data:
                logger.warning("网口连接已关闭")
                self.disconnect()
                return None
            self._buf += data
            logger.info(f"收到 {len(data)} 字节, 缓冲区 {len(self._buf)} 字节")
        except socket.timeout:
            logger.info("TCP等待数据中...")  # 确认socket未断开
            pass
        except (socket.error, OSError):
            self.disconnect()
            return None

        while True:
            # 查找帧头 AA 55
            idx = self._buf.find(FRAME_HEADER)
            if idx < 0:
                self._buf = self._buf[-1:]
                return None
            if idx > 0:
                self._buf = self._buf[idx:]

            # 至少需要4字节读取帧类型
            if len(self._buf) < MIN_HEADER:
                return None

            data_type = self._buf[3]
            info = FRAME_TYPES.get(data_type)
            if info is None:
                logger.warning(f"未知帧类型: 0x{data_type:02X}, 跳过1字节")
                self._buf = self._buf[1:]
                continue

            data_len = info["data_len"]
            has_tail = info["has_tail"]
            frame_len = HEADER_LEN + data_len + 1 + (2 if has_tail else 0)

            if len(self._buf) < frame_len:
                return None

            seq = self._buf[2]
            payload = self._buf[4:4 + data_len]

            # 校验和
            if has_tail:
                checksum = self._buf[4 + data_len]
                # 验证帧尾
                tail_start = 4 + data_len + 1
                if self._buf[tail_start:tail_start + 2] != FRAME_TAIL:
                    logger.warning(f"帧尾不匹配: 期望DDEE 实际{self._buf[tail_start:tail_start+2].hex().upper()}, 跳过1字节")
                    self._buf = self._buf[1:]
                    continue
            else:
                # 0x04: 无帧尾, 校验和在数据区之后
                checksum = self._buf[4 + data_len]

            # 计算校验和 (seq + type + payload)
            calc = (seq + data_type + sum(payload)) & 0xFF
            if calc != checksum:
                logger.warning(f"校验失败 seq={seq} type=0x{data_type:02X} calc=0x{calc:02X} expected=0x{checksum:02X}")
                self._buf = self._buf[1:]
                continue

            # 解析通过
            self._buf = self._buf[frame_len:]

            try:
                values = struct.unpack(info["format"], payload)
                result = {"type": data_type, "seq": seq, "timestamp": time.time()}
                for i, key in enumerate(info["keys"]):
                    v = values[i]
                    if isinstance(v, float):
                        result[key] = round(v, 2)
                    else:
                        result[key] = v
                logger.info(f"解析成功 seq={seq} type=0x{data_type:02X} {dict((k,result[k]) for k in info['keys'] if k in result)}")
                return result
            except struct.error as e:
                logger.warning(f"payload解析失败 type=0x{data_type:02X} len={data_len} err={e}")
                continue


class SimulatedReader:
    """模拟数据源 — 开发测试用"""

    def __init__(self):
        import random
        self.random = random
        self._t = 0.0
        self._seq = 0

    def connect(self):
        logger.info("模拟数据源已就绪")
        return True

    def disconnect(self):
        pass

    def read_frame(self):
        import math
        self._t += 0.1
        self._seq = (self._seq + 1) & 0xFF
        return {
            "type": 0x04,
            "seq": self._seq,
            "timestamp": time.time(),
            "roll": round(math.sin(self._t * 0.5) * 15, 2),
            "pitch": round(math.cos(self._t * 0.3) * 10, 2),
            "yaw": round((self._t * 30) % 360, 2),
            "speed": self.random.randint(0, 80),
            "servo1": self.random.randint(0, 180),
            "servo2": self.random.randint(0, 180),
            "co": self.random.randint(0, 50),
            "co2": self.random.randint(300, 800),
        }
