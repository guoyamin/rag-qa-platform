<template>
  <div class="error-page">
    <div class="error-content">
      <h1 class="error-code">404</h1>
      <p>抱歉，您访问的页面不存在</p>
      <el-button type="primary" class="back-btn" @click="$router.push('/')"> 返回首页 </el-button>
    </div>
  </div>
</template>

<style scoped lang="scss">
.error-page {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 100vh;
  background: var(--bg-page);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

.error-content {
  text-align: center;

  .error-code {
    font-size: 140px;
    font-weight: 700;
    line-height: 1;
    margin-bottom: 16px;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    -webkit-background-clip: text;
    background-clip: text;
    -webkit-text-fill-color: transparent;
  }

  p {
    font-size: 18px;
    color: var(--text-secondary);
    margin-bottom: 28px;
  }

  .back-btn {
    height: 44px;
    padding: 0 28px;
    font-size: 15px;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    box-shadow: 0 4px 12px rgba(45, 108, 223, 0.3);

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 16px rgba(45, 108, 223, 0.4);
    }
  }
}
</style>
