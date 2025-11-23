<script setup lang="ts">
import { ref } from 'vue'
import DocumentUploader from './components/DocumentUploader.vue'
import ChatInterface from './components/ChatInterface.vue'
import AnalysisReport from './components/AnalysisReport.vue'
import { Document, ChatLineRound, DataAnalysis } from '@element-plus/icons-vue'

const activeTab = ref('upload')
const currentDocumentId = ref('')

const handleDocumentUploaded = (id: string) => {
  currentDocumentId.value = id
  activeTab.value = 'chat'
}
</script>

<template>
  <div class="app-wrapper">
    <el-container class="main-container">
      <el-aside width="260px" class="sidebar">
        <div class="brand">
          <div class="logo-icon">⚡</div>
          <div class="brand-text">BlockRAG</div>
        </div>
        
        <div class="nav-menu">
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'upload' }"
            @click="activeTab = 'upload'"
          >
            <el-icon><Document /></el-icon>
            <span>Document</span>
          </div>
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'chat', disabled: !currentDocumentId }"
            @click="currentDocumentId && (activeTab = 'chat')"
          >
            <el-icon><ChatLineRound /></el-icon>
            <span>Chat Q&A</span>
          </div>
          <div 
            class="nav-item" 
            :class="{ active: activeTab === 'analysis', disabled: !currentDocumentId }"
            @click="currentDocumentId && (activeTab = 'analysis')"
          >
            <el-icon><DataAnalysis /></el-icon>
            <span>Analysis</span>
          </div>
        </div>

        <div class="sidebar-footer">
          <p class="status-text" v-if="currentDocumentId">
            <span class="dot online"></span> Doc Loaded
          </p>
          <p class="status-text" v-else>
            <span class="dot offline"></span> No Document
          </p>
        </div>
      </el-aside>
      
      <el-container>
        <el-header class="app-header">
          <div class="header-content">
            <h2>{{ 
              activeTab === 'upload' ? 'Upload Whitepaper' : 
              activeTab === 'chat' ? 'Interactive Q&A' : 
              'Deep Analysis Report' 
            }}</h2>
            <div class="user-profile">
              <el-avatar size="small" src="https://cube.elemecdn.com/3/7c/3ea6beec64369c2642b92c6726f1epng.png" />
              <span class="username">Demo User</span>
            </div>
          </div>
        </el-header>
        
        <el-main class="content-area">
          <transition name="fade" mode="out-in">
            <keep-alive>
              <component 
                :is="activeTab === 'upload' ? DocumentUploader : activeTab === 'chat' ? ChatInterface : AnalysisReport"
                :document-id="currentDocumentId"
                @document-uploaded="handleDocumentUploaded"
                :key="activeTab"
              />
            </keep-alive>
          </transition>
        </el-main>
      </el-container>
    </el-container>
  </div>
</template>

<style scoped>
.app-wrapper {
  height: 100vh;
  width: 100vw;
  display: flex;
  background-color: #f8f9fb;
}

.main-container {
  height: 100%;
  width: 100%;
}

.sidebar {
  background: white;
  border-right: 1px solid #f0f0f0;
  display: flex;
  flex-direction: column;
  padding: 24px;
}

.brand {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 48px;
  padding-left: 12px;
}

.logo-icon {
  width: 32px;
  height: 32px;
  background: linear-gradient(135deg, #409eff 0%, #2c3e50 100%);
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-weight: bold;
  font-size: 18px;
}

.brand-text {
  font-size: 20px;
  font-weight: 700;
  color: #1a1a1a;
  letter-spacing: -0.5px;
}

.nav-menu {
  display: flex;
  flex-direction: column;
  gap: 8px;
  flex: 1;
}

.nav-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 12px;
  cursor: pointer;
  color: #606266;
  font-weight: 500;
  transition: all 0.2s ease;
}

.nav-item:hover:not(.disabled) {
  background-color: #f5f7fa;
  color: #409eff;
}

.nav-item.active {
  background-color: #ecf5ff;
  color: #409eff;
}

.nav-item.disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.sidebar-footer {
  padding-top: 20px;
  border-top: 1px solid #f0f0f0;
}

.status-text {
  font-size: 12px;
  color: #909399;
  display: flex;
  align-items: center;
  gap: 8px;
}

.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
}

.dot.online { background-color: #67c23a; }
.dot.offline { background-color: #909399; }

.app-header {
  background: transparent;
  padding: 0 40px;
  height: 80px;
  display: flex;
  align-items: center;
}

.header-content {
  width: 100%;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-content h2 {
  margin: 0;
  font-size: 24px;
  font-weight: 600;
}

.user-profile {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 6px 12px;
  background: white;
  border-radius: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.username {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.content-area {
  padding: 0 40px 40px;
  overflow-y: auto;
}

/* Transitions */
.fade-enter-active,
.fade-leave-active {
  transition: opacity 0.2s ease;
}

.fade-enter-from,
.fade-leave-to {
  opacity: 0;
}
</style>
