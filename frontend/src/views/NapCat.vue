<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getNapCatStatus, startNapCat, stopNapCat, getNapCatQRCode, getSettings, updateSettings } from '@/api/client'

const status = ref<any>(null)
const qrcode = ref<any>(null)
const loading = ref(false)
const msg = ref('')
const qqAccount = ref('')
const savingAccount = ref(false)

async function fetchStatus() {
  try {
    const [{ data: s }, { data: settings }] = await Promise.all([getNapCatStatus(), getSettings()])
    status.value = s
    qqAccount.value = settings.qq_account || ''
  } catch {
    status.value = null
  }
}

async function saveQQAccount() {
  savingAccount.value = true
  try {
    await updateSettings({ qq_account: qqAccount.value.trim() })
    msg.value = 'QQ 账号已保存'
    setTimeout(() => { if (msg.value === 'QQ 账号已保存') msg.value = '' }, 2000)
  } catch {
    msg.value = '保存失败'
  }
  savingAccount.value = false
}

async function doStart() {
  loading.value = true
  msg.value = '正在启动 NapCat（关闭旧 QQ → 切换模式 → 启动），请稍候...'
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
    <h1>连接管理</h1>

    <div class="card">
      <div class="flex-between">
        <div>
          <strong>连接状态</strong>
          <span v-if="status" class="badge" :class="status.qq_login === true ? 'badge-green' : status.webui_reachable ? 'badge-green' : status.qq_running ? 'badge-gray' : 'badge-red'" style="margin-left: 8px;">
            {{ status.qq_login === true ? 'QQ 已登录' : status.webui_reachable ? (status.qq_login === false ? '运行中（QQ 未登录）' : '运行中') : status.qq_running ? 'QQ 已启动，WebUI 未就绪' : '已停止' }}
          </span>
        </div>
        <button class="btn btn-primary btn-sm" @click="fetchStatus">刷新</button>
      </div>

      <div v-if="status" style="margin-top: 8px; font-size: 0.85em; color: #666;">
        <div>QQ 模式:
          <span :style="{ color: status.napcat_mode ? '#2a9d8f' : '#e63946', fontWeight: 600 }">
            {{ status.napcat_mode ? 'NapCat 模式' : '普通模式' }}
          </span>
        </div>
        <div>WebUI:
          <span :style="{ color: status.webui_reachable ? '#2a9d8f' : '#e63946' }">
            {{ status.webui_reachable ? '可达' : '不可达' }}
          </span>
        </div>
        <div>QQ 登录:
          <span :style="{ color: status.qq_login === true ? '#2a9d8f' : status.qq_offline ? '#f4a261' : status.webui_reachable && status.qq_login === null ? '#666' : '#e63946', fontWeight: 600 }">
            {{ status.qq_login === true ? '已登录' : status.qq_offline ? '离线' : status.webui_reachable && status.qq_login === null ? '检测中...' : '未登录' }}
          </span>
        </div>
        <div v-if="status.login_error">登录提示: {{ status.login_error }}</div>
      </div>
    </div>

    <div class="card">
      <div class="form-group" style="margin-bottom: 0;">
        <label>QQ 账号 <span style="font-weight: 400; color: #888; font-size: 0.9em;">留空则启动时不指定账号，需要扫码登录</span></label>
        <div style="display: flex; gap: 8px;">
          <input v-model="qqAccount" placeholder="如 123456789" style="flex: 1;" />
          <button class="btn btn-success btn-sm" :disabled="savingAccount" @click="saveQQAccount">保存</button>
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
      <div v-if="qrcode.message" style="margin-top: 8px;" :style="{ color: qrcode.ok === false ? '#e63946' : '#555' }">
        {{ qrcode.message }}
      </div>
      <div v-if="qrcode.qrcode_image_api" style="margin-top: 10px;">
        <img
          :src="qrcode.qrcode_image_api"
          alt="QQ 登录二维码"
          style="width: 220px; height: 220px; border: 1px solid #ddd; border-radius: 8px; background: #fff;"
        />
        <div style="margin-top: 8px; color: #666; font-size: 0.85em;">
          请使用手机 QQ 扫码登录
        </div>
      </div>
    </div>
  </div>
</template>
