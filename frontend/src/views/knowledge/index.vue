<template>
  <div class="placeholder-page">
    <div class="placeholder-card">
      <div class="placeholder-icon">
        <el-icon :size="40" color="#fff">
          <Collection />
        </el-icon>
      </div>
      <h3>知识库管理</h3>
      <p>该功能正在开发中，敬请期待</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Collection } from '@element-plus/icons-vue'
</script>

<style scoped lang="scss">
.placeholder-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: calc(100vh - 100px);
}

.placeholder-card {
  text-align: center;
  padding: 48px 40px;
  background: var(--bg-card);
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.06);

  .placeholder-icon {
    width: 80px;
    height: 80px;
    margin: 0 auto 20px;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(45, 108, 223, 0.3);
  }

  h3 {
    font-size: 18px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 8px;
  }

  p {
    font-size: 14px;
    color: var(--text-tertiary);
  }
}
</style>
