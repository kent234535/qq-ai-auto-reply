<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { listProviders, createProvider, updateProvider, deleteProvider, getProviderRawKey, testProviderModel, getSettings, updateSettings } from '@/api/client'

const providers = ref<any[]>([])
const activeProviderId = ref('')
const showForm = ref(false)
const form = ref({
  name: '',
  type: 'openai_compat',
  base_url: '',
  api_key: '',
  model: '',
  enabled: true,
})

// 编辑表单
const editingId = ref('')
const editForm = ref({
  name: '',
  type: 'openai_compat',
  base_url: '',
  api_key: '',
  model: '',
})
const savingEdit = ref(false)

// 检测模型
const testingId = ref('')
const testResult = ref<{ ok: boolean; msg: string } | null>(null)

async function load() {
  const [p, s] = await Promise.all([listProviders(), getSettings()])
  providers.value = p.data
  activeProviderId.value = s.data.active_provider_id || ''
}

function resetForm() {
  form.value = { name: '', type: 'openai_compat', base_url: '', api_key: '', model: '', enabled: true }
}

async function save() {
  if (!form.value.name) return
  await createProvider(form.value)
  showForm.value = false
  resetForm()
  await load()
}

async function remove(id: string) {
  if (!confirm('确认删除该模型？')) return
  await deleteProvider(id)
  if (activeProviderId.value === id) {
    await updateSettings({ active_provider_id: '' })
  }
  await load()
}

async function activate(id: string) {
  await updateSettings({ active_provider_id: id })
  activeProviderId.value = id
}

async function startEdit(p: any) {
  editingId.value = p.id
  editForm.value = {
    name: p.name,
    type: p.type,
    base_url: p.base_url || '',
    api_key: '',
    model: p.model || '',
  }
  testResult.value = null
  testingId.value = ''
  try {
    const { data } = await getProviderRawKey(p.id)
    editForm.value.api_key = data.api_key || ''
  } catch {}
}

function cancelEdit() {
  editingId.value = ''
}

async function saveEditForm(id: string) {
  if (!editForm.value.name) return
  savingEdit.value = true
  try {
    await updateProvider(id, editForm.value)
    cancelEdit()
    await load()
  } finally {
    savingEdit.value = false
  }
}

async function testModel(id: string) {
  testingId.value = id
  testResult.value = null
  try {
    await testProviderModel(id, {
      type: editForm.value.type,
      base_url: editForm.value.base_url,
      api_key: editForm.value.api_key,
      model: editForm.value.model,
    })
    testResult.value = { ok: true, msg: '模型可用' }
  } catch (e: any) {
    testResult.value = { ok: false, msg: e.response?.data?.detail || '检测失败' }
  }
}

onMounted(load)
</script>

<template>
  <div>
    <div class="flex-between mb-10">
      <h1>模型</h1>
      <button class="btn btn-primary" @click="showForm = !showForm">
        {{ showForm ? '取消' : '+ 添加模型' }}
      </button>
    </div>

    <div v-if="showForm" class="card">
      <div class="form-group">
        <label>名称</label>
        <input v-model="form.name" placeholder="如 DeepSeek" />
      </div>
      <div class="form-group">
        <label>类型</label>
        <select v-model="form.type">
          <option value="openai_compat">OpenAI 兼容</option>
          <option value="claude">Anthropic Claude</option>
        </select>
      </div>
      <div class="form-group">
        <label>Base URL</label>
        <input v-model="form.base_url" placeholder="https://api.deepseek.com/v1" />
      </div>
      <div class="form-group">
        <label>API Key</label>
        <input v-model="form.api_key" type="password" placeholder="sk-..." />
      </div>
      <div class="form-group">
        <div style="font-size: 0.8em; color: #888; margin-bottom: 4px;">请查阅 API 提供方的官方文档查看可用模型的完整字段</div>
        <label>模型</label>
        <input v-model="form.model" placeholder="如 deepseek-chat" />
      </div>
      <button class="btn btn-success" @click="save">保存</button>
    </div>

    <div v-for="p in providers" :key="p.id" class="card" :style="activeProviderId === p.id ? 'border: 2px solid #a8e6cf;' : ''">
      <div class="flex-between">
        <div>
          <strong>{{ p.name }}</strong>
          <span v-if="activeProviderId === p.id" class="badge badge-green" style="margin-left: 8px;">当前启用</span>
          <span class="badge badge-gray" style="margin-left: 4px;">{{ p.type }}</span>
        </div>
        <div style="display: flex; gap: 8px;">
          <button v-if="activeProviderId !== p.id" class="btn btn-success btn-sm" @click="activate(p.id)">启用</button>
          <button class="btn btn-primary btn-sm" @click="startEdit(p)">编辑</button>
          <button class="btn btn-danger btn-sm" @click="remove(p.id)">删除</button>
        </div>
      </div>
      <div style="margin-top: 8px; font-size: 0.85em; color: #666;">
        模型: {{ p.model || '未设置' }} &nbsp;|&nbsp;
        API Key: {{ p.api_key || '未设置' }}
      </div>

      <div v-if="editingId === p.id" style="margin-top: 12px; border-top: 1px dashed #ddd; padding-top: 10px;">
        <div class="form-group">
          <label>名称</label>
          <input v-model="editForm.name" />
        </div>
        <div class="form-group">
          <label>类型</label>
          <select v-model="editForm.type">
            <option value="openai_compat">OpenAI 兼容</option>
            <option value="claude">Anthropic Claude</option>
          </select>
        </div>
        <div class="form-group">
          <label>Base URL</label>
          <input v-model="editForm.base_url" />
        </div>
        <div class="form-group">
          <label>API Key</label>
          <input v-model="editForm.api_key" type="password" />
        </div>
        <div class="form-group">
          <div style="font-size: 0.8em; color: #888; margin-bottom: 4px;">请查阅 API 提供方的官方文档查看可用模型的完整字段</div>
          <label>模型</label>
          <div style="display: flex; gap: 8px;">
            <input v-model="editForm.model" placeholder="如 deepseek-chat" style="flex: 1;" />
            <button class="btn btn-primary btn-sm" :disabled="testingId === p.id && !testResult" @click="testModel(p.id)">
              {{ testingId === p.id && !testResult ? '检测中...' : '检测模型可用性' }}
            </button>
          </div>
          <div v-if="testingId === p.id && testResult" style="margin-top: 6px; font-size: 0.85em; font-weight: 600;"
            :style="{ color: testResult.ok ? '#2a9d8f' : '#e63946' }">
            {{ testResult.msg }}
          </div>
        </div>
        <div style="display: flex; gap: 8px;">
          <button class="btn btn-success btn-sm" :disabled="savingEdit" @click="saveEditForm(p.id)">保存修改</button>
          <button class="btn btn-primary btn-sm" :disabled="savingEdit" @click="cancelEdit">取消</button>
        </div>
      </div>
    </div>

    <div v-if="!providers.length" class="card" style="color: #888; text-align: center;">
      暂无模型，点击上方按钮添加
    </div>
  </div>
</template>
