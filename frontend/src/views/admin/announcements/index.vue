<template>
  <div class="announcement-page">
    <div class="page-header">
      <h2>公告管理</h2>
      <div class="header-actions">
        <el-button type="primary" @click="handleCreate">
          <el-icon><Plus /></el-icon>
          新增公告
        </el-button>
      </div>
    </div>

    <div class="filter-bar">
      <el-select v-model="filterStatus" placeholder="状态" clearable @change="fetchAnnouncements">
        <el-option label="草稿" value="draft" />
        <el-option label="已发布" value="published" />
        <el-option label="已归档" value="archived" />
      </el-select>
      <el-select v-model="filterType" placeholder="类型" clearable @change="fetchAnnouncements">
        <el-option label="普通通知" value="notice" />
        <el-option label="维护通知" value="maintenance" />
        <el-option label="更新公告" value="update" />
      </el-select>
      <el-button @click="fetchAnnouncements"> 刷新 </el-button>
    </div>

    <el-table v-loading="loading" :data="announcements" stripe>
      <el-table-column prop="title" label="标题" min-width="180" show-overflow-tooltip />
      <el-table-column prop="type" label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="typeTag(row.type)">
            {{ typeLabel(row.type) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="100">
        <template #default="{ row }">
          <el-tag :type="statusTag(row.status)">
            {{ statusLabel(row.status) }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="pinned" label="置顶" width="80" align="center">
        <template #default="{ row }">
          <el-icon v-if="row.pinned" color="#e6a23c">
            <Star />
          </el-icon>
        </template>
      </el-table-column>
      <el-table-column prop="published_at" label="发布时间" width="170">
        <template #default="{ row }">
          {{ row.published_at ? formatDate(row.published_at) : '-' }}
        </template>
      </el-table-column>
      <el-table-column prop="created_at" label="创建时间" width="170">
        <template #default="{ row }">
          {{ formatDate(row.created_at) }}
        </template>
      </el-table-column>
      <el-table-column label="操作" width="240" fixed="right">
        <template #default="{ row }">
          <el-button type="primary" link size="small" @click="handleEdit(row)"> 编辑 </el-button>
          <el-button
            v-if="row.status === 'draft'"
            type="success"
            link
            size="small"
            @click="handlePublish(row)"
          >
            发布
          </el-button>
          <el-button type="warning" link size="small" @click="handleTogglePin(row)">
            {{ row.pinned ? '取消置顶' : '置顶' }}
          </el-button>
          <el-button type="danger" link size="small" @click="handleDelete(row)"> 删除 </el-button>
        </template>
      </el-table-column>
    </el-table>

    <div class="pagination">
      <el-pagination
        v-model:current-page="pagination.page"
        v-model:page-size="pagination.page_size"
        :total="pagination.total"
        :page-sizes="[10, 20, 50]"
        layout="total, sizes, prev, pager, next"
        @current-change="fetchAnnouncements"
        @size-change="fetchAnnouncements"
      />
    </div>

    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="600px">
      <el-form ref="formRef" :model="formData" :rules="formRules" label-width="100px">
        <el-form-item label="标题" prop="title">
          <el-input
            v-model="formData.title"
            placeholder="请输入公告标题"
            maxlength="200"
            show-word-limit
          />
        </el-form-item>
        <el-form-item label="正文" prop="content">
          <el-input
            v-model="formData.content"
            type="textarea"
            :rows="5"
            placeholder="请输入公告内容"
          />
        </el-form-item>
        <el-form-item label="类型" prop="type">
          <el-select v-model="formData.type" placeholder="选择类型">
            <el-option label="普通通知" value="notice" />
            <el-option label="维护通知" value="maintenance" />
            <el-option label="更新公告" value="update" />
          </el-select>
        </el-form-item>
        <el-form-item label="状态" prop="status">
          <el-select v-model="formData.status" placeholder="选择状态">
            <el-option label="草稿" value="draft" />
            <el-option label="已发布" value="published" />
            <el-option label="已归档" value="archived" />
          </el-select>
        </el-form-item>
        <el-form-item label="置顶">
          <el-switch v-model="formData.pinned" />
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
import { Plus, Star } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import {
  listAnnouncements,
  createAnnouncement,
  updateAnnouncement,
  deleteAnnouncement,
  publishAnnouncement,
  type AnnouncementItem,
  type AnnouncementStatus,
  type AnnouncementType,
} from '@/api/announcement'

const loading = ref(false)
const submitting = ref(false)
const dialogVisible = ref(false)
const isEdit = ref(false)

const announcements = ref<AnnouncementItem[]>([])
const filterStatus = ref('')
const filterType = ref('')
const pagination = reactive({ page: 1, page_size: 20, total: 0 })

const formRef = ref<FormInstance>()
const formData = reactive({
  id: undefined as string | undefined,
  title: '',
  content: '',
  type: 'notice' as AnnouncementType,
  status: 'draft' as AnnouncementStatus,
  pinned: false,
})

const formRules: FormRules = {
  title: [{ required: true, message: '请输入公告标题', trigger: 'blur' }],
  content: [{ required: true, message: '请输入公告正文', trigger: 'blur' }],
}

const dialogTitle = computed(() => (isEdit.value ? '编辑公告' : '新增公告'))

const fetchAnnouncements = async () => {
  loading.value = true
  try {
    const res = await listAnnouncements({
      page: pagination.page,
      page_size: pagination.page_size,
      status: (filterStatus.value as AnnouncementStatus) || undefined,
      type: (filterType.value as AnnouncementType) || undefined,
    })
    announcements.value = res.items
    pagination.total = res.total
  } catch {
    ElMessage.error('获取公告列表失败')
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  Object.assign(formData, {
    id: undefined,
    title: '',
    content: '',
    type: 'notice',
    status: 'draft',
    pinned: false,
  })
}

const handleCreate = () => {
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const handleEdit = (row: AnnouncementItem) => {
  isEdit.value = true
  Object.assign(formData, {
    id: row.id,
    title: row.title,
    content: row.content,
    type: row.type,
    status: row.status,
    pinned: row.pinned,
  })
  dialogVisible.value = true
}

const handleSubmit = async () => {
  if (!formRef.value) return
  await formRef.value.validate()

  submitting.value = true
  try {
    if (isEdit.value) {
      await updateAnnouncement(formData.id!, {
        title: formData.title,
        content: formData.content,
        type: formData.type,
        status: formData.status,
        pinned: formData.pinned,
      })
      ElMessage.success('更新成功')
    } else {
      await createAnnouncement({
        title: formData.title,
        content: formData.content,
        type: formData.type,
        pinned: formData.pinned,
      })
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchAnnouncements()
  } catch {
    ElMessage.error(isEdit.value ? '更新失败' : '创建失败')
  } finally {
    submitting.value = false
  }
}

const handlePublish = async (row: AnnouncementItem) => {
  try {
    await publishAnnouncement(row.id)
    ElMessage.success('发布成功')
    fetchAnnouncements()
  } catch {
    ElMessage.error('发布失败')
  }
}

const handleTogglePin = async (row: AnnouncementItem) => {
  try {
    await updateAnnouncement(row.id, { pinned: !row.pinned })
    ElMessage.success(row.pinned ? '已取消置顶' : '已置顶')
    fetchAnnouncements()
  } catch {
    ElMessage.error('操作失败')
  }
}

const handleDelete = async (row: AnnouncementItem) => {
  try {
    await ElMessageBox.confirm(`确定删除公告 "${row.title}" 吗？`, '提示', { type: 'warning' })
    await deleteAnnouncement(row.id)
    ElMessage.success('删除成功')
    fetchAnnouncements()
  } catch {
    // cancelled
  }
}

const typeLabel = (type: AnnouncementType) => {
  const map: Record<AnnouncementType, string> = {
    notice: '普通通知',
    maintenance: '维护通知',
    update: '更新公告',
  }
  return map[type] ?? type
}

const typeTag = (type: AnnouncementType) => {
  const map: Record<AnnouncementType, string> = {
    notice: '',
    maintenance: 'warning',
    update: 'success',
  }
  return (map[type] ?? '') as '' | 'warning' | 'success'
}

const statusLabel = (status: AnnouncementStatus) => {
  const map: Record<AnnouncementStatus, string> = {
    draft: '草稿',
    published: '已发布',
    archived: '已归档',
  }
  return map[status] ?? status
}

const statusTag = (status: AnnouncementStatus) => {
  const map: Record<AnnouncementStatus, string> = {
    draft: 'info',
    published: 'success',
    archived: '',
  }
  return (map[status] ?? '') as '' | 'info' | 'success'
}

const formatDate = (dateStr: string) => {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return d.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  })
}

onMounted(() => {
  fetchAnnouncements()
})
</script>

<style scoped lang="scss">
.announcement-page {
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

.filter-bar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.pagination {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}
</style>
