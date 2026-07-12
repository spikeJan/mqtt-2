<template>
  <div id="app-root">
    <router-view v-slot="{ Component }">
      <keep-alive include="Dashboard,Charts,Video,Analysis">
        <component :is="Component" />
      </keep-alive>
    </router-view>
    <van-tabbar v-model="active" route safe-area-inset-bottom>
      <van-tabbar-item to="/" icon="gauge-o">仪表盘</van-tabbar-item>
      <van-tabbar-item to="/charts" icon="chart-trending-o">曲线</van-tabbar-item>
      <van-tabbar-item to="/video" icon="video-o">画面</van-tabbar-item>
      <van-tabbar-item to="/export" icon="down-o">导出</van-tabbar-item>
      <van-tabbar-item to="/analysis" icon="bar-chart-o">分析</van-tabbar-item>
    </van-tabbar>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRoute } from 'vue-router'

const route = useRoute()
const active = ref(0)

const tabMap = { '/': 0, '/charts': 1, '/video': 2, '/export': 3, '/analysis': 4 }
watch(() => route.path, (p) => { active.value = tabMap[p] ?? 0 }, { immediate: true })
</script>

<style>
html, body, #app, #app-root { height: 100%; margin: 0; padding: 0; }
#app-root { padding-bottom: 50px; box-sizing: border-box; overflow-y: auto; }
</style>
