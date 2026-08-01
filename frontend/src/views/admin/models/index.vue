<template>
  <div class="model-page">
    <!-- 页面标题 -->
    <div class="page-header">
      <h2>模型管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新增模型
        </el-button>
      </div>
    </div>

    <!-- 状态卡片 -->
    <div class="status-cards">
      <div class="status-card healthy">
        <div class="status-icon">
          <el-icon :size="24">
            <CircleCheck />
          </el-icon>
        </div>
        <div class="status-info">
          <span class="status-count">{{ healthSummary.healthy_count || 0 }}</span>
          <span class="status-label">健康</span>
        </div>
      </div>
      <div class="status-card degraded">
        <div class="status-icon">
          <el-icon :size="24">
            <Warning />
          </el-icon>
        </div>
        <div class="status-info">
          <span class="status-count">{{ healthSummary.degraded_count || 0 }}</span>
          <span class="status-label"> degraded</span>
        </div>
      </div>
      <div class="status-card unhealthy">
        <div class="status-icon">
          <el-icon :size="24">
            <CircleClose />
          </el-icon>
        </div>
        <div class="status-info">
          <span class="status-count">{{ healthSummary.unhealthy_count || 0 }}</span>
          <span class="status-label">异常</span>
        </div>
      </div>
      <div class="status-card total">
        <div class="status-icon">
          <el-icon :size="24">
            <Box />
          </el-icon>
        </div>
        <div class="status-info">
          <span class="status-count">{{ healthSummary.total_models || 0 }}</span>
          <span class="status-label">总计</span>
        </div>
      </div>
    </div>

    <!-- 筛选栏 -->
    <div class="filter-bar">
      <el-select v-model="filterProvider" placeholder="提供商" clearable @change="fetchModels">
        <el-option label="OpenAI" value="openai" />
        <el-option label="Anthropic" value="anthropic" />
        <el-option label="Qwen" value="qwen" />
        <el-option label="本地部署" value="local" />
      </el-select>
      <el-select v-model="filterStatus" placeholder="状态" clearable @change="fetchModels">
        <el-option label="启用" value="active" />
        <el-option label="禁用" value="inactive" />
        <el-option label="维护中" value="maintenance" />
      </el-select>
      <el-button @click="fetchModels"> 刷新 </el-button>
    </div>

    <!-- 模型列表 -->
    <el-table v-loading="loading" :data="models" stripe>
      <el-table-column prop="name" label="名称" min-width="120" />
      <el-table-column prop="provider" label="提供商" width="120">
        <template #default="{ row }">
          <el-tag type="info">
            {{ row.provider }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="config.model" label="模型" min-width="120">
        <template #default="{ row }">
          <code class="model-code">{{ row.config?.model }}</code>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="row.status === 'active' ? 'success' : 'info'">
            {{ row.status === 'active' ? '启用' : '禁用' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="use_count" label="调用次数" width="100" align="right" />
      <el-table-column label="操作" width="200" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row as ModelInstance)">
            编辑
          </el-button>
          <el-button type="warning" link size="small" @click="handleToggle(row as ModelInstance)">
            {{ row.status === 'active' ? '禁用' : '启用' }}
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row as ModelInstance)">
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <!-- 分页 -->
    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchModels"
        @size-change="fetchModels"
      />
    </div>

    <!-- 创建/编辑对话框 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="formData.name" placeholder="请输入模型名称" />
        </el-form-item>
        <el-form-item label="提供商" prop="provider">
          <el-select v-model="formData.provider" placeholder="选择提供商">
            <el-option label="OpenAI" value="openai" />
            <el-option label="Anthropic" value="anthropic" />
            <el-option label="Qwen" value="qwen" />
            <el-option label="本地部署" value="local" />
          </el-select>
        </el-form-item>
        <el-form-item label="模型名称" prop="config.model">
          <el-input v-model="formData.config.model" placeholder="如: gpt-4o" />
        </el-form-item>
        <el-form-item label="API 端点" prop="config.api_base">
          <el-input
            v-model="formData.config.api_base"
            placeholder="如: https://api.openai.com/v1"
          />
        </el-form-item>
        <el-form-item label="API Key">
          <el-select v-model="formData.api_key_id" placeholder="选择 API Key" clearable>
            <el-option
              v-for="key in apiKeys"
              :key="key.id"
              :label="`${key.name} (${key.key_preview})`"
              :value="key.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="温度参数">
          <el-slider
            v-model="formData.config.temperature"
            :min="0"
            :max="2"
            :step="0.1"
            show-input
          />
        </el-form-item>
        <el-form-item label="最大Token">
          <el-input-number v-model="formData.config.max_tokens" :min="1" :max="32000" />
        </el-form-item>
        <el-form-item label="描述">
          <el-input v-model="formData.description" type="textarea" :rows="2" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false"> 取消 </el-button>
        <el-button type="primary" :loading="submitting" @click="handleSubmit"> 确定 </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, CircleCheck, CircleClose, Warning, Box } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  listModels,
  createModel,
  updateModel,
  toggleModel,
  deleteModel,
  listApiKeys,
  getHealthSummary,
  type ModelInstance,
} from '@/api/model'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)

const models = ref<ModelInstance[]>([])
const apiKeys = ref<any[]>([])
const healthSummary = ref({
  total_models: 0,
  healthy_count: 0,
  degraded_count: 0,
  unhealthy_count: 0,
  unknown_count: 0,
})

const filterProvider = ref('')
const filterStatus = ref('')
const pagination = reactive({
  page: 1,
  page_size: 20,
  total: 0,
})

const formRef = ref<FormInstance>()
const formData = reactive({
  id: undefined as string | undefined,
  name: '',
  provider: 'openai',
  api_key_id: undefined as string | undefined,
  model_type: 'chat',
  description: '',
  config: {
    model: '',
    api_base: '',
    temperature: 0.7,
    max_tokens: 2048,
    top_p: undefined as number | undefined,
    timeout: 60,
  },
})

const formRules: FormRules = {
  name: [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
  provider: [{ required: true, message: '请选择提供商', trigger: 'change' }],
  'config.model': [{ required: true, message: '请输入模型名称', trigger: 'blur' }],
}

const dialogTitle = computed(() => (isEdit.value ? '编辑模型' : '新增模型'))

const fetchModels = async () => {
  loading.value = true
  try {
    const res = await listModels({
      page: pagination.page,
      page_size: pagination.page_size,
      provider: filterProvider.value || undefined,
      status: filterStatus.value || undefined,
    })
    models.value = res.items
    pagination.total = res.total
  } catch {
    ElMessage.error('获取模型列表失败')
  } finally {
    loading.value = false
  }
}

const fetchApiKeys = async () => {
  try {
    const res = await listApiKeys({ page_size: 100 })
    apiKeys.value = res.items
  } catch {
    // ignore
  }
}

const fetchHealth = async () => {
  try {
    healthSummary.value = await getHealthSummary()
  } catch {
    // ignore
  }
}

const resetForm = () => {
  Object.assign(formData, {
    id: undefined,
    name: '',
    provider: 'openai',
    api_key_id: undefined,
    model_type: 'chat',
    description: '',
    config: {
      model: '',
      api_base: '',
      temperature: 0.7,
      max_tokens: 2048,
      top_p: undefined,
      timeout: 60,
    },
  })
}

const handleCreate = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row: ModelInstance) => {
  isEdit.value = true
  Object.assign(formData, {
    id: row.id,
    name: row.name,
    provider: row.provider,
    api_key_id: row.api_key_id,
    model_type: row.model_type,
    description: row.description || '',
    config: { ...row.config },
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateModel(formData.id!, formData)
      ElMessage.success('更新成功')
    } else {
      await createModel(formData)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchModels()
    fetchHealth()
  } catch {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handleToggle = async (row: ModelInstance) => {
  try {
    await toggleModel(row.id)
    ElMessage.success(row.status === 'active' ? '已禁用' : '已启用')
    fetchModels()
    fetchHealth()
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row: ModelInstance) => {
  try {
    await ElMessageBox.confirm(`确定删除模型 "${row.name}" 吗？`, '提示', {
      type: 'warning',
    })
    await deleteModel(row.id)
    ElMessage.success('删除成功')
    fetchModels()
    fetchHealth()
  } catch {
    // cancelled
  }
}

onMounted(() => {
  fetchModels()
  fetchApiKeys()
  fetchHealth()
})
</script>

<style scoped lang="scss">
.model-page {
  padding: 20px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 20px;

  h2 {
    font-size: 20px;
    font-weight: 600;
    color: var(--text-primary);
  }
}

.status-cards {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 20px;
}

.status-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px 20px;
  background: var(--bg-card);
  border-radius: 12px;
  border: 1px solid var(--border-color);

  .status-icon {
    width: 44px;
    height: 44px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  &.healthy .status-icon {
    background: rgba(34, 197, 94, 0.1);
    color: #22c55e;
  }

  &.degraded .status-icon {
    background: rgba(234, 179, 8, 0.1);
    color: #eab308;
  }

  &.unhealthy .status-icon {
    background: rgba(239, 68, 68, 0.1);
    color: #ef4444;
  }

  &.total .status-icon {
    background: rgba(59, 130, 246, 0.1);
    color: #3b82f6;
  }

  .status-info {
    display: flex;
    flex-direction: column;
  }

  .status-count {
    font-size: 24px;
    font-weight: 600;
    color: var(--text-primary);
  }

  .status-label {
    font-size: 13px;
    color: var(--text-secondary);
  }
}

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.model-code {
  font-family: 'SF Mono', monospace;
  font-size: 12px;
  padding: 2px 6px;
  background: var(--bg-subtle);
  border-radius: 4px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

@media (max-width: 768px) {
  .status-cards {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
