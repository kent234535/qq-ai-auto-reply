<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listPersonas, createPersona, deletePersona } from '@/api/client'

const personas = ref<any[]>([])
const showForm = ref(false)
const form = ref({
  id: '',
  name: '',
  system_prompt: '',
  description: '',
  builtin: false,
})

async function load() {
  const { data } = await listPersonas()
  personas.value = data
}

function resetForm() {
  form.value = { id: '', name: '', system_prompt: '', description: '', builtin: false }
}

async function save() {
  if (!form.value.id || !form.value.name || !form.value.system_prompt) return
  await createPersona(form.value)
  showForm.value = false
  resetForm()
  await load()
}

async function remove(id: string) {
  if (!confirm('确认删除该人格？')) return
  try {
    await deletePersona(id)
  } catch (e: any) {
    alert(e.response?.data?.detail || '删除失败')
  }
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex-between mb-10">
      <h1>人格管理</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? '取消' : '+ 添加人格' }}
      </button>
    </div>

    <div v-if="showForm" class="card">
      <div class="form-group">
        <label>ID（唯一标识）</label>
        <input v-model="form.id" placeholder="如 tsundere" />
      </div>
      <div class="form-group">
        <label>名称</label>
        <input v-model="form.name" placeholder="如 傲娇少女" />
      </div>
      <div class="form-group">
        <label>描述</label>
        <input v-model="form.description" placeholder="简短描述" />
      </div>
      <div class="form-group">
        <label>System Prompt</label>
        <textarea v-model="form.system_prompt" placeholder="你是一个..." rows="4"></textarea>
      </div>
      <button class="btn btn-success" @click="save">保存</button>
    </div>

    <div v-for="p in personas" :key="p.id" class="card">
      <div class="flex-between">
        <div>
          <strong>{{ p.name }}</strong>
          <span v-if="p.builtin" class="badge badge-gray" style="margin-left: 8px;">内置</span>
        </div>
        <button v-if="!p.builtin" class="btn btn-danger btn-sm" @click="remove(p.id)">删除</button>
      </div>
      <div v-if="p.description" style="margin-top: 4px; font-size: 0.85em; color: #666;">
        {{ p.description }}
      </div>
      <div style="margin-top: 8px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 0.85em; white-space: pre-wrap;">{{ p.system_prompt }}</div>
    </div>
  </div>
</template>
