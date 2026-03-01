import axios from 'axios'

const api = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// ── Status ──
export const getStatus = () => api.get('/status')

// ── Settings ──
export const getSettings = () => api.get('/settings')
export const updateSettings = (data: Record<string, unknown>) => api.put('/settings', data)

// ── Providers ──
export const listProviders = () => api.get('/providers')
export const createProvider = (data: Record<string, unknown>) => api.post('/providers', data)
export const updateProvider = (id: string, data: Record<string, unknown>) => api.put(`/providers/${id}`, data)
export const deleteProvider = (id: string) => api.delete(`/providers/${id}`)

// ── Personas ──
export const listPersonas = () => api.get('/personas')
export const createPersona = (data: Record<string, unknown>) => api.post('/personas', data)
export const updatePersona = (id: string, data: Record<string, unknown>) => api.put(`/personas/${id}`, data)
export const deletePersona = (id: string) => api.delete(`/personas/${id}`)

// ── NapCat ──
export const getNapCatStatus = () => api.get('/napcat/status')
export const startNapCat = () => api.post('/napcat/start')
export const stopNapCat = () => api.post('/napcat/stop')
export const getNapCatQRCode = () => api.get('/napcat/qrcode')
