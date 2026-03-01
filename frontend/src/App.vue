<script setup lang="ts">
import { useRoute } from 'vue-router'

const route = useRoute()

const navItems = [
  { path: '/', label: '仪表盘', icon: '📊' },
  { path: '/settings', label: '设置', icon: '⚙️' },
  { path: '/providers', label: 'AI 提供商', icon: '🤖' },
  { path: '/personas', label: '人格', icon: '🎭' },
  { path: '/napcat', label: 'NapCat', icon: '🐱' },
]
</script>

<template>
  <div class="app">
    <nav class="sidebar">
      <div class="logo">
        <h2>QQ Bot</h2>
        <small>控制台</small>
      </div>
      <ul>
        <li v-for="item in navItems" :key="item.path">
          <router-link
            :to="item.path"
            :class="{ active: route.path === item.path }"
          >
            <span class="icon">{{ item.icon }}</span>
            {{ item.label }}
          </router-link>
        </li>
      </ul>
    </nav>
    <main class="content">
      <router-view />
    </main>
  </div>
</template>

<style>
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  background: #f5f5f5;
  color: #333;
}
.app {
  display: flex;
  min-height: 100vh;
}
.sidebar {
  width: 220px;
  background: #1a1a2e;
  color: #fff;
  padding: 20px 0;
  flex-shrink: 0;
}
.logo {
  text-align: center;
  padding: 0 20px 20px;
  border-bottom: 1px solid #333;
}
.logo h2 { font-size: 1.4em; }
.logo small { color: #888; }
.sidebar ul { list-style: none; margin-top: 10px; }
.sidebar li a {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 24px;
  color: #ccc;
  text-decoration: none;
  transition: background 0.2s;
}
.sidebar li a:hover, .sidebar li a.active {
  background: #16213e;
  color: #fff;
}
.icon { font-size: 1.1em; }
.content {
  flex: 1;
  padding: 30px;
  max-width: 1000px;
}
h1 { margin-bottom: 20px; font-size: 1.6em; }
.card {
  background: #fff;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 16px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
.form-group {
  margin-bottom: 14px;
}
.form-group label {
  display: block;
  font-weight: 600;
  margin-bottom: 4px;
  font-size: 0.9em;
}
.form-group input, .form-group select, .form-group textarea {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid #ddd;
  border-radius: 6px;
  font-size: 0.95em;
}
.form-group textarea { resize: vertical; min-height: 80px; }
.btn {
  padding: 8px 20px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9em;
  transition: opacity 0.2s;
}
.btn:hover { opacity: 0.85; }
.btn-primary { background: #4361ee; color: #fff; }
.btn-danger { background: #e63946; color: #fff; }
.btn-success { background: #2a9d8f; color: #fff; }
.btn-sm { padding: 5px 12px; font-size: 0.85em; }
.badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 0.8em;
  font-weight: 600;
}
.badge-green { background: #d4edda; color: #155724; }
.badge-red { background: #f8d7da; color: #721c24; }
.badge-gray { background: #e9ecef; color: #495057; }
.flex { display: flex; }
.flex-between { display: flex; justify-content: space-between; align-items: center; }
.gap-8 { gap: 8px; }
.mt-10 { margin-top: 10px; }
.mb-10 { margin-bottom: 10px; }
</style>
