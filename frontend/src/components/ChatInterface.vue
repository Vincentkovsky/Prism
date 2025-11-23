<script setup lang="ts">
import { ref, watch, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { VideoPlay, Lightning, UserFilled } from '@element-plus/icons-vue'
import { qaQuery } from '../api'

const props = defineProps<{
  documentId: string
}>()

interface Message {
  role: 'user' | 'ai'
  content: string
  sources?: any[]
  model?: string
  cached?: boolean
  timestamp: Date
}

const messages = ref<Message[]>([])
const input = ref('')
const isLoading = ref(false)
const selectedModel = ref('mini')
const scrollRef = ref<HTMLElement | null>(null)

const sendMessage = async () => {
  if (!input.value.trim() || !props.documentId) return
  
  const question = input.value
  messages.value.push({ role: 'user', content: question, timestamp: new Date() })
  input.value = ''
  isLoading.value = true
  scrollToBottom()
  
  try {
    const response = await qaQuery(props.documentId, question, selectedModel.value)
    const data = response.data
    
    messages.value.push({
      role: 'ai',
      content: data.answer,
      sources: data.sources,
      model: data.model_used,
      cached: data.cached,
      timestamp: new Date()
    })
  } catch (error: any) {
    ElMessage.error(error.response?.data?.detail || 'Query failed')
    messages.value.push({
      role: 'ai',
      content: 'Sorry, an error occurred while processing your request.',
      timestamp: new Date()
    })
  } finally {
    isLoading.value = false
    scrollToBottom()
  }
}

const scrollToBottom = () => {
  nextTick(() => {
    if (scrollRef.value) {
      scrollRef.value.scrollTop = scrollRef.value.scrollHeight
    }
  })
}

const formatTime = (date: Date) => {
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
}

// Clear messages when document changes
watch(() => props.documentId, () => {
  messages.value = []
})
</script>

<template>
  <div class="chat-wrapper">
    <div v-if="!documentId" class="empty-state">
      <div class="empty-content">
        <div class="icon-placeholder">💬</div>
        <h3>No Document Selected</h3>
        <p>Please upload or select a document from the sidebar to start chatting.</p>
      </div>
    </div>
    
    <template v-else>
      <div class="chat-header">
        <div class="model-selector">
          <span class="label">Model:</span>
          <el-radio-group v-model="selectedModel" size="small" class="model-radios">
            <el-radio-button label="mini">
              <div class="radio-content">
                <el-icon><Lightning /></el-icon> Mini
              </div>
            </el-radio-button>
            <el-radio-button label="turbo">
              <div class="radio-content">
                <el-icon><VideoPlay /></el-icon> Turbo
              </div>
            </el-radio-button>
          </el-radio-group>
        </div>
        <div class="header-actions">
          <el-button link size="small" @click="messages = []">Clear Chat</el-button>
        </div>
      </div>

      <div class="messages-area" ref="scrollRef">
        <div v-if="messages.length === 0" class="welcome-message">
          <h3>Ask anything about the document!</h3>
          <p>Try asking about the technical architecture, team background, or tokenomics.</p>
          <div class="suggestions">
            <el-tag class="suggestion" @click="input = 'What problem does this project solve?'; sendMessage()">What problem does it solve?</el-tag>
            <el-tag class="suggestion" @click="input = 'Explain the consensus mechanism.'; sendMessage()">Consensus mechanism?</el-tag>
            <el-tag class="suggestion" @click="input = 'Who are the team members?'; sendMessage()">Team background?</el-tag>
          </div>
        </div>

        <div v-for="(msg, index) in messages" :key="index" :class="['message-row', msg.role]">
          <div class="avatar" v-if="msg.role === 'ai'">
            <div class="ai-icon">🤖</div>
          </div>
          
          <div class="message-content-wrapper">
            <div class="message-meta" v-if="msg.role === 'ai'">
              <span class="name">AI Assistant</span>
              <span class="time">{{ formatTime(msg.timestamp) }}</span>
              <el-tag v-if="msg.cached" size="small" type="success" effect="plain" round class="cached-badge">Cached</el-tag>
            </div>

            <div class="message-bubble">
              <div class="text-content">{{ msg.content }}</div>
              
              <div v-if="msg.sources && msg.sources.length" class="sources-section">
                <div class="sources-header">
                  <span>Sources</span>
                </div>
                <div class="sources-grid">
                  <div v-for="(source, sIndex) in msg.sources" :key="sIndex" class="source-card">
                    <div class="source-title">{{ source.section || 'Unknown Section' }}</div>
                    <div class="source-page">Page {{ source.page }}</div>
                  </div>
                </div>
              </div>
            </div>
          </div>

          <div class="avatar user" v-if="msg.role === 'user'">
            <el-icon><UserFilled /></el-icon>
          </div>
        </div>
        
        <div v-if="isLoading" class="message-row ai">
          <div class="avatar">
            <div class="ai-icon">🤖</div>
          </div>
          <div class="message-bubble loading">
            <div class="typing-indicator">
              <span></span>
              <span></span>
              <span></span>
            </div>
          </div>
        </div>
      </div>
      
      <div class="input-area">
        <div class="input-container">
          <el-input
            v-model="input"
            type="textarea"
            :rows="1"
            autosize
            placeholder="Type your question..."
            @keydown.enter.exact.prevent="sendMessage"
            :disabled="isLoading"
            resize="none"
            class="chat-input"
          />
          <el-button type="primary" circle @click="sendMessage" :loading="isLoading" class="send-btn">
            <template #icon>
              <svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </template>
          </el-button>
        </div>
        <div class="input-hint">Press Enter to send, Shift + Enter for new line</div>
      </div>
    </template>
  </div>
</template>

<style scoped>
.chat-wrapper {
  height: calc(100vh - 140px);
  display: flex;
  flex-direction: column;
  background: white;
  border-radius: 16px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.05);
  overflow: hidden;
}

.empty-state {
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  text-align: center;
  color: #909399;
}

.icon-placeholder {
  font-size: 48px;
  margin-bottom: 16px;
  opacity: 0.5;
}

.chat-header {
  padding: 16px 24px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: white;
}

.model-selector {
  display: flex;
  align-items: center;
  gap: 12px;
}

.label {
  font-size: 14px;
  color: #606266;
  font-weight: 500;
}

.radio-content {
  display: flex;
  align-items: center;
  gap: 6px;
}

.messages-area {
  flex: 1;
  overflow-y: auto;
  padding: 24px;
  background: #f8f9fb;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.welcome-message {
  text-align: center;
  margin-top: 40px;
  color: #606266;
}

.suggestions {
  display: flex;
  justify-content: center;
  gap: 10px;
  margin-top: 20px;
  flex-wrap: wrap;
}

.suggestion {
  cursor: pointer;
  transition: all 0.2s;
}

.suggestion:hover {
  transform: translateY(-2px);
}

.message-row {
  display: flex;
  gap: 16px;
  max-width: 85%;
}

.message-row.user {
  align-self: flex-end;
  flex-direction: row-reverse;
}

.message-row.ai {
  align-self: flex-start;
}

.avatar {
  width: 36px;
  height: 36px;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.ai-icon {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  width: 100%;
  height: 100%;
  border-radius: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  font-size: 18px;
}

.avatar.user {
  background: #409eff;
  color: white;
  border-radius: 50%;
}

.message-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.message-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #909399;
  margin-left: 4px;
}

.cached-badge {
  height: 18px;
  padding: 0 6px;
}

.message-bubble {
  padding: 16px;
  border-radius: 16px;
  line-height: 1.6;
  position: relative;
  box-shadow: 0 2px 8px rgba(0,0,0,0.02);
}

.message-row.ai .message-bubble {
  background: white;
  border-top-left-radius: 4px;
  color: #303133;
}

.message-row.user .message-bubble {
  background: #409eff;
  color: white;
  border-top-right-radius: 4px;
}

.sources-section {
  margin-top: 16px;
  padding-top: 12px;
  border-top: 1px solid #f0f0f0;
}

.sources-header {
  font-size: 12px;
  font-weight: 600;
  color: #909399;
  margin-bottom: 8px;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.sources-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.source-card {
  background: #f5f7fa;
  padding: 6px 10px;
  border-radius: 6px;
  font-size: 12px;
  border: 1px solid #ebeef5;
  max-width: 200px;
}

.source-title {
  font-weight: 600;
  color: #303133;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.source-page {
  color: #909399;
  font-size: 11px;
}

.input-area {
  padding: 20px 24px;
  background: white;
  border-top: 1px solid #f0f0f0;
}

.input-container {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  background: #f5f7fa;
  padding: 8px 8px 8px 16px;
  border-radius: 24px;
  border: 1px solid transparent;
  transition: all 0.3s;
}

.input-container:focus-within {
  background: white;
  border-color: #409eff;
  box-shadow: 0 0 0 2px rgba(64, 158, 255, 0.1);
}

.chat-input :deep(.el-textarea__inner) {
  box-shadow: none;
  background: transparent;
  padding: 8px 0;
  min-height: 24px !important;
}

.send-btn {
  flex-shrink: 0;
}

.input-hint {
  font-size: 12px;
  color: #909399;
  margin-top: 8px;
  text-align: center;
}

/* Typing indicator */
.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 6px;
  height: 6px;
  background: #c0c4cc;
  border-radius: 50%;
  animation: bounce 1.4s infinite ease-in-out both;
}

.typing-indicator span:nth-child(1) { animation-delay: -0.32s; }
.typing-indicator span:nth-child(2) { animation-delay: -0.16s; }

@keyframes bounce {
  0%, 80%, 100% { transform: scale(0); }
  40% { transform: scale(1); }
}
</style>
