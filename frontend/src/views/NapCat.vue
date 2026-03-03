<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { getNapCatStatus, startNapCat, stopNapCat, getNapCatQRCode } from '@/api/client'

const status = ref<any>(null)
const qrcode = ref<any>(null)
const loading = ref(false)
const msg = ref('')
const qqAccount = ref('')
let pollTimer: ReturnType<typeof setInterval> | null = null

const hasAccount = computed(() => qqAccount.value.trim().length > 0)
const isRunning = computed(() => status.value?.webui_reachable === true)
const isLoggedIn = computed(() => status.value?.qq_login === true)

async function fetchStatus() {
  try {
    const { data } = await getNapCatStatus()
    status.value = data
  } catch {
    // 网络瞬断不清空状态，避免闪烁
  }
}

async function doStart() {
  if (!hasAccount.value) return
  loading.value = true
  msg.value = '正在启动 QQ 消息代理，请稍候...'
  try {
    const { data } = await startNapCat(qqAccount.value.trim())
    msg.value = data.message || (data.ok ? '启动成功' : '启动失败')
    await fetchStatus()
  } catch {
    msg.value = '启动请求失败'
  }
  loading.value = false
}

async function doStop() {
  loading.value = true
  msg.value = '正在停止...'
  try {
    const { data } = await stopNapCat()
    msg.value = data.message || '已停止'
    qrcode.value = null
    await fetchStatus()
  } catch {
    msg.value = '停止请求失败'
  }
  loading.value = false
}

async function doLogin() {
  loading.value = true
  msg.value = ''
  try {
    const { data } = await getNapCatQRCode()
    qrcode.value = data
    if (data.is_login) {
      msg.value = 'QQ 已登录'
    }
  } catch {
    qrcode.value = { ok: false, message: '获取二维码失败' }
  }
  loading.value = false
}

async function doLogout() {
  // 退出账号 = 停止再启动（不传 -q，清除登录态）
  loading.value = true
  msg.value = '正在退出账号...'
  qrcode.value = null
  try {
    await stopNapCat()
    await new Promise(r => setTimeout(r, 1000))
    const { data } = await startNapCat(qqAccount.value.trim())
    msg.value = data.ok ? '已退出账号，请重新登录' : data.message
    await fetchStatus()
  } catch {
    msg.value = '操作失败'
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

    <div class="card">
      <div class="flex-between">
        <div>
          <strong>连接状态</strong>
          <span v-if="status" class="badge"
            :class="isLoggedIn ? 'badge-green' : isRunning ? 'badge-green' : 'badge-red'"
            style="margin-left: 8px;">
            {{ isLoggedIn ? 'QQ 已登录' : isRunning ? '等待登录 QQ' : '未启动' }}
          </span>
        </div>
        <button class="btn btn-primary btn-sm" @click="fetchStatus">刷新</button>
      </div>

      <div v-if="status" style="margin-top: 8px; font-size: 0.85em; color: #666;">
        <div>NapCat: <span :style="{ color: status.napcat_mode ? '#2a9d8f' : '#e63946', fontWeight: 600 }">{{ status.napcat_mode ? '已启用' : '未启用' }}</span></div>
        <div>WebUI: <span :style="{ color: isRunning ? '#2a9d8f' : '#e63946' }">{{ isRunning ? '已连接' : '未连接' }}</span></div>
        <div>QQ 登录: <span :style="{ color: isLoggedIn ? '#2a9d8f' : '#e63946', fontWeight: 600 }">{{ isLoggedIn ? '已登录' : '未登录' }}</span></div>
        <div v-if="status.login_error">登录提示: {{ status.login_error }}</div>
      </div>
    </div>

    <div class="card">
      <div class="form-group" style="margin-bottom: 12px;">
        <label>QQ 账号</label>
        <input v-model="qqAccount" placeholder="请输入 QQ 号（必填）" />
      </div>

      <strong>操作</strong>
      <div style="margin-top: 6px; font-size: 0.85em; color: #888;">
        第一步：启动 QQ 消息代理 → 第二步：登录 QQ（扫码）
      </div>
      <div class="flex gap-8 mt-10">
        <!-- 启动 / 断开 -->
        <button v-if="!isRunning" class="btn btn-success" :disabled="loading || !hasAccount" @click="doStart">
          启动 QQ 消息代理
        </button>
        <button v-else class="btn btn-danger" :disabled="loading" @click="doStop">
          断开 QQ 消息代理
        </button>

        <!-- 登录 / 退出账号 -->
        <button v-if="!isLoggedIn" class="btn btn-primary" :disabled="loading || !isRunning || !hasAccount" @click="doLogin">
          登录 QQ
        </button>
        <button v-else class="btn btn-danger" :disabled="loading" @click="doLogout">
          退出账号
        </button>
      </div>

      <div v-if="!hasAccount" style="margin-top: 8px; color: #e63946; font-size: 0.85em;">
        请先填写 QQ 账号
      </div>
      <div v-if="msg" style="margin-top: 10px; color: #555;">{{ msg }}</div>
    </div>

    <div v-if="qrcode && !qrcode.is_login" class="card">
      <strong>登录二维码</strong>
      <div v-if="qrcode.message && !qrcode.qrcode_image_api" style="margin-top: 8px;"
        :style="{ color: qrcode.ok === false ? '#e63946' : '#555' }">
        {{ qrcode.message }}
      </div>
      <div v-if="qrcode.qrcode_image_api" style="margin-top: 10px;">
        <img :src="qrcode.qrcode_image_api" alt="QQ 登录二维码"
          style="width: 220px; height: 220px; border: 1px solid #ddd; border-radius: 8px; background: #fff;" />
        <div style="margin-top: 8px; color: #666; font-size: 0.85em;">
          请使用手机 QQ 扫码登录，登录后状态会自动刷新
        </div>
      </div>
    </div>
  </div>
</template>
