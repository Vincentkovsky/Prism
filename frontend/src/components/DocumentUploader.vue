<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { ElMessage, UploadFile } from 'element-plus'
import { UploadFilled, Link, CircleCheckFilled, Loading } from '@element-plus/icons-vue'
import { uploadDocument, submitUrl, getDocumentStatus } from '../api'

const emit = defineEmits(['document-uploaded'])

const activeTab = ref('file')
const urlInput = ref('')
const isUploading = ref(false)
const uploadProgress = ref(0)
const statusMessage = ref('')
const documentId = ref('')
const pollingInterval = ref<number | null>(null)

const handleFileChange = async (uploadFile: UploadFile) => {
  if (!uploadFile.raw) return
  
  const file = uploadFile.raw
  if (file.type !== 'application/pdf') {
    ElMessage.error('Only PDF files are allowed')
    return
  }

  try {
    isUploading.value = true
    statusMessage.value = 'Uploading...'
    uploadProgress.value = 10
    
    const response = await uploadDocument(file)
    documentId.value = response.data.document_id
    
    uploadProgress.value = 30
    statusMessage.value = 'Upload successful. Processing...'
    
    startPolling()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Upload failed')
    isUploading.value = false
    statusMessage.value = ''
  }
}

const handleSubmitUrl = async () => {
  if (!urlInput.value) return
  
  try {
    isUploading.value = true
    statusMessage.value = 'Submitting URL...'
    uploadProgress.value = 10
    
    const response = await submitUrl(urlInput.value)
    documentId.value = response.data.document_id
    
    uploadProgress.value = 30
    statusMessage.value = 'Submission successful. Processing...'
    
    startPolling()
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Submission failed')
    isUploading.value = false
    statusMessage.value = ''
  }
}

const startPolling = () => {
  if (pollingInterval.value) clearInterval(pollingInterval.value)
  
  pollingInterval.value = window.setInterval(async () => {
    if (!documentId.value) return
    
    try {
      const response = await getDocumentStatus(documentId.value)
      const status = response.data.status
      
      if (status === 'completed') {
        uploadProgress.value = 100
        statusMessage.value = 'Processing completed!'
        ElMessage.success('Document processed successfully')
        stopPolling()
        isUploading.value = false
        emit('document-uploaded', documentId.value)
      } else if (status === 'failed') {
        statusMessage.value = `Processing failed: ${response.data.error_message}`
        ElMessage.error(`Processing failed: ${response.data.error_message}`)
        stopPolling()
        isUploading.value = false
      } else {
        // Fake progress increment for better UX while pending/parsing
        if (uploadProgress.value < 90) {
          uploadProgress.value += 5
        }
        statusMessage.value = `Status: ${status}...`
      }
    } catch (error) {
      console.error('Polling error', error)
    }
  }, 2000)
}

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

onUnmounted(() => {
  stopPolling()
})
</script>

<template>
  <div class="uploader-wrapper">
    <el-card class="uploader-card">
      <template #header>
        <div class="card-header">
          <span>Start Analysis</span>
          <el-tag type="info" size="small">Supports PDF & URL</el-tag>
        </div>
      </template>

      <el-tabs v-model="activeTab" class="upload-tabs">
        <el-tab-pane label="Upload PDF" name="file">
          <div class="tab-content">
            <el-upload
              class="upload-area"
              drag
              action="#"
              :auto-upload="false"
              :on-change="handleFileChange"
              :show-file-list="false"
              accept="application/pdf"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                Drop PDF here or <em>click to upload</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  Max file size 10MB.
                </div>
              </template>
            </el-upload>
          </div>
        </el-tab-pane>
        
        <el-tab-pane label="Import from URL" name="url">
          <div class="tab-content url-content">
            <div class="url-icon-wrapper">
              <el-icon :size="40" color="#909399"><Link /></el-icon>
            </div>
            <p class="url-instruction">Enter the direct link to a hosted whitepaper PDF.</p>
            <div class="input-group">
              <el-input
                v-model="urlInput"
                placeholder="https://example.com/whitepaper.pdf"
                class="url-input"
                size="large"
              >
                <template #prefix>
                  <el-icon><Link /></el-icon>
                </template>
              </el-input>
              <el-button type="primary" size="large" @click="handleSubmitUrl" :loading="isUploading" :disabled="!urlInput">
                Import & Analyze
              </el-button>
            </div>
          </div>
        </el-tab-pane>
      </el-tabs>

      <div v-if="isUploading || statusMessage" class="progress-section">
        <div class="progress-header">
          <div class="status-row">
            <el-icon :class="{ 'is-loading': uploadProgress < 100 }">
              <Loading v-if="uploadProgress < 100" />
              <CircleCheckFilled v-else />
            </el-icon>
            <span>{{ statusMessage }}</span>
          </div>
          <span class="percentage">{{ uploadProgress }}%</span>
        </div>
        <el-progress 
          :percentage="uploadProgress" 
          :show-text="false" 
          :status="uploadProgress === 100 ? 'success' : ''" 
          :stroke-width="8"
        />
      </div>
    </el-card>

    <div class="features-grid">
      <div class="feature-item">
        <h3>Smart Parsing</h3>
        <p>Extracts headers, tables, and metadata automatically.</p>
      </div>
      <div class="feature-item">
        <h3>Vector Search</h3>
        <p>Semantic search powered by OpenAI embeddings.</p>
      </div>
      <div class="feature-item">
        <h3>Deep Analysis</h3>
        <p>Multi-dimensional analysis of tech, team, and risks.</p>
      </div>
    </div>
  </div>
</template>

<style scoped>
.uploader-wrapper {
  max-width: 800px;
  margin: 0 auto;
  padding-top: 20px;
}

.uploader-card {
  background: white;
  border-radius: 16px;
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-weight: 600;
  font-size: 16px;
}

.tab-content {
  padding: 20px 0;
}

.upload-area {
  width: 100%;
}

:deep(.el-upload-dragger) {
  border-radius: 12px;
  border: 2px dashed #dcdfe6;
  padding: 40px;
  transition: all 0.3s;
}

:deep(.el-upload-dragger:hover) {
  border-color: #409eff;
  background-color: #f9fbff;
}

.url-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: 40px 20px;
}

.url-icon-wrapper {
  margin-bottom: 16px;
  background: #f5f7fa;
  padding: 16px;
  border-radius: 50%;
}

.url-instruction {
  color: #606266;
  margin-bottom: 24px;
}

.input-group {
  display: flex;
  gap: 12px;
  width: 100%;
  max-width: 600px;
}

.url-input {
  flex: 1;
}

.progress-section {
  margin-top: 20px;
  padding: 20px;
  background: #f5f7fa;
  border-radius: 12px;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 8px;
  font-size: 14px;
  color: #606266;
}

.status-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.percentage {
  font-weight: 600;
  color: #409eff;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 20px;
  margin-top: 40px;
}

.feature-item {
  background: white;
  padding: 20px;
  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0,0,0,0.02);
}

.feature-item h3 {
  margin: 0 0 8px 0;
  font-size: 16px;
  color: #303133;
}

.feature-item p {
  margin: 0;
  font-size: 14px;
  color: #909399;
  line-height: 1.5;
}
</style>
