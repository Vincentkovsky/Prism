<script setup lang="ts">
import { ref, watch, computed, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, RefreshRight, DataLine } from '@element-plus/icons-vue'
import MarkdownIt from 'markdown-it'
import { generateAnalysis, getAnalysis } from '../api'

const props = defineProps<{
  documentId: string
  isAuthenticated: boolean
}>()

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
})

const report = ref<any>(null)
const isLoading = ref(false)
const statusMessage = ref('')
const pollingInterval = ref<number | null>(null)

const reportHtml = computed(() => {
  if (!report.value) return ''
  
  if (typeof report.value === 'string') {
    return md.render(report.value)
  }
  
  // Structured report rendering
  let html = ''
  
  // Header Section
  html += `<div class="report-title-section">`
  if (report.value.overall_score) {
    const scoreClass = report.value.overall_score >= 80 ? 'high' : report.value.overall_score >= 60 ? 'medium' : 'low'
    html += `
      <div class="score-card ${scoreClass}">
        <div class="score-value">${report.value.overall_score}</div>
        <div class="score-label">Overall Score</div>
      </div>
    `
  }
  html += `</div>`

  // Summary
  if (report.value.summary) {
    html += `
      <div class="report-section">
        <h2>Executive Summary</h2>
        <div class="section-content">${md.render(report.value.summary)}</div>
      </div>
    `
  }

  // Technical Analysis
  if (report.value.technical_analysis) {
    html += `
      <div class="report-section">
        <h2>Technical Architecture</h2>
        <div class="section-content">${md.render(report.value.technical_analysis)}</div>
      </div>
    `
  }

  // Market Analysis
  if (report.value.market_analysis) {
    html += `
      <div class="report-section">
        <h2>Market & Tokenomics</h2>
        <div class="section-content">${md.render(report.value.market_analysis)}</div>
      </div>
    `
  }

  // Fallback for unstructured data
  if (!html || (!report.value.summary && !report.value.technical_analysis)) {
    return `<pre>${JSON.stringify(report.value, null, 2)}</pre>`
  }
  
  return html
})

const startAnalysis = async () => {
  if (!props.documentId) return
  
  try {
    isLoading.value = true
    statusMessage.value = 'Initializing analysis workflow...'
    
    const response = await generateAnalysis(props.documentId)
    const status = response.data.status
    
    if (status === 'completed') {
      report.value = response.data.report
      isLoading.value = false
      statusMessage.value = 'Analysis completed successfully'
    } else {
      statusMessage.value = 'Analysis queued. Processing deep dive...'
      startPolling()
    }
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Analysis generation failed')
    isLoading.value = false
    statusMessage.value = 'Failed to start analysis'
  }
}

const startPolling = () => {
  if (pollingInterval.value) clearInterval(pollingInterval.value)
  
  pollingInterval.value = window.setInterval(async () => {
    if (!props.documentId) return
    
    try {
      const response = await getAnalysis(props.documentId)
      const status = response.data.status
      
      if (status === 'completed') {
        report.value = response.data.report
        isLoading.value = false
        statusMessage.value = 'Analysis completed!'
        stopPolling()
      } else {
        statusMessage.value = 'Analyzing document structure and content...'
      }
    } catch (error) {
      console.error('Polling error', error)
    }
  }, 3000)
}

const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
}

const exportReport = () => {
  if (!report.value) return
  const blob = new Blob([JSON.stringify(report.value, null, 2)], { type: 'application/json' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `analysis_${props.documentId}.json`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

onUnmounted(() => {
  stopPolling()
})

watch(
  () => [props.documentId, props.isAuthenticated],
  () => {
    report.value = null
    statusMessage.value = ''
    isLoading.value = false
    stopPolling()
  },
)
</script>

<template>
  <div class="analysis-wrapper">
    <div v-if="!isAuthenticated" class="empty-state">
      <div class="empty-content">
        <div class="icon-placeholder">🔐</div>
        <h3>请先登录</h3>
        <p>登录后即可生成深度分析报告。</p>
      </div>
    </div>
    <div v-else-if="!documentId" class="empty-state">
      <div class="empty-content">
        <div class="icon-placeholder">📊</div>
        <h3>No Document Selected</h3>
        <p>Please upload a document to generate an analysis report.</p>
      </div>
    </div>
    
    <div v-else class="content-container">
      <transition name="fade" mode="out-in">
        <div v-if="!report && !isLoading" class="start-card" key="start">
          <div class="illustration">
            <el-icon :size="64"><DataLine /></el-icon>
          </div>
          <h2>Generate Comprehensive Report</h2>
          <p class="description">
            Our AI agents will analyze the whitepaper across multiple dimensions:
            Technical Architecture, Tokenomics, Team Background, and Risk Factors.
          </p>
          <div class="cost-badge">
            <span>50 Credits</span>
          </div>
          <el-button type="primary" size="large" @click="startAnalysis" class="start-btn">
            Start Analysis
          </el-button>
        </div>
        
        <div v-else-if="isLoading" class="loading-card" key="loading">
          <div class="spinner-wrapper">
            <div class="spinner"></div>
          </div>
          <h3>Generating Insights...</h3>
          <p class="status-text">{{ statusMessage }}</p>
          <el-progress :percentage="50" :indeterminate="true" :format="() => ''" class="progress-bar" />
        </div>
        
        <div v-else class="report-view" key="report">
          <div class="report-actions">
            <el-button @click="exportReport">
              <el-icon class="el-icon--left"><Download /></el-icon> Export JSON
            </el-button>
            <el-button @click="startAnalysis" plain>
              <el-icon class="el-icon--left"><RefreshRight /></el-icon> Regenerate
            </el-button>
          </div>
          
          <div class="paper-sheet markdown-body" v-html="reportHtml"></div>
        </div>
      </transition>
    </div>
  </div>
</template>

<style scoped>
.analysis-wrapper {
  max-width: 900px;
  margin: 0 auto;
  padding-top: 20px;
}

.empty-state {
  height: 400px;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #909399;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.05);
}

.icon-placeholder {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.start-card, .loading-card {
  background: white;
  border-radius: 16px;
  padding: 60px 40px;
  text-align: center;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05);
}

.illustration {
  color: #409eff;
  margin-bottom: 24px;
}

.description {
  color: #606266;
  line-height: 1.6;
  max-width: 500px;
  margin: 16px auto 32px;
}

.cost-badge {
  display: inline-block;
  background: #f0f9eb;
  color: #67c23a;
  padding: 4px 12px;
  border-radius: 12px;
  font-weight: 600;
  font-size: 14px;
  margin-bottom: 32px;
}

.start-btn {
  padding: 12px 40px;
  font-weight: 600;
}

.loading-card h3 {
  margin-top: 24px;
  color: #303133;
}

.status-text {
  color: #909399;
  margin-bottom: 32px;
}

.progress-bar {
  max-width: 300px;
  margin: 0 auto;
}

.report-view {
  padding-bottom: 60px;
}

.report-actions {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  margin-bottom: 20px;
}

.paper-sheet {
  background: white;
  padding: 60px;
  border-radius: 2px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  color: #2c3e50;
  line-height: 1.8;
}

/* Markdown Styles overrides */
:deep(.report-title-section) {
  text-align: center;
  margin-bottom: 40px;
  padding-bottom: 40px;
  border-bottom: 1px solid #eee;
}

:deep(.score-card) {
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 120px;
  height: 120px;
  border-radius: 50%;
  border: 4px solid #eee;
}

:deep(.score-card.high) { border-color: #67c23a; color: #67c23a; }
:deep(.score-card.medium) { border-color: #e6a23c; color: #e6a23c; }
:deep(.score-card.low) { border-color: #f56c6c; color: #f56c6c; }

:deep(.score-value) {
  font-size: 36px;
  font-weight: 700;
}

:deep(.score-label) {
  font-size: 12px;
  text-transform: uppercase;
  color: #909399;
  margin-top: 4px;
}

:deep(h2) {
  border-bottom: none;
  color: #1a1a1a;
  font-size: 24px;
  margin-top: 40px;
  margin-bottom: 20px;
}

:deep(p) {
  margin-bottom: 16px;
  color: #4a4a4a;
}

/* Spinner animation */
.spinner-wrapper {
  display: flex;
  justify-content: center;
}

.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid #f3f3f3;
  border-top: 3px solid #409eff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
</style>
