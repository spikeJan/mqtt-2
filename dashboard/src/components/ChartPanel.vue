<template>
  <div class="chart-panel">
    <div class="chart-header">{{ title }}</div>
    <v-chart :option="option" autoresize style="height: 220px" />
  </div>
</template>

<script setup>
import { computed } from 'vue'
import VChart from 'vue-echarts'
import { use } from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { CanvasRenderer } from 'echarts/renderers'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
use([LineChart, CanvasRenderer, GridComponent, TooltipComponent, LegendComponent])

const props = defineProps({
  title: String,
  xData: { type: Array, default: () => [] },
  series: { type: Array, default: () => [] },
  unit: { type: String, default: '' },
})

const option = computed(() => ({
  grid: { top: 10, left: 40, right: 16, bottom: 28 },
  tooltip: { trigger: 'axis' },
  legend: { bottom: 0, textStyle: { fontSize: 10 } },
  xAxis: { type: 'category', data: props.xData, axisLabel: { fontSize: 9, rotate: 30 } },
  yAxis: {
    type: 'value',
    axisLabel: { fontSize: 10 },
    splitLine: { lineStyle: { type: 'dashed', color: '#eee' } }
  },
  series: props.series.map(s => ({
    ...s,
    smooth: true,
    symbol: 'none',
    lineStyle: { width: 2 },
  })),
}))
</script>

<style scoped>
.chart-panel {
  background: #fff; border-radius: 10px; margin: 6px 12px; padding: 10px;
  box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.chart-header { font-size: 14px; font-weight: 600; margin-bottom: 4px; }
</style>
