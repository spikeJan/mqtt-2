<template>
  <div class="page">
    <div class="page-header">实时仪表盘</div>
    <SpeedGauge :speed="sensorData.speed" />
    <div class="section-title">姿态角度</div>
    <div class="card-grid">
      <SensorCard label="翻滚角 Roll" :value="sensorData.roll" unit="°" icon="↻" color="#f56c6c" />
      <SensorCard label="俯仰角 Pitch" :value="sensorData.pitch" unit="°" icon="↕" color="#409eff" />
      <SensorCard label="偏航角 Yaw" :value="sensorData.yaw" unit="°" icon="🧭" color="#67c23a" />
    </div>
    <div class="section-title">舵机</div>
    <div class="card-grid">
      <SensorCard label="舵机1角度" :value="sensorData.servo1" unit="°" icon="🔧" color="#e6a23c" :precision="0" />
      <SensorCard label="舵机2角度" :value="sensorData.servo2" unit="°" icon="🔧" color="#409eff" :precision="0" />
    </div>
    <div class="section-title">气体检测</div>
    <div class="card-grid">
      <SensorCard label="一氧化碳 CO" :value="sensorData.co" unit="ppm" icon="⚠" :color="sensorData.co > 35 ? '#f56c6c' : '#67c23a'" :precision="0" />
      <SensorCard label="二氧化碳 CO2" :value="sensorData.co2" unit="ppm" icon="🌫" :color="sensorData.co2 > 1000 ? '#f56c6c' : '#67c23a'" :precision="0" />
    </div>
    <AlertBanner :alerts="alerts" />
    <div class="connection-badge" :class="{ connected: mqttConnected }">
      {{ mqttConnected ? '🟢 MQTT已连接' : '🔴 MQTT未连接' }}
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { subscribe, TOPICS, onConnected } from '../services/mqtt.js'
import SpeedGauge from '../components/SpeedGauge.vue'
import SensorCard from '../components/SensorCard.vue'
import AlertBanner from '../components/AlertBanner.vue'

const mqttConnected = ref(false)
const sensorData = reactive({
  roll: '--', pitch: '--', yaw: '--',
  speed: 0, servo1: '--', servo2: '--', co: '--', co2: '--',
})
const alerts = ref([])

let unsubs = []

onMounted(() => {
  unsubs.push(onConnected((connected) => { mqttConnected.value = connected }))
  unsubs.push(subscribe(TOPICS.allSensors, (data) => {
    Object.assign(sensorData, {
      roll: data.roll ?? sensorData.roll,
      pitch: data.pitch ?? sensorData.pitch,
      yaw: data.yaw ?? sensorData.yaw,
      speed: data.speed ?? sensorData.speed,
      servo1: data.servo1 ?? sensorData.servo1,
      servo2: data.servo2 ?? sensorData.servo2,
      co: data.co ?? sensorData.co,
      co2: data.co2 ?? sensorData.co2,
    })
    // 自动告警
    if (data.co > 35 && alerts.value.filter(a => a.message.includes('CO超标')).length === 0) {
      alerts.value.push({ level: 'critical', message: `CO浓度超标: ${data.co} ppm`, timestamp: Date.now() / 1000 })
    }
    if (data.co2 > 1000 && alerts.value.filter(a => a.message.includes('CO2超标')).length === 0) {
      alerts.value.push({ level: 'warning', message: `CO2浓度偏高: ${data.co2} ppm`, timestamp: Date.now() / 1000 })
    }
  }))

  unsubs.push(subscribe(TOPICS.alert, (data) => {
    alerts.value.push(data)
    if (alerts.value.length > 50) alerts.value.shift()
  }))
})

onUnmounted(() => unsubs.forEach(fn => fn()))
</script>

<style scoped>
.page { padding-bottom: 20px; }
.motor-status {
  display: flex; align-items: center; gap: 8px; margin: 12px;
  background: #fff; border-radius: 10px; padding: 14px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06); font-size: 14px;
}
.status-label { font-weight: 600; }
.status-dot { width: 10px; height: 10px; border-radius: 50%; }
.running { background: #67c23a; animation: pulse 1s infinite; }
.stopped { background: #c0c4cc; }
.motor-speed { color: #999; margin-left: auto; }
@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.3; } }
.connection-badge { text-align: center; font-size: 12px; padding: 6px; margin: 0 12px; border-radius: 6px; }
.connected { background: #e8f8e8; }
.connection-badge:not(.connected) { background: #fde2e2; }
</style>
