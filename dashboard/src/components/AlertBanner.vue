<template>
  <div class="alert-banner" v-if="alerts.length">
    <div class="alert-header">⚠ 最近告警</div>
    <div v-for="(a, i) in alerts.slice(-5).reverse()" :key="i" class="alert-item" :class="'level-' + a.level">
      <span class="alert-dot"></span>
      <span class="alert-time">{{ formatTime(a.timestamp || a.time) }}</span>
      <span class="alert-msg">{{ a.message }}</span>
    </div>
  </div>
</template>

<script setup>
defineProps({ alerts: { type: Array, default: () => [] } })
function formatTime(ts) {
  if (!ts) return ''
  const d = new Date(typeof ts === 'number' ? ts * 1000 : ts)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}
</script>

<style scoped>
.alert-banner { padding: 0 12px; }
.alert-header { font-size: 13px; color: #e6a23c; margin-bottom: 6px; font-weight: 600; }
.alert-item { display: flex; align-items: center; gap: 6px; font-size: 12px; padding: 4px 8px; border-radius: 4px; margin-bottom: 3px; }
.level-info { background: #e8f4fd; }
.level-warning { background: #fef0d0; }
.level-critical { background: #fde2e2; }
.alert-dot { width: 6px; height: 6px; border-radius: 50%; }
.level-info .alert-dot { background: #1989fa; }
.level-warning .alert-dot { background: #e6a23c; }
.level-critical .alert-dot { background: #f56c6c; }
.alert-time { color: #999; flex-shrink: 0; }
.alert-msg { color: #333; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
