<template>
  <div class="page">
    <div class="page-header">数据分析与建议</div>

    <div class="summary-cards">
      <div class="summary-item">
        <div class="summary-num">{{ stats.maxSpeed }}</div>
        <div class="summary-label">最高速度</div>
      </div>
      <div class="summary-item">
        <div class="summary-num">{{ stats.avgSpeed }}</div>
        <div class="summary-label">平均速度</div>
      </div>
      <div class="summary-item">
        <div class="summary-num">{{ stats.maxCO }}</div>
        <div class="summary-label">CO峰值 (ppm)</div>
      </div>
      <div class="summary-item">
        <div class="summary-num">{{ stats.maxCO2 }}</div>
        <div class="summary-label">CO2峰值 (ppm)</div>
      </div>
    </div>

    <div class="section-title">姿态角/速度趋势</div>
    <ChartPanel title="" :xData="trendLabels" :series="[trendRollSeries, trendSpeedSeries]" />

    <div class="section-title">气体浓度趋势</div>
    <ChartPanel title="" :xData="trendLabels" :series="[trendCOSeries, trendCO2Series]" />

    <div class="section-title">分析建议</div>
    <div class="suggestions">
      <div v-for="(s, i) in suggestions" :key="i" class="suggestion-item" :class="'sev-' + s.severity">
        <div class="sug-icon">{{ s.severity === 'high' ? '🔴' : s.severity === 'mid' ? '🟡' : '🟢' }}</div>
        <div>
          <div class="sug-title">{{ s.title }}</div>
          <div class="sug-desc">{{ s.desc }}</div>
        </div>
      </div>
    </div>

    <div style="padding: 16px 12px;">
      <van-button type="primary" block :loading="analyzing" @click="runAnalysis" icon="play-circle-o">
        {{ analyzing ? '分析中...' : '运行数据分析' }}
      </van-button>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, onUnmounted } from 'vue'
import { subscribe, TOPICS } from '../services/mqtt.js'
import ChartPanel from '../components/ChartPanel.vue'

const stats = reactive({ maxSpeed: '--', avgSpeed: '--', maxCO: '--', maxCO2: '--' })
const trendLabels = ref([])
const trendRollSeries = ref({ name: 'Roll', type: 'line', data: [] })
const trendSpeedSeries = ref({ name: '速度', type: 'line', data: [] })
const trendCOSeries = ref({ name: 'CO', type: 'line', data: [] })
const trendCO2Series = ref({ name: 'CO2', type: 'line', data: [] })
const analyzing = ref(false)
const suggestions = ref([])

const analysisData = []
let unsubs = []

onMounted(() => {
  unsubs.push(subscribe(TOPICS.allSensors, (data) => {
    analysisData.push({ ...data, ts: data.timestamp || Date.now() / 1000 })
    if (analysisData.length > 300) analysisData.shift()
  }))
})

function runAnalysis() {
  analyzing.value = true
  setTimeout(() => {
    if (analysisData.length < 2) { analyzing.value = false; return }

    const rolls = analysisData.map(d => d.roll).filter(v => v != null)
    const speeds = analysisData.map(d => d.speed).filter(v => v != null)
    const cos = analysisData.map(d => d.co).filter(v => v != null)
    const co2s = analysisData.map(d => d.co2).filter(v => v != null)
    const ts = analysisData.map(d => {
      const t = new Date(d.ts * 1000)
      return t.toLocaleTimeString('zh-CN', { hour12: false })
    })

    trendLabels.value = ts
    trendRollSeries.value = { name: 'Roll (°)', type: 'line', data: rolls, lineStyle: { color: '#f56c6c' }, symbol: 'none' }
    trendSpeedSeries.value = { name: '速度', type: 'line', data: speeds, lineStyle: { color: '#1989fa' }, symbol: 'none' }
    trendCOSeries.value = { name: 'CO (ppm)', type: 'line', data: cos, lineStyle: { color: '#f56c6c' }, symbol: 'none' }
    trendCO2Series.value = { name: 'CO2 (ppm)', type: 'line', data: co2s, lineStyle: { color: '#e6a23c' }, symbol: 'none' }

    const maxSpeed = Math.max(...speeds, 0)
    const avgSpeed = (speeds.reduce((a, b) => a + b, 0) / speeds.length) || 0
    const maxCO = Math.max(...cos, 0)
    const maxCO2 = Math.max(...co2s, 0)

    stats.maxSpeed = maxSpeed
    stats.avgSpeed = avgSpeed.toFixed(1)
    stats.maxCO = maxCO
    stats.maxCO2 = maxCO2

    const newSuggestions = []

    if (maxCO > 35) {
      newSuggestions.push({
        severity: 'high', title: 'CO浓度超标!',
        desc: `一氧化碳峰值 ${maxCO} ppm，超出安全限值35ppm。立即停止作业，检查管道是否有燃烧源，确保通风。`,
      })
    } else if (maxCO > 20) {
      newSuggestions.push({
        severity: 'mid', title: 'CO浓度偏高',
        desc: `一氧化碳峰值 ${maxCO} ppm，接近警戒值。建议加强通风，持续监测。`,
      })
    }

    if (maxCO2 > 1000) {
      newSuggestions.push({
        severity: 'high', title: 'CO2浓度超标!',
        desc: `二氧化碳峰值 ${maxCO2} ppm，超出安全限值1000ppm。管道通风不良，建议立即通风。`,
      })
    } else if (maxCO2 > 800) {
      newSuggestions.push({
        severity: 'mid', title: 'CO2浓度偏高',
        desc: `二氧化碳峰值 ${maxCO2} ppm，空气质量下降，注意通风。`,
      })
    }

    const rollExtreme = Math.max(...rolls.map(Math.abs))
    if (rollExtreme > 30) {
      newSuggestions.push({
        severity: 'mid', title: '车身倾斜过大',
        desc: `翻滚角最大 ${rollExtreme.toFixed(1)}°，可能有侧翻风险。检查管道坡度和平整度。`,
      })
    }

    if (maxSpeed > 70) {
      newSuggestions.push({
        severity: 'low', title: '速度偏高',
        desc: '最高速度接近上限80，高速下传感器精度可能下降，建议适当降速。',
      })
    }

    if (!maxCO && !maxCO2) {
      newSuggestions.push({
        severity: 'low', title: '气体指标正常',
        desc: 'CO和CO2浓度均在安全范围内，管道空气质量良好。',
      })
    }

    newSuggestions.push({
      severity: 'low', title: '综合评估',
      desc: `共分析 ${analysisData.length} 条数据。平均速度 ${avgSpeed.toFixed(1)}。气体指标${maxCO < 20 && maxCO2 < 800 ? '安全' : '需关注'}。`,
    })
    suggestions.value = newSuggestions
    analyzing.value = false
  }, 800)
}

onUnmounted(() => unsubs.forEach(fn => fn()))
</script>

<style scoped>
.page { padding-bottom: 20px; }
.summary-cards { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; padding: 0 12px; }
.summary-item {
  background: #fff; border-radius: 10px; padding: 16px; text-align: center;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.summary-num { font-size: 28px; font-weight: 700; color: #1989fa; }
.summary-label { font-size: 12px; color: #999; margin-top: 4px; }
.suggestions { padding: 0 12px; }
.suggestion-item {
  display: flex; gap: 10px; padding: 12px; margin-bottom: 8px; border-radius: 10px;
  background: #fff; box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.sev-high { border-left: 4px solid #f56c6c; }
.sev-mid { border-left: 4px solid #e6a23c; }
.sev-low { border-left: 4px solid #67c23a; }
.sug-icon { font-size: 20px; flex-shrink: 0; }
.sug-title { font-size: 14px; font-weight: 600; }
.sug-desc { font-size: 12px; color: #666; margin-top: 4px; line-height: 1.5; }
</style>
