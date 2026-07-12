<template>
  <div class="page">
    <div class="page-header">摄像头实时画面</div>

    <!-- RTSP → MJPEG 视频流 -->
    <div class="video-area" @click="captureSnapshot">
      <img v-if="mjpegUrl" :src="mjpegUrl" class="camera-view" alt="摄像头画面" />
      <div v-else class="no-signal">
        <div class="no-signal-icon">📷</div>
        <div>等待视频流...</div>
        <div class="no-signal-hint">请确认桥接程序已启动</div>
      </div>
      <div class="capture-hint" v-if="mjpegUrl">点击画面抓图</div>
    </div>

    <!-- 视频流设置 -->
    <div class="stream-settings" v-if="!mjpegUrl">
      <div class="field-label">MJPEG流地址</div>
      <van-field v-model="streamHost" label="IP:端口" placeholder="192.168.1.102:8080" />
      <van-button type="primary" block @click="connectStream" style="margin:8px 12px;">连接视频流</van-button>
    </div>

    <div class="section-title">云台角度</div>
    <div class="card-grid">
      <SensorCard label="水平角度" :value="gimbalH" unit="°" icon="↔" color="#e6a23c" />
      <SensorCard label="垂直角度" :value="gimbalV" unit="°" icon="↕" color="#e6a23c" />
    </div>

    <div class="captured-list" v-if="captured.length">
      <div class="section-title">已抓取图像 ({{ captured.length }})</div>
      <div class="capture-thumbs">
        <div v-for="(img, i) in captured" :key="i" class="thumb-item" @click="previewImage(img)">
          <img :src="img.data" class="thumb-img" />
          <span class="thumb-time">{{ img.time }}</span>
        </div>
      </div>
    </div>

    <van-image-preview v-model:show="showPreview" :images="previewImages" :startPosition="previewIndex" />
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted, computed } from 'vue'
import { subscribe, TOPICS } from '../services/mqtt.js'
import SensorCard from '../components/SensorCard.vue'

const gimbalH = ref('--')
const gimbalV = ref('--')
const captured = ref([])
const showPreview = ref(false)
const previewImages = ref([])
const previewIndex = ref(0)

// MJPEG流地址 — 从当前页面host自动推断
const streamHost = ref(window.location.hostname + ':8080')
const mjpegUrl = computed(() => {
  if (!streamHost.value) return null
  return `http://${streamHost.value}/camera/mjpeg`
})

// 默认自动连接视频流
function connectStream() {
  // 触发computed重新计算
  streamHost.value = streamHost.value.trim()
}

function captureSnapshot() {
  // 从snapshot接口获取当前帧
  const snapUrl = `http://${streamHost.value}/camera/snapshot`
  fetch(snapUrl)
    .then(r => r.blob())
    .then(blob => {
      const reader = new FileReader()
      reader.onload = () => {
        const t = new Date().toLocaleTimeString('zh-CN', { hour12: false })
        captured.value.unshift({ data: reader.result, time: t })
        if (captured.value.length > 20) captured.value.pop()
      }
      reader.readAsDataURL(blob)
    })
    .catch(() => {})
}

function previewImage(img) {
  previewImages.value = captured.value.map(c => c.data)
  previewIndex.value = captured.value.indexOf(img)
  showPreview.value = true
}

let unsubs = []

onMounted(() => {
  unsubs.push(subscribe(TOPICS.gimbal, (data) => {
    if (data && typeof data === 'object') {
      gimbalH.value = data.horizontal ?? gimbalH.value
      gimbalV.value = data.vertical ?? gimbalV.value
    }
  }))
})

onUnmounted(() => unsubs.forEach(fn => fn()))
</script>

<style scoped>
.page { padding-bottom: 20px; }
.video-area {
  position: relative; margin: 0 12px; border-radius: 12px; overflow: hidden;
  background: #000; min-height: 260px; display: flex; align-items: center; justify-content: center;
}
.camera-view { width: 100%; display: block; }
.no-signal { color: #666; text-align: center; }
.no-signal-icon { font-size: 48px; margin-bottom: 8px; }
.no-signal-hint { font-size: 12px; color: #999; margin-top: 4px; }
.capture-hint {
  position: absolute; bottom: 8px; left: 50%; transform: translateX(-50%);
  background: rgba(0,0,0,.5); color: #fff; font-size: 12px; padding: 4px 12px; border-radius: 12px;
}
.stream-settings { background: #fff; margin: 8px 12px; border-radius: 10px; padding: 8px 0; }
.field-label { padding: 8px 16px 2px; font-size: 13px; color: #666; font-weight: 600; }
.capture-thumbs { display: flex; gap: 8px; padding: 0 12px; overflow-x: auto; }
.thumb-item { flex-shrink: 0; width: 80px; text-align: center; }
.thumb-img { width: 80px; height: 60px; object-fit: cover; border-radius: 6px; }
.thumb-time { font-size: 10px; color: #999; }
</style>
