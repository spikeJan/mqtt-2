<template>
  <div class="gauge-container">
    <v-chart :option="option" autoresize style="height: 200px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { GaugeChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
use([GaugeChart, CanvasRenderer])

const props = defineProps({ speed: { type: Number, default: 0 } })

const option = computed(() => ({
  series: [{
    type: 'gauge',
    startAngle: 210, endAngle: -30,
    center: ['50%', '60%'], radius: '90%',
    min: 0, max: 80,
    axisLine: {
      lineStyle: {
        width: 18,
        color: [
          [0.3, '#67c23a'], [0.6, '#e6a23c'], [1, '#f56c6c']
        ]
      }
    },
    axisTick: { show: false },
    splitLine: { length: 12, lineStyle: { width: 2, color: '#999' } },
    axisLabel: { distance: 20, fontSize: 10, color: '#999' },
    pointer: { length: '70%', width: 6, itemStyle: { color: '#1989fa' } },
    detail: {
      valueAnimation: true,
      fontSize: 28,
      fontWeight: 'bold',
      offsetCenter: [0, '80%'],
      formatter: '{value}'
    },
    data: [{ value: props.speed, name: '速度' }]
  }]
}))
</script>

<style scoped>
.gauge-container { background: #fff; border-radius: 10px; margin: 0 12px; padding: 8px; box-shadow: 0 1px 4px rgba(0,0,0,.06); }
</style>
