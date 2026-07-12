/**
 * 小车 TCP 传感器数据发送模块 (STM32F405 + LwIP)
 * 电脑 IP: 192.168.0.100  TCP 端口: 1234
 * 帧格式: 29字节, AA 55 帧头, 0D 0A 帧尾, 小端序
 */

#ifndef CAR_TCP_SENDER_H
#define CAR_TCP_SENDER_H

#include <stdint.h>

/* ── 网络配置 ── */
#define CAR_IP           "192.168.0.233"   // 本机 IP
#define CAR_NETMASK      "255.255.255.0"
#define CAR_GATEWAY      "192.168.0.1"
#define PC_PORT          1234               // 电脑端口 (PC 连接此端口)

/* ── 帧结构常量 ── */
#define FRAME_HEADER_0   0xAA
#define FRAME_HEADER_1   0x55
#define FRAME_TYPE_DATA  0x04              // 全数据帧
#define FRAME_FOOTER_0   0x0D
#define FRAME_FOOTER_1   0x0A
#define FRAME_SIZE       29                // 总字节数

/* ── 传感器原始数据 ── */
typedef struct {
    float    roll;      // 翻滚角 (°)
    float    pitch;     // 俯仰角 (°)
    float    yaw;       // 偏航角 (°)
    uint16_t speed;     // 速度 (0-80)
    uint16_t servo1;    // 舵机1 (0-180°)
    uint16_t servo2;    // 舵机2 (0-180°)
    uint16_t co;        // 一氧化碳 (ppm)
    uint16_t co2;       // 二氧化碳 (ppm)
} sensor_data_t;

/* ── API ── */

/**
 * 初始化以太网和 LwIP 协议栈
 * 在 HAL_Init() + SystemClock_Config() 之后调用
 * 调用前需通过 CubeMX 配置好 ETH(MAC) + PHY + LwIP
 */
void car_network_init(void);

/**
 * TCP Server 主循环
 * 阻塞等待 PC 连接, 连接后持续发送传感器数据
 * 放在 FreeRTOS 任务中调用, 或裸机主循环中调用
 */
void car_tcp_server_task(void *arg);

/**
 * 读取传感器数据 (用户根据实际传感器实现)
 * 返回填充好的 sensor_data_t 结构体
 */
sensor_data_t car_read_sensors(void);

/**
 * 将传感器数据打包为 29 字节帧并发送
 * @return 实际发送字节数, <0 表示失败
 */
int car_send_frame(int sock, const sensor_data_t *data);

#endif /* CAR_TCP_SENDER_H */
