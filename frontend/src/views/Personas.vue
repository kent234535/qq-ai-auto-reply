<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listPersonas, createPersona, updatePersona, deletePersona, getSettings, updateSettings } from '@/api/client'

const personas = ref<any[]>([])
const activePersonaId = ref('')
const showForm = ref(false)
const form = ref({ name: '', system_prompt: '' })

const editingId = ref('')
const editForm = ref({ name: '', system_prompt: '' })

async function load() {
  const [pe, s] = await Promise.all([listPersonas(), getSettings()])
  personas.value = pe.data
  activePersonaId.value = s.data.active_persona_id || ''
}

function resetForm() {
  form.value = { name: '', system_prompt: '' }
}

async function save() {
  if (!form.value.name || !form.value.system_prompt) return
  await createPersona(form.value)
  showForm.value = false
  resetForm()
  await load()
}

async function remove(id: string) {
  if (!confirm('确认删除该角色？')) return
  try {
    await deletePersona(id)
  } catch (e: any) {
    alert(e.response?.data?.detail || '删除失败')
  }
  if (activePersonaId.value === id) {
    await updateSettings({ active_persona_id: '' })
  }
  await load()
}

async function activate(id: string) {
  await updateSettings({ active_persona_id: id })
  activePersonaId.value = id
}

function startEdit(p: any) {
  editingId.value = p.id
  editForm.value = { name: p.name, system_prompt: p.system_prompt }
}

function cancelEdit() {
  editingId.value = ''
}

async function saveEdit(id: string) {
  if (!editForm.value.name || !editForm.value.system_prompt) return
  await updatePersona(id, editForm.value)
  editingId.value = ''
  await load()
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex-between mb-10">
      <h1>角色管理</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? '取消' : '+ 添加角色' }}
      </button>
    </div>

    <div v-if="showForm" class="card">
      <div class="form-group">
        <label>名称</label>
        <input v-model="form.name" placeholder="如 傲娇少女" />
      </div>
      <div class="form-group">
        <label>角色描述</label>
        <textarea v-model="form.system_prompt" placeholder="你是一个..." rows="4"></textarea>
      </div>
      <button class="btn btn-success" @click="save">保存</button>
    </div>

    <div v-for="p in personas" :key="p.id" class="card" :style="activePersonaId === p.id ? 'border: 2px solid #a8e6cf;' : ''">
      <div class="flex-between">
        <div>
          <strong>{{ p.name }}</strong>
          <span v-if="activePersonaId === p.id" class="badge badge-green" style="margin-left: 8px;">当前启用</span>
        </div>
        <div style="display: flex; gap: 8px;">
          <button v-if="activePersonaId !== p.id" class="btn btn-success btn-sm" @click="activate(p.id)">启用</button>
          <button class="btn btn-primary btn-sm" @click="startEdit(p)">编辑</button>
          <button class="btn btn-danger btn-sm" @click="remove(p.id)">删除</button>
        </div>
      </div>

      <div v-if="editingId === p.id" style="margin-top: 12px; border-top: 1px dashed #ddd; padding-top: 10px;">
        <div class="form-group">
          <label>名称</label>
          <input v-model="editForm.name" />
        </div>
        <div class="form-group">
          <label>角色描述</label>
          <textarea v-model="editForm.system_prompt" rows="4"></textarea>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-success btn-sm" @click="saveEdit(p.id)">保存修改</button>
          <button class="btn btn-primary btn-sm" @click="cancelEdit">取消</button>
        </div>
      </div>

      <div v-else style="margin-top: 8px; padding: 10px; background: #f8f9fa; border-radius: 6px; font-size: 0.85em; white-space: pre-wrap;">{{ p.system_prompt }}</div>
    </div>
  </div>
</template>
