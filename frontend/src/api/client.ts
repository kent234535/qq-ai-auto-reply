import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// ── Settings ──
export const getSettings = () => api.get('/settings')
export const updateSettings = (data: Record<string, unknown>) => api.put('/settings', data)

// ── Providers ──
export const listProviders = () => api.get('/providers')
export const createProvider = (data: Record<string, unknown>) => api.post('/providers', data)
export const updateProvider = (id: string, data: Record<string, unknown>) => api.put(`/providers/${id}`, data)
export const updateProviderModelKey = (id: string, data: Record<string, unknown>) =>
  api.patch(`/providers/${id}/model-key`, data)
export const deleteProvider = (id: string) => api.delete(`/providers/${id}`)
export const listAvailableModels = (data: Record<string, unknown>) =>
  api.post('/providers/list-models', data, { timeout: 20000 })
export const listProviderModels = (id: string) =>
  api.get(`/providers/${id}/models`, { timeout: 20000 })
export const getProviderRawKey = (id: string) => api.get(`/providers/${id}/raw-key`)
export const testProviderModel = (id: string, data?: Record<string, unknown>) =>
  api.post(`/providers/${id}/test`, data || null, { timeout: 20000 })

// ── Personas ──
export const listPersonas = () => api.get('/personas')
export const createPersona = (data: Record<string, unknown>) => api.post('/personas', data)
export const updatePersona = (id: string, data: Record<string, unknown>) => api.put(`/personas/${id}`, data)
export const deletePersona = (id: string) => api.delete(`/personas/${id}`)

// ── NapCat ──
export const getNapCatStatus = () => api.get('/napcat/status')
export const startNapCat = () => api.post('/napcat/start', null, { timeout: 60000 })
export const stopNapCat = () => api.post('/napcat/stop', null, { timeout: 30000 })
export const getNapCatQRCode = () => api.get('/napcat/qrcode')
