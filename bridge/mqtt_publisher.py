"""MQTT发布模块"""

import json
import logging
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)

TOPIC_ALL_SENSORS = "car/sensors/all"
TOPIC_ALERT = "car/alerts"
TOPIC_IMAGE = "car/camera/image"

SENSOR_TOPICS = {
    "roll": "car/sensors/roll",
    "pitch": "car/sensors/pitch",
    "yaw": "car/sensors/yaw",
    "speed": "car/sensors/speed",
    "servo1": "car/sensors/servo1",
    "servo2": "car/sensors/servo2",
    "co": "car/sensors/co",
    "co2": "car/sensors/co2",
}


class MQTTPublisher:
    def __init__(self, broker="localhost", port=1883):
        self.broker = broker
        self.port = port
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.connected = False
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        if reason_code == 0:
            self.connected = True
            logger.info(f"MQTT Broker {self.broker}:{self.port} 已连接")
        else:
            logger.error(f"MQTT连接失败, 返回码: {reason_code}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties=None):
        self.connected = False
        logger.warning("MQTT已断开")

    def connect(self):
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            return True
        except Exception as e:
            logger.error(f"MQTT连接失败: {e}")
            return False

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def publish_sensor(self, data):
        """发布传感器数据"""
        payload = {
            "timestamp": data.get("timestamp"),
            "roll": data.get("roll"),
            "pitch": data.get("pitch"),
            "yaw": data.get("yaw"),
            "speed": data.get("speed"),
            "servo1": data.get("servo1"),
            "servo2": data.get("servo2"),
            "co": data.get("co"),
            "co2": data.get("co2"),
        }
        # 聚合消息
        self.client.publish(TOPIC_ALL_SENSORS, json.dumps(payload), qos=0)

        # 单项消息
        for key, topic in SENSOR_TOPICS.items():
            if key in data:
                self.client.publish(topic, str(data[key]), qos=0)

    def publish_alert(self, data):
        msg = json.dumps({
            "timestamp": data.get("timestamp"),
            "level": data.get("level_str", "info"),
            "message": data.get("message", ""),
        })
        self.client.publish(TOPIC_ALERT, msg, qos=1)

    def publish_image(self, data):
        self.client.publish(TOPIC_IMAGE, data.get("image_data"), qos=0)
