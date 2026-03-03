<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getNapCatStatus, connectNapCat, disconnectNapCat, setNapCatApp, getNapCatQRCode } from '@/api/client'

const status = ref<any>(null)
const qrcode = ref<any>(null)
const loading = ref(false)
const msg = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const connected = computed(() => status.value?.connected === true)
const webuiReady = computed(() => status.value?.webui_reachable === true)
const apps = computed(() => status.value?.apps || [])
const activeExe = computed(() => status.value?.active_exe || '')
const napcatInstalled = computed(() => status.value?.napcat_installed !== false)

async function fetchStatus() {
  try {
    const { data } = await getNapCatStatus()
    status.value = data
  } catch {
    // 网络瞬断不清空状态
  }
}

async function doConnect() {
  loading.value = true
  msg.value = '正在连接，请稍候...'
  qrcode.value = null
  try {
    const { data } = await connectNapCat()
    if (data.qrcode_image_api || data.qrcode_url) {
      // 返回了二维码
      qrcode.value = data
      msg.value = data.message || '请使用手机 QQ 扫码登录'
    } else if (data.is_login) {
      msg.value = 'QQ 已连接并登录'
    } else {
      msg.value = data.message || (data.ok ? '连接成功' : '连接失败')
    }
    await fetchStatus()
  } catch {
    msg.value = '连接请求失败，请检查网络'
  }
  loading.value = false
}

async function doDisconnect() {
  loading.value = true
  msg.value = '正在断开...'
  qrcode.value = null
  try {
    const { data } = await disconnectNapCat()
    msg.value = data.message || '已断开'
    await fetchStatus()
  } catch {
    msg.value = '断开请求失败'
  }
  loading.value = false
}

async function doRefreshQR() {
  loading.value = true
  try {
    const { data } = await getNapCatQRCode()
    if (data.is_login) {
      qrcode.value = null
      msg.value = 'QQ 已登录'
      await fetchStatus()
    } else {
      qrcode.value = data
      msg.value = data.message || ''
    }
  } catch {
    msg.value = '获取二维码失败'
  }
  loading.value = false
}

async function doSwitchApp(exe: string) {
  if (exe === activeExe.value) return
  loading.value = true
  qrcode.value = null
  msg.value = ''
  try {
    const { data } = await setNapCatApp(exe)
    msg.value = data.message || ''
    await fetchStatus()
  } catch {
    msg.value = '切换失败'
  }
  loading.value = false
}

onMounted(() => {
  fetchStatus()
  pollTimer = setInterval(fetchStatus, 5000)
})

onUnmounted(() => {
  if (pollTimer) clearInterval(pollTimer)
})
</script>

<template>
  <div>
    <h1>连接管理</h1>

    <!-- 状态卡片 -->
    <div class="card">
      <div class="flex-between">
        <div>
          <strong>连接状态</strong>
          <span v-if="status" class="badge" style="margin-left: 8px;"
            :class="connected ? 'badge-green' : 'badge-red'">
            {{ connected ? '已连接' : '未连接' }}
          </span>
        </div>
      </div>

      <!-- QQ 应用选择 -->
      <div v-if="apps.length > 0" style="margin-top: 12px;">
        <label style="font-size: 0.85em; color: #666;">QQ 应用</label>
        <div class="flex gap-8 mt-10" style="flex-wrap: wrap;">
          <button v-for="app in apps" :key="app.exe"
            class="btn btn-sm"
            :class="app.exe === activeExe ? 'btn-primary' : 'btn-outline'"
            :disabled="loading"
            :title="app.exe"
            @click="doSwitchApp(app.exe)">
            {{ app.name }}
          </button>
        </div>
      </div>
    </div>

    <!-- 操作卡片 -->
    <div class="card">
      <div class="flex gap-8">
        <button v-if="!connected" class="btn btn-success" :disabled="loading || !napcatInstalled" @click="doConnect">
          连接
        </button>
        <button v-if="webuiReady || connected" class="btn btn-danger" :disabled="loading" @click="doDisconnect">
          断开连接
        </button>
      </div>
      <div v-if="!napcatInstalled" style="margin-top: 8px; color: #e63946; font-size: 0.85em;">
        未检测到 NapCat，请先安装 NapCat
      </div>
      <div v-if="msg" style="margin-top: 10px; color: #555; white-space: pre-line;">{{ msg }}</div>
    </div>

    <!-- 二维码卡片 -->
    <div v-if="qrcode && !qrcode.is_login" class="card">
      <div class="flex-between">
        <strong>扫码登录</strong>
        <button class="btn btn-primary btn-sm" :disabled="loading" @click="doRefreshQR">
          刷新二维码
        </button>
      </div>
      <div v-if="qrcode.message && !qrcode.qrcode_image_api" style="margin-top: 8px;"
        :style="{ color: qrcode.ok === false ? '#e63946' : '#555' }">
        {{ qrcode.message }}
      </div>
      <div v-if="qrcode.qrcode_image_api" style="margin-top: 10px;">
        <img :src="qrcode.qrcode_image_api" alt="QQ 登录二维码"
          style="width: 220px; height: 220px; border: 1px solid #ddd; border-radius: 8px; background: #fff;" />
      </div>
    </div>
  </div>
</template>
