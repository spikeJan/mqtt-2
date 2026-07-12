import mqtt from 'mqtt'

const WS_HOST = window.location.hostname || 'localhost'
const BROKER_URL = `ws://${WS_HOST}:9001`

const TOPICS = {
  allSensors: 'car/sensors/all',
  roll: 'car/sensors/roll',
  pitch: 'car/sensors/pitch',
  yaw: 'car/sensors/yaw',
  speed: 'car/sensors/speed',
  servo1: 'car/sensors/servo1',
  co: 'car/sensors/co',
  co2: 'car/sensors/co2',
  gimbal: 'car/sensors/gimbal',
  alert: 'car/alerts',
}

let client = null
const listeners = new Map()
const connectCallbacks = new Set()

export function isConnected() {
  return client ? client.connected : false
}

export function onConnected(cb) {
  connectCallbacks.add(cb)
  if (client && client.connected) cb(true)
  return () => connectCallbacks.delete(cb)
}

function getClient() {
  if (!client) {
    client = mqtt.connect(BROKER_URL, {
      keepalive: 30,
      clean: true,
      reconnectPeriod: 3000,
    })

    client.on('connect', () => {
      console.log('MQTT已连接')
      connectCallbacks.forEach(cb => cb(true))
      Object.values(TOPICS).forEach(t => client.subscribe(t))
    })

    client.on('message', (topic, payload) => {
      const cbs = listeners.get(topic)
      if (cbs) {
        let data = payload.toString()
        try { data = JSON.parse(data) } catch (_) { /* keep string */ }
        cbs.forEach(cb => cb(data))
      }
    })

    client.on('error', (e) => console.error('MQTT错误:', e))
    client.on('reconnect', () => console.log('MQTT重连中...'))
    client.on('close', () => {
      console.log('MQTT已断开')
      connectCallbacks.forEach(cb => cb(false))
    })
  }
  return client
}

export function subscribe(topic, callback) {
  getClient()
  if (!listeners.has(topic)) listeners.set(topic, new Set())
  listeners.get(topic).add(callback)
  return () => {
    const cbs = listeners.get(topic)
    if (cbs) {
      cbs.delete(callback)
      if (cbs.size === 0) listeners.delete(topic)
    }
  }
}

export function unsubscribeAll() {
  listeners.clear()
  if (client) {
    client.end(true)
    client = null
  }
}

export { TOPICS }
