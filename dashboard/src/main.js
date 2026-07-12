import { createApp } from 'vue'
import { createRouter, createWebHashHistory } from 'vue-router'
import App from './App.vue'
import 'vant/lib/index.css'
import './assets/main.css'

import Dashboard from './views/Dashboard.vue'
import SensorCharts from './views/SensorCharts.vue'
import VideoFeed from './views/VideoFeed.vue'
import DataExport from './views/DataExport.vue'
import Analysis from './views/Analysis.vue'

const routes = [
  { path: '/', name: 'Dashboard', component: Dashboard, meta: { title: '仪表盘' } },
  { path: '/charts', name: 'Charts', component: SensorCharts, meta: { title: '曲线' } },
  { path: '/video', name: 'Video', component: VideoFeed, meta: { title: '画面' } },
  { path: '/export', name: 'Export', component: DataExport, meta: { title: '导出' } },
  { path: '/analysis', name: 'Analysis', component: Analysis, meta: { title: '分析' } },
]

const router = createRouter({
  history: createWebHashHistory(),
  routes,
})

const app = createApp(App)
app.use(router)
app.mount('#app')
