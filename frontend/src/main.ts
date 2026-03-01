import { createApp } from 'vue'
import { createRouter, createWebHistory } from 'vue-router'
import App from './App.vue'

const router = createRouter({
  history: createWebHistory('/web/'),
  routes: [
    { path: '/', name: 'dashboard', component: () => import('./views/Dashboard.vue') },
    { path: '/settings', name: 'settings', component: () => import('./views/Settings.vue') },
    { path: '/providers', name: 'providers', component: () => import('./views/Providers.vue') },
    { path: '/personas', name: 'personas', component: () => import('./views/Personas.vue') },
    { path: '/napcat', name: 'napcat', component: () => import('./views/NapCat.vue') },
  ],
})

createApp(App).use(router).mount('#app')
