/**
 * 小车 TCP 传感器数据发送模块 - 实现
 *
 * 硬件: STM32F405RGT6 + 外接 PHY (LAN8720 / DP83848)
 * 前提: CubeMX 已配置 ETH + LwIP (socket API)，FreeRTOS 可选
 *
 * 帧格式 (29字节 小端序):
 *   [0-1]  AA 55          帧头
 *   [2]    seq            序列号 (0-255 循环)
 *   [3]    0x04           全数据帧
 *   [4-7]  roll           float32
 *   [8-11] pitch          float32
 *   [12-15] yaw           float32
 *   [16-17] speed         uint16  (0-80)
 *   [18-19] servo1        uint16  (0-180)
 *   [20-21] servo2        uint16  (0-180)
 *   [22-23] co            uint16  (ppm)
 *   [24-25] co2           uint16  (ppm)
 *   [26]   checksum       字节2-25累加取低8位
 *   [27-28] 0D 0A         帧尾
 */

#include "car_tcp_sender.h"
#include <string.h>
#include <stdio.h>

/* ── STM32 / LwIP 头文件 (根据实际工程调整) ── */
#include "lwip/netif.h"
#include "lwip/sockets.h"
#include "lwip/tcpip.h"
#include "lwip/dhcp.h"
#include "lwip/etharp.h"
#include "netif/etharp.h"

/* ── 外部声明 (CubeMX 自动生成) ── */
extern struct netif gnetif;      // CubeMX 生成的默认网口
extern ETH_HandleTypeDef heth;   // CubeMX 生成的 ETH 句柄

/* ═══════════════════════════════════════════════════════════════
 * 1. 网络初始化
 * ═══════════════════════════════════════════════════════════════ */

void car_network_init(void) {
    /* 注册 MAC 地址 (可用 CubeMX 默认值, 确保局域网唯一) */
    uint8_t mac[6] = { 0x02, 0x00, 0x00, 0x00, 0x00, 0x01 };

    /* 初始化 LwIP 内核 */
    tcpip_init(NULL, NULL);

    /* 添加并配置网口 */
    struct netif *netif = netif_add(&gnetif,
        (ip4_addr_t *)&(ip4_addr_t){0},   // IP (先用 0, DHCP 或静态)
        (ip4_addr_t *)&(ip4_addr_t){0},   // Netmask
        (ip4_addr_t *)&(ip4_addr_t){0},   // Gateway
        NULL,
        ethernetif_init,                   // CubeMX 生成的底层初始化
        tcpip_input);

    if (netif == NULL) {
        printf("[TCP] netif_add 失败\r\n");
        return;
    }

    netif_set_default(netif);
    netif_set_up(netif);

    /* 启用 DHCP (自动获取 IP) —— 或使用静态 IP */
#if 1  /* 静态 IP */
    ip4_addr_t ipaddr, netmask, gw;
    IP4_ADDR(&ipaddr,  192, 168, 0, 233);
    IP4_ADDR(&netmask, 255, 255, 255, 0);
    IP4_ADDR(&gw,      192, 168, 0, 1);
    netif_set_addr(netif, &ipaddr, &netmask, &gw);
#else /* DHCP */
    dhcp_start(netif);
#endif

    printf("[TCP] 网络初始化完成, IP: %s\r\n", CAR_IP);
}


/* ═══════════════════════════════════════════════════════════════
 * 2. 帧打包
 * ═══════════════════════════════════════════════════════════════ */

int car_send_frame(int sock, const sensor_data_t *data) {
    static uint8_t seq = 0;
    uint8_t frame[FRAME_SIZE];
    uint8_t i;
    uint16_t checksum = 0;

    /* ── 填充帧 ── */
    frame[0] = FRAME_HEADER_0;          // AA
    frame[1] = FRAME_HEADER_1;          // 55
    frame[2] = seq++;                   // 序列号 (自动溢出)
    frame[3] = FRAME_TYPE_DATA;         // 0x04 全数据帧

    /* Payload: 22字节, 小端序 */
    /* Roll (float32) */
    memcpy(frame + 4, &data->roll, 4);
    /* Pitch (float32) */
    memcpy(frame + 8, &data->pitch, 4);
    /* Yaw (float32) */
    memcpy(frame + 12, &data->yaw, 4);
    /* Speed (uint16 LE) */
    frame[16] = data->speed & 0xFF;
    frame[17] = (data->speed >> 8) & 0xFF;
    /* Servo1 (uint16 LE) */
    frame[18] = data->servo1 & 0xFF;
    frame[19] = (data->servo1 >> 8) & 0xFF;
    /* Servo2 (uint16 LE) */
    frame[20] = data->servo2 & 0xFF;
    frame[21] = (data->servo2 >> 8) & 0xFF;
    /* CO (uint16 LE) */
    frame[22] = data->co & 0xFF;
    frame[23] = (data->co >> 8) & 0xFF;
    /* CO2 (uint16 LE) */
    frame[24] = data->co2 & 0xFF;
    frame[25] = (data->co2 >> 8) & 0xFF;

    /* 校验和: 字节2-25 累加取低8位 */
    checksum = 0;
    for (i = 2; i < 26; i++) {
        checksum += frame[i];
    }
    frame[26] = (uint8_t)(checksum & 0xFF);

    /* 帧尾 */
    frame[27] = FRAME_FOOTER_0;         // 0D
    frame[28] = FRAME_FOOTER_1;         // 0A

    /* ── 发送 ── */
    int sent = lwip_send(sock, frame, FRAME_SIZE, 0);
    return sent;
}


/* ═══════════════════════════════════════════════════════════════
 * 3. TCP Server 主循环
 * ═══════════════════════════════════════════════════════════════ */

void car_tcp_server_task(void *arg) {
    int listen_sock, client_sock;
    struct sockaddr_in addr;
    int addr_len = sizeof(addr);
    int ret;

    /* ── 等待 LwIP 就绪 ── */
    printf("[TCP] 等待网络就绪...\r\n");
    while (!netif_is_up(&gnetif)) {
        vTaskDelay(pdMS_TO_TICKS(100));
    }

    /* ── 创建监听 Socket ── */
    listen_sock = lwip_socket(AF_INET, SOCK_STREAM, 0);
    if (listen_sock < 0) {
        printf("[TCP] socket 创建失败: %d\r\n", listen_sock);
        vTaskDelete(NULL);
        return;
    }

    /* 绑定本机端口 1234 */
    memset(&addr, 0, sizeof(addr));
    addr.sin_family = AF_INET;
    addr.sin_port = htons(PC_PORT);
    addr.sin_addr.s_addr = INADDR_ANY;

    ret = lwip_bind(listen_sock, (struct sockaddr *)&addr, sizeof(addr));
    if (ret < 0) {
        printf("[TCP] bind 失败: %d\r\n", ret);
        lwip_close(listen_sock);
        vTaskDelete(NULL);
        return;
    }

    /* 开始监听 */
    ret = lwip_listen(listen_sock, 1);
    if (ret < 0) {
        printf("[TCP] listen 失败: %d\r\n", ret);
        lwip_close(listen_sock);
        vTaskDelete(NULL);
        return;
    }

    printf("[TCP] 监听端口 %d, 等待 PC 连接...\r\n", PC_PORT);

    /* ── 主循环: 接受连接 + 发送数据 ── */
    while (1) {
        /* 阻塞等待 PC 连接 */
        client_sock = lwip_accept(listen_sock, (struct sockaddr *)&addr,
                                   (socklen_t *)&addr_len);
        if (client_sock < 0) {
            printf("[TCP] accept 失败: %d\r\n", client_sock);
            vTaskDelay(pdMS_TO_TICKS(1000));
            continue;
        }

        printf("[TCP] PC 已连接\r\n");

        /* ── 持续发送传感器数据 ── */
        while (1) {
            sensor_data_t data = car_read_sensors();
            int sent = car_send_frame(client_sock, &data);

            if (sent < 0) {
                printf("[TCP] 连接断开, 等待重连...\r\n");
                lwip_close(client_sock);
                break;  /* 退出内层循环, 重新 accept */
            }

            /* 10Hz 发送频率 (100ms 间隔) */
            vTaskDelay(pdMS_TO_TICKS(100));
        }
    }
}


/* ═══════════════════════════════════════════════════════════════
 * 4. 传感器读数 (用户实现)
 * ═══════════════════════════════════════════════════════════════ */

sensor_data_t car_read_sensors(void) {
    sensor_data_t data;

    /* ── 替换为你的实际传感器驱动 ── */

    /*
     * 示例: MPU6050 / MPU9250 姿态角
     * data.roll  = mpu_get_roll();
     * data.pitch = mpu_get_pitch();
     * data.yaw   = mpu_get_yaw();
     */
    data.roll  = 0.0f;
    data.pitch = 0.0f;
    data.yaw   = 0.0f;

    /*
     * 示例: 编码器速度
     * data.speed = encoder_get_speed();
     */
    data.speed = 0;

    /*
     * 示例: 舵机 PWM 当前角度
     * data.servo1 = servo_get_angle(1);
     * data.servo2 = servo_get_angle(2);
     */
    data.servo1 = 0;
    data.servo2 = 0;

    /*
     * 示例: MQ-7 (CO) / MQ-135 或串口气体传感器
     * data.co  = gas_sensor_read_co();
     * data.co2 = gas_sensor_read_co2();
     */
    data.co  = 0;
    data.co2 = 0;

    return data;
}
