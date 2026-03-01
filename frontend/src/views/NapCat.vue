<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getNapCatStatus, startNapCat, stopNapCat, getNapCatQRCode } from '@/api/client'

const status = ref<any>(null)
const qrcode = ref<any>(null)
const loading = ref(false)
const msg = ref('')

async function fetchStatus() {
  try {
    const { data } = await getNapCatStatus()
    status.value = data
  } catch {
    status.value = null
  }
}

async function doStart() {
  loading.value = true
  msg.value = '正在启动 NapCat...'
  try {
    const { data } = await startNapCat()
    msg.value = data.message || (data.ok ? '启动成功' : '启动失败')
    await fetchStatus()
  } catch {
    msg.value = '启动请求失败'
  }
  loading.value = false
}

async function doStop() {
  loading.value = true
  try {
    const { data } = await stopNapCat()
    msg.value = data.message || '已停止'
    await fetchStatus()
  } catch {
    msg.value = '停止请求失败'
  }
  loading.value = false
}

async function fetchQRCode() {
  try {
    const { data } = await getNapCatQRCode()
    qrcode.value = data
  } catch {
    qrcode.value = { ok: false, message: '获取二维码失败' }
  }
}

onMounted(fetchStatus)
</script>

<template>
  <div>
    <h1>NapCat 管理</h1>

    <div class="card">
      <div class="flex-between">
        <div>
          <strong>NapCat 状态</strong>
          <span v-if="status" class="badge" :class="status.process_running ? 'badge-green' : 'badge-red'" style="margin-left: 8px;">
            {{ status.process_running ? '运行中' : '已停止' }}
          </span>
        </div>
        <button class="btn btn-primary btn-sm" @click="fetchStatus">刷新</button>
      </div>

      <div v-if="status" style="margin-top: 8px; font-size: 0.85em; color: #666;">
        <div v-if="status.pid">PID: {{ status.pid }}</div>
        <div>WebUI:
          <span :style="{ color: status.webui_reachable ? '#2a9d8f' : '#e63946' }">
            {{ status.webui_reachable ? '可达' : '不可达' }}
          </span>
        </div>
      </div>
    </div>

    <div class="card">
      <strong>操作</strong>
      <div class="flex gap-8 mt-10">
        <button class="btn btn-success" @click="doStart" :disabled="loading">启动 NapCat</button>
        <button class="btn btn-danger" @click="doStop" :disabled="loading">停止 NapCat</button>
        <button class="btn btn-primary" @click="fetchQRCode" :disabled="loading">获取登录二维码</button>
      </div>
      <div v-if="msg" style="margin-top: 10px; color: #555;">{{ msg }}</div>
    </div>

    <div v-if="qrcode" class="card">
      <strong>登录二维码</strong>
      <div v-if="qrcode.ok === false" style="margin-top: 8px; color: #e63946;">
        {{ qrcode.message }}
      </div>
      <div v-else style="margin-top: 8px;">
        <pre style="background: #f8f9fa; padding: 12px; border-radius: 6px; font-size: 0.85em; overflow: auto;">{{ JSON.stringify(qrcode, null, 2) }}</pre>
      </div>
    </div>
  </div>
</template>
