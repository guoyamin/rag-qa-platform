<template>
  <div class="login-page">
    <!-- 左侧品牌区 -->
    <div class="login-brand">
      <div class="brand-decoration">
        <div class="deco-circle deco-1" />
        <div class="deco-circle deco-2" />
        <div class="deco-circle deco-3" />
        <div class="deco-grid" />
      </div>
      <div class="brand-content">
        <div class="logo-placeholder">
          <el-icon :size="44" color="#fff">
            <OfficeBuilding />
          </el-icon>
        </div>
        <h1 class="brand-title">企业知识库问答平台</h1>
        <p class="brand-subtitle">智能问答平台</p>
        <div class="brand-features">
          <div class="feature-item">
            <el-icon :size="22">
              <ChatDotRound />
            </el-icon>
            <span>AI智能问答</span>
          </div>
          <div class="feature-item">
            <el-icon :size="22">
              <Collection />
            </el-icon>
            <span>知识库管理</span>
          </div>
          <div class="feature-item">
            <el-icon :size="22">
              <Document />
            </el-icon>
            <span>企业文档检索</span>
          </div>
        </div>
      </div>
    </div>

    <!-- 右侧登录表单 -->
    <div class="login-form-wrapper">
      <div class="login-form-container">
        <div class="form-header">
          <h2>欢迎登录</h2>
          <p>请使用您的工号和密码登录系统</p>
        </div>

        <el-form
          ref="formRef"
          :model="loginForm"
          :rules="rules"
          class="login-form"
          @keyup.enter="handleLogin"
        >
          <el-form-item prop="username">
            <el-input
              v-model="loginForm.username"
              placeholder="请输入工号/用户名"
              size="large"
              :prefix-icon="User"
              clearable
            />
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="loginForm.password"
              type="password"
              placeholder="请输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
              clearable
            />
          </el-form-item>

          <el-form-item prop="auth_type">
            <el-radio-group v-model="loginForm.auth_type">
              <el-radio label=""> 自动识别 </el-radio>
              <el-radio label="local"> 本地账号 </el-radio>
              <el-radio label="ldap"> 企业认证 </el-radio>
            </el-radio-group>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              size="large"
              class="login-btn"
              :loading="loading"
              @click="handleLogin"
            >
              登 录
            </el-button>
          </el-form-item>
        </el-form>

        <div class="form-footer">
          <p>
            <el-icon><Warning /></el-icon>
            如遇登录问题，请联系系统管理员
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  ChatDotRound,
  Collection,
  Document,
  OfficeBuilding,
  User,
  Lock,
  Warning,
} from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import type { FormInstance, FormRules } from 'element-plus'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const loginForm = reactive({
  username: 'admin',
  password: 'Admin@123',
  auth_type: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入工号/用户名', trigger: 'blur' },
    { min: 2, max: 64, message: '长度在2到64个字符', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 1, max: 128, message: '长度在1到128个字符', trigger: 'blur' },
  ],
}

const handleLogin = async () => {
  if (!formRef.value) return

  await formRef.value.validate(async valid => {
    if (!valid) return

    loading.value = true
    try {
      const success = await authStore.login({
        username: loginForm.username,
        password: loginForm.password,
        auth_type: loginForm.auth_type || undefined,
      })

      if (success) {
        ElMessage.success('登录成功')
        router.push('/')
      }
    } catch (error: any) {
      ElMessage.error(error.response?.data?.message || error.message || '登录失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<style scoped lang="scss">
.login-page {
  display: flex;
  min-height: 100vh;
  background: var(--bg-page);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* ===== 左侧品牌区 ===== */
.login-brand {
  flex: 1;
  position: relative;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: linear-gradient(135deg, #1a5f9e 0%, #2d6cdf 50%, #5b6ef5 100%);
  overflow: hidden;

  .brand-decoration {
    position: absolute;
    inset: 0;
    pointer-events: none;
  }

  .deco-circle {
    position: absolute;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.08);
    backdrop-filter: blur(10px);
  }
  .deco-1 {
    width: 320px;
    height: 320px;
    top: -90px;
    right: -90px;
  }
  .deco-2 {
    width: 220px;
    height: 220px;
    bottom: 8%;
    left: -70px;
    background: rgba(255, 255, 255, 0.06);
  }
  .deco-3 {
    width: 130px;
    height: 130px;
    top: 18%;
    right: 14%;
    background: rgba(255, 255, 255, 0.1);
  }

  .deco-grid {
    position: absolute;
    inset: 0;
    background-image:
      linear-gradient(rgba(255, 255, 255, 0.04) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255, 255, 255, 0.04) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: radial-gradient(circle at center, black 0%, transparent 70%);
    -webkit-mask-image: radial-gradient(circle at center, black 0%, transparent 70%);
  }

  .brand-content {
    position: relative;
    z-index: 2;
    text-align: center;
    color: #fff;
    padding: 40px;
    animation: fadeInUp 0.8s ease;
  }

  .logo-placeholder {
    width: 76px;
    height: 76px;
    background: rgba(255, 255, 255, 0.15);
    border: 1px solid rgba(255, 255, 255, 0.2);
    border-radius: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin: 0 auto 24px;
    backdrop-filter: blur(20px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.12);
  }

  .brand-title {
    font-size: 30px;
    font-weight: 600;
    margin-bottom: 8px;
    letter-spacing: 2px;
    text-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .brand-subtitle {
    font-size: 18px;
    opacity: 0.85;
    margin-bottom: 48px;
    letter-spacing: 6px;
  }

  .brand-features {
    display: flex;
    gap: 16px;
    justify-content: center;

    .feature-item {
      display: flex;
      flex-direction: column;
      align-items: center;
      gap: 8px;
      padding: 18px 20px;
      background: rgba(255, 255, 255, 0.1);
      border: 1px solid rgba(255, 255, 255, 0.15);
      border-radius: 14px;
      backdrop-filter: blur(20px);
      transition: all 0.3s ease;

      &:hover {
        background: rgba(255, 255, 255, 0.2);
        transform: translateY(-4px);
        box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
      }

      span {
        font-size: 13px;
        opacity: 0.9;
      }
    }
  }
}

/* ===== 右侧表单区 ===== */
.login-form-wrapper {
  width: 480px;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px;
  background: var(--bg-card);

  .login-form-container {
    width: 100%;
    max-width: 380px;
    animation: fadeInUp 0.8s ease 0.1s both;
  }

  .form-header {
    margin-bottom: 36px;

    h2 {
      font-size: 26px;
      font-weight: 600;
      color: var(--text-primary);
      margin-bottom: 8px;
    }

    p {
      font-size: 14px;
      color: var(--text-tertiary);
    }
  }

  .login-form {
    :deep(.el-input__wrapper) {
      box-shadow: 0 0 0 1px #e5e6eb inset;
      border-radius: 10px;
      padding: 4px 14px;
      transition: all 0.2s ease;

      &:hover {
        box-shadow: 0 0 0 1px #c9cdd4 inset;
      }

      &.is-focus {
        box-shadow: 0 0 0 2px rgba(45, 108, 223, 0.3) inset;
      }
    }

    :deep(.el-input__inner) {
      height: 44px;
      font-size: 14px;
    }
  }

  .login-btn {
    width: 100%;
    height: 48px;
    font-size: 16px;
    font-weight: 500;
    border-radius: 10px;
    border: none;
    background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
    box-shadow: 0 4px 12px rgba(45, 108, 223, 0.3);
    transition: all 0.3s ease;

    &:hover {
      transform: translateY(-2px);
      box-shadow: 0 6px 20px rgba(45, 108, 223, 0.4);
      background: linear-gradient(135deg, #3a78e8 0%, #6a7bf7 100%);
    }

    &:active {
      transform: translateY(0);
    }
  }

  .form-footer {
    margin-top: 28px;
    text-align: center;

    p {
      font-size: 12px;
      color: var(--text-tertiary);
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 4px;
    }
  }
}

@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

/* 响应式 */
@media (max-width: 900px) {
  .login-brand {
    display: none;
  }
  .login-form-wrapper {
    width: 100%;
  }
}
</style>
