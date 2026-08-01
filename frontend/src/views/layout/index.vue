<template>
  <div class="layout">
    <!-- 侧边栏 -->
    <aside class="sidebar" :class="{ collapsed: isCollapsed }">
      <div class="sidebar-header">
        <div class="logo">
          <div class="logo-icon">
            <el-icon :size="20" color="#fff">
              <OfficeBuilding />
            </el-icon>
          </div>
          <span v-if="!isCollapsed" class="logo-text">知识问答</span>
        </div>
      </div>

      <el-menu
        :default-active="activeMenu"
        :collapse="isCollapsed"
        :collapse-transition="false"
        router
        class="sidebar-menu"
        background-color="transparent"
        text-color="rgba(255, 255, 255, 0.75)"
        active-text-color="#fff"
      >
        <template v-for="route in menuRoutes" :key="route.path">
          <el-menu-item v-if="!route.meta?.hidden" :index="route.path">
            <el-icon>
              <component :is="route.meta?.icon" />
            </el-icon>
            <template #title>
              {{ route.meta?.title }}
            </template>
          </el-menu-item>
        </template>
      </el-menu>

      <div class="sidebar-footer">
        <el-dropdown @command="handleCommand">
          <div class="user-info">
            <el-avatar :size="32" :icon="UserFilled" />
            <span v-if="!isCollapsed" class="user-name">{{ authStore.displayName }}</span>
          </div>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="profile">
                <el-icon><User /></el-icon>个人中心
              </el-dropdown-item>
              <el-dropdown-item command="password">
                <el-icon><Lock /></el-icon>修改密码
              </el-dropdown-item>
              <el-dropdown-item divided command="logout">
                <el-icon><SwitchButton /></el-icon>退出登录
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>
    </aside>

    <!-- 主区域 -->
    <div class="main-area">
      <header class="topbar">
        <div class="topbar-left">
          <div class="collapse-btn" @click="toggleCollapse">
            <el-icon><Fold v-if="!isCollapsed" /><Expand v-else /></el-icon>
          </div>
          <el-breadcrumb separator="/">
            <el-breadcrumb-item>{{ currentTitle }}</el-breadcrumb-item>
          </el-breadcrumb>
        </div>
        <div class="topbar-right">
          <div class="theme-btn" @click="toggleDark()">
            <el-icon :size="18"> <Sunny v-if="isDark" /><Moon v-else /> </el-icon>
          </div>
        </div>
      </header>

      <main class="main-content">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useRoute } from 'vue-router'
import { useDark, useToggle } from '@vueuse/core'
import {
  UserFilled,
  User,
  Lock,
  SwitchButton,
  Fold,
  Expand,
  OfficeBuilding,
  Sunny,
  Moon,
} from '@element-plus/icons-vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { useAuthStore } from '@/stores/auth'
import { routes } from '@/router'

const route = useRoute()
const authStore = useAuthStore()
const isCollapsed = ref(false)
const isDark = useDark()
const toggleDark = useToggle(isDark)

const activeMenu = computed(() => route.path)
const currentTitle = computed(() => (route.meta?.title as string) || '智能问答平台')

// 根据角色过滤菜单
const menuRoutes = computed(() => {
  const layoutRoute = routes.find(r => r.name === 'Layout')
  if (!layoutRoute?.children) return []

  return layoutRoute.children.filter(r => {
    if (r.meta?.hidden) return false
    if (r.meta?.admin && !authStore.isAdmin) return false
    return true
  })
})

const toggleCollapse = () => {
  isCollapsed.value = !isCollapsed.value
}

const handleCommand = (command: string) => {
  switch (command) {
    case 'profile':
      ElMessage.info('个人中心功能开发中')
      break
    case 'password':
      // TODO: 打开修改密码对话框
      break
    case 'logout':
      ElMessageBox.confirm('确定要退出登录吗？', '提示', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      }).then(() => {
        authStore.logout()
        ElMessage.success('已退出登录')
      })
      break
  }
}
</script>

<style scoped lang="scss">
.layout {
  display: flex;
  height: 100vh;
  background: var(--bg-page);
  font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Microsoft YaHei', sans-serif;
}

/* ===== 侧边栏（深色，亮/暗通用） ===== */
.sidebar {
  width: 230px;
  background: linear-gradient(180deg, #1a2342 0%, #1f2a52 100%);
  display: flex;
  flex-direction: column;
  transition: width 0.3s ease;
  box-shadow: 2px 0 12px rgba(0, 0, 0, 0.15);

  &.collapsed {
    width: 64px;
  }
}

.sidebar-header {
  padding: 16px 18px;
  display: flex;
  align-items: center;

  .logo {
    display: flex;
    align-items: center;
    gap: 12px;

    .logo-icon {
      width: 36px;
      height: 36px;
      border-radius: 10px;
      background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      box-shadow: 0 4px 10px rgba(45, 108, 223, 0.3);
    }

    .logo-text {
      font-size: 17px;
      font-weight: 600;
      color: #fff;
      white-space: nowrap;
      letter-spacing: 1px;
    }
  }
}

.sidebar-menu {
  flex: 1;
  border-right: none;
  padding: 8px 12px;

  :deep(.el-menu-item) {
    height: 46px;
    line-height: 46px;
    border-radius: 10px;
    margin-bottom: 4px;
    padding-left: 14px !important;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(255, 255, 255, 0.08);
      color: #fff;
    }

    &.is-active {
      background: linear-gradient(135deg, #2d6cdf 0%, #5b6ef5 100%);
      box-shadow: 0 4px 12px rgba(45, 108, 223, 0.35);
      color: #fff;
    }
  }
}

.sidebar-footer {
  padding: 12px 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);

  .user-info {
    display: flex;
    align-items: center;
    gap: 10px;
    cursor: pointer;
    padding: 8px;
    border-radius: 10px;
    transition: all 0.2s ease;

    &:hover {
      background: rgba(255, 255, 255, 0.08);
    }

    .user-name {
      font-size: 14px;
      color: rgba(255, 255, 255, 0.9);
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }
  }
}

/* ===== 主区域 ===== */
.main-area {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.topbar {
  height: 60px;
  background: var(--bg-card);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 24px;
  box-shadow: 0 1px 4px rgba(0, 0, 0, 0.04);
  z-index: 10;
  transition: background 0.3s ease;

  .topbar-left {
    display: flex;
    align-items: center;
    gap: 16px;
  }

  .topbar-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }

  .collapse-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.2s ease;

    &:hover {
      background: var(--bg-subtle);
      color: #2d6cdf;
    }
  }

  .theme-btn {
    width: 36px;
    height: 36px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 8px;
    cursor: pointer;
    color: var(--text-secondary);
    transition: all 0.2s ease;

    &:hover {
      background: var(--bg-subtle);
      color: #2d6cdf;
    }
  }

  :deep(.el-breadcrumb__item) {
    .el-breadcrumb__inner {
      font-size: 15px;
      font-weight: 500;
      color: var(--text-primary);
    }
  }
}

.main-content {
  flex: 1;
  overflow: auto;
  padding: 20px;
}
</style>
