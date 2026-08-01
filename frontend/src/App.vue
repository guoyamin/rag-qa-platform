<template>
  <router-view />
</template>

<script setup lang="ts"></script>

<style>
* {
  margin: 0;
  padding: 0;
  box-sizing: border-box;
}

/* 亮色主题变量 */
:root {
  --bg-page: #f0f2f5;
  --bg-card: #fff;
  --bg-subtle: #f7f8fa;
  --text-primary: #1d2129;
  --text-secondary: #4e5969;
  --text-tertiary: #86909c;
  --border-color: #f0f2f5;
}

/* 暗色主题变量 */
html.dark {
  --bg-page: #141414;
  --bg-card: #1d1f27;
  --bg-subtle: #25262e;
  --text-primary: #e5e6eb;
  --text-secondary: #a8a8b3;
  --text-tertiary: #6b6e76;
  --border-color: #2a2d35;
}

html,
body,
#app {
  height: 100%;
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
  background: var(--bg-page);
  color: var(--text-primary);
  transition:
    background 0.3s ease,
    color 0.3s ease;
}
</style>
