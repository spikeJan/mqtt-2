<template>
  <div class="page">
    <div class="page-header">数据导出</div>
    <div class="form-section">
      <div class="field-label">数据类型</div>
      <van-checkbox-group v-model="exportTypes" direction="horizontal">
        <van-checkbox name="sensor" shape="square">传感器数据</van-checkbox>
        <van-checkbox name="alert" shape="square">告警记录</van-checkbox>
        <van-checkbox name="image" shape="square">图像记录</van-checkbox>
      </van-checkbox-group>

      <div class="field-label">导出格式</div>
      <van-radio-group v-model="exportFormat" direction="horizontal">
        <van-radio name="csv">CSV</van-radio>
        <van-radio name="excel">Excel</van-radio>
      </van-radio-group>

      <div class="field-label">时间范围</div>
      <div style="display:flex; gap:8px; margin: 8px 12px;">
        <van-field v-model="startTime" label="开始" placeholder="2024-01-01 00:00" type="text" />
        <van-field v-model="endTime" label="结束" placeholder="2024-12-31 23:59" type="text" />
      </div>

      <div style="padding: 16px 12px;">
        <van-button type="primary" block :loading="exporting" @click="doExport" icon="down-o">
          {{ exporting ? '导出中...' : '开始导出' }}
        </van-button>
      </div>
    </div>
    <div v-if="exportHistory.length" class="section-title">导出历史</div>
    <div v-for="(h, i) in exportHistory" :key="i" class="export-item">
      <span>{{ h.name }}</span>
      <span class="export-time">{{ h.time }}</span>
      <span class="export-status" :class="h.status">{{ h.status === 'ok' ? '✓' : '✗' }}</span>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { Toast } from 'vant'

const exportTypes = ref(['sensor'])
const exportFormat = ref('csv')
const startTime = ref('')
const endTime = ref('')
const exporting = ref(false)
const exportHistory = ref([])

async function doExport() {
  if (!exportTypes.value.length) {
    Toast.fail('请选择至少一种数据类型')
    return
  }
  exporting.value = true
  try {
    // 调用后端导出API
    const resp = await fetch('http://localhost:5000/api/export', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        types: exportTypes.value,
        format: exportFormat.value,
        start: startTime.value || undefined,
        end: endTime.value || undefined,
      }),
    })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const blob = await resp.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `car_data_export.${exportFormat.value === 'excel' ? 'xlsx' : 'zip'}`
    a.click()
    URL.revokeObjectURL(url)

    exportHistory.value.unshift({
      name: `${exportTypes.value.join('+')}.${exportFormat.value}`,
      time: new Date().toLocaleString('zh-CN'),
      status: 'ok',
    })
    Toast.success('导出成功')
  } catch (e) {
    exportHistory.value.unshift({
      name: exportTypes.value.join('+'),
      time: new Date().toLocaleString('zh-CN'),
      status: 'fail',
    })
    Toast.fail(`导出失败: ${e.message}`)
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.page { padding-bottom: 20px; }
.form-section { background: #fff; margin: 0 12px; border-radius: 10px; padding: 12px 0; }
.field-label { padding: 8px 16px 4px; font-size: 13px; font-weight: 600; color: #666; }
.export-item {
  display: flex; align-items: center; gap: 8px; margin: 4px 12px;
  background: #fff; border-radius: 8px; padding: 10px 12px; font-size: 13px;
}
.export-time { color: #999; margin-left: auto; }
.export-status { font-weight: 700; }
.export-status.ok { color: #67c23a; }
.export-status.fail { color: #f56c6c; }
</style>
