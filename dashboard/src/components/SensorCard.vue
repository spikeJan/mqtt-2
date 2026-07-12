<template>
  <div class="sensor-card" :style="{ borderLeftColor: color }">
    <div class="sensor-icon">{{ icon }}</div>
    <div class="sensor-info">
      <div class="sensor-label">{{ label }}</div>
      <div class="sensor-value">{{ displayValue }} <span class="sensor-unit">{{ unit }}</span></div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  label: String,
  value: [Number, String],
  unit: { type: String, default: '' },
  icon: { type: String, default: '📊' },
  color: { type: String, default: '#1989fa' },
  precision: { type: Number, default: 1 },
})
const displayValue = computed(() => {
  const v = props.value
  if (v === null || v === undefined || v === '--') return '--'
  if (typeof v === 'string') return v
  return v.toFixed(props.precision)
})
</script>

<style scoped>
.sensor-card {
  display: flex; align-items: center; gap: 10px;
  background: #fff; border-radius: 10px; padding: 14px 12px;
  border-left: 4px solid #1989fa; box-shadow: 0 1px 4px rgba(0,0,0,.06);
}
.sensor-icon { font-size: 24px; }
.sensor-label { font-size: 12px; color: #999; }
.sensor-value { font-size: 22px; font-weight: 700; }
.sensor-unit { font-size: 12px; color: #999; font-weight: 400; }
</style>
