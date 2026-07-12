import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { VitePWA } from 'vite-plugin-pwa'
import Components from 'unplugin-vue-components/vite'
import { VantResolver } from '@vant/auto-import-resolver'

export default defineConfig({
  plugins: [
    vue(),
    Components({ resolvers: [VantResolver()] }),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: '管道探测小车数据展板',
        short_name: '小车展板',
        description: 'MQTT实时数据监控',
        theme_color: '#1989fa',
        background_color: '#f5f5f5',
        display: 'standalone',
        orientation: 'portrait',
        icons: [
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png' }
        ]
      },
      workbox: { globPatterns: ['**/*.{js,css,html,png,svg}'] }
    })
  ],
  server: { host: '0.0.0.0', port: 5173 }
})
