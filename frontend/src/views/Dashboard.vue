<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { getStatus } from '@/api/client'

const status = ref<Record<string, unknown> | null>(null)
const error = ref('')

function formatUptime(seconds: number): string {
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  return `${h}h ${m}m ${s}s`
}

async function fetchStatus() {
  try {
    const { data } = await getStatus()
    status.value = data
    error.value = ''
  } catch (e: any) {
    error.value = '无法连接后端'
  }
}

onMounted(fetchStatus)
</script>

<template>
  <div>
    <h1>仪表盘</h1>

    <div v-if="error" class="card" style="color: #e63946;">{{ error }}</div>

    <div v-if="status" class="flex gap-8" style="flex-wrap: wrap;">
      <div class="card" style="flex: 1; min-width: 200px;">
        <div style="font-size: 0.85em; color: #888;">运行时间</div>
        <div style="font-size: 1.4em; font-weight: 700; margin-top: 4px;">
          {{ formatUptime(status.uptime_seconds as number) }}
        </div>
      </div>
      <div class="card" style="flex: 1; min-width: 200px;">
        <div style="font-size: 0.85em; color: #888;">当前 AI 提供商</div>
        <div style="font-size: 1.2em; font-weight: 600; margin-top: 4px;">
          {{ status.active_provider || '未配置' }}
        </div>
      </div>
      <div class="card" style="flex: 1; min-width: 200px;">
        <div style="font-size: 0.85em; color: #888;">当前人格</div>
        <div style="font-size: 1.2em; font-weight: 600; margin-top: 4px;">
          {{ status.active_persona || '未配置' }}
        </div>
      </div>
    </div>

    <div v-if="status" class="flex gap-8" style="flex-wrap: wrap; margin-top: 4px;">
      <div class="card" style="flex: 1; min-width: 200px;">
        <div style="font-size: 0.85em; color: #888;">AI 提供商数</div>
        <div style="font-size: 1.4em; font-weight: 700; margin-top: 4px;">
          {{ status.providers_count }}
        </div>
      </div>
      <div class="card" style="flex: 1; min-width: 200px;">
        <div style="font-size: 0.85em; color: #888;">人格数</div>
        <div style="font-size: 1.4em; font-weight: 700; margin-top: 4px;">
          {{ status.personas_count }}
        </div>
      </div>
    </div>

    <button class="btn btn-primary mt-10" @click="fetchStatus">刷新状态</button>
  </div>
</template>
