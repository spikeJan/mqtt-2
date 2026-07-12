<template>
  <div class="page">
    <div class="page-header">传感器历史曲线</div>
    <div class="time-range">
      <van-button v-for="r in ranges" :key="r.value" size="small" :type="selectedRange === r.value ? 'primary' : 'default'" @click="selectRange(r.value)">{{ r.label }}</van-button>
    </div>
    <ChartPanel title="姿态角 (°)" :xData="timeLabels" :series="[rollSeries, pitchSeries, yawSeries]" />
    <ChartPanel title="速度" :xData="timeLabels" :series="[speedSeries]" />
    <ChartPanel title="气体浓度 (ppm)" :xData="timeLabels" :series="[coSeries, co2Series]" />
    <div style="text-align:center; padding: 12px; color: #999; font-size: 12px;">
      共 {{ historyData.length }} 条记录 | 自动刷新
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted, computed } from 'vue'
import { subscribe, TOPICS } from '../services/mqtt.js'
import ChartPanel from '../components/ChartPanel.vue'

const ranges = [
  { label: '1分钟', value: 60 },
  { label: '5分钟', value: 300 },
  { label: '30分钟', value: 1800 },
  { label: '1小时', value: 3600 },
]
const selectedRange = ref(300)
const historyData = reactive([])
const MAX_POINTS = 200

let unsubs = []

function selectRange(v) {
  selectedRange.value = v
  pruneHistory()
}

function pruneHistory() {
  const cutoff = Date.now() / 1000 - selectedRange.value
  while (historyData.length && historyData[0].ts < cutoff) {
    historyData.shift()
  }
}

const timeLabels = computed(() => historyData.map(d => {
  const t = new Date(d.ts * 1000)
  return t.toLocaleTimeString('zh-CN', { hour12: false })
}))

const rollSeries = computed(() => ({
  name: 'Roll', type: 'line', data: historyData.map(d => d.roll ?? 0),
  lineStyle: { color: '#f56c6c' }, symbol: 'none',
}))
const pitchSeries = computed(() => ({
  name: 'Pitch', type: 'line', data: historyData.map(d => d.pitch ?? 0),
  lineStyle: { color: '#409eff' }, symbol: 'none',
}))
const yawSeries = computed(() => ({
  name: 'Yaw', type: 'line', data: historyData.map(d => d.yaw ?? 0),
  lineStyle: { color: '#67c23a' }, symbol: 'none',
}))
const speedSeries = computed(() => ({
  name: '速度', type: 'line', data: historyData.map(d => d.speed ?? 0),
  lineStyle: { color: '#1989fa' }, symbol: 'none', areaStyle: { color: 'rgba(25,137,250,0.1)' },
}))
const coSeries = computed(() => ({
  name: 'CO', type: 'line', data: historyData.map(d => d.co ?? 0),
  lineStyle: { color: '#f56c6c' }, symbol: 'none',
}))
const co2Series = computed(() => ({
  name: 'CO2', type: 'line', data: historyData.map(d => d.co2 ?? 0),
  lineStyle: { color: '#e6a23c' }, symbol: 'none',
}))

onMounted(() => {
  unsubs.push(subscribe(TOPICS.allSensors, (data) => {
    historyData.push({ ...data, ts: data.timestamp || Date.now() / 1000 })
    if (historyData.length > MAX_POINTS) historyData.shift()
    pruneHistory()
  }))
})

onUnmounted(() => unsubs.forEach(fn => fn()))
</script>

<style scoped>
.page { padding-bottom: 20px; }
.time-range { display: flex; gap: 8px; padding: 8px 12px; flex-wrap: wrap; }
</style>
