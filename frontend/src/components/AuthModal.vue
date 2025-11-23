<script setup lang="ts">
import { ref } from 'vue'
import { ElMessage } from 'element-plus'
import type { Session } from '@supabase/supabase-js'
import { supabase } from '../lib/supabase'

const visible = defineModel<boolean>('visible', { default: false })

const emit = defineEmits<{
  authenticated: [session: Session | null]
}>()

const activeTab = ref<'login' | 'register'>('login')
const email = ref('')
const password = ref('')
const loading = ref(false)
const helperText = ref('')

const minPassword = 6

const handleGoogleLogin = async () => {
  loading.value = true
  helperText.value = ''
  try {
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: {
        redirectTo: window.location.origin,
      },
    })
    if (error) {
      helperText.value = error.message
    } else {
      ElMessage.info('正在跳转到 Google 登录...')
    }
  } finally {
    loading.value = false
  }
}

const handleSubmit = async () => {
  helperText.value = ''
  if (!email.value || !password.value) {
    helperText.value = '请填写邮箱和密码'
    return
  }
  if (password.value.length < minPassword) {
    helperText.value = `密码至少 ${minPassword} 位`
    return
  }

  loading.value = true
  try {
    if (activeTab.value === 'login') {
      const { data, error } = await supabase.auth.signInWithPassword({
        email: email.value,
        password: password.value,
      })
      if (error) {
        helperText.value = error.message
        return
      }
      emit('authenticated', data.session)
      resetForm()
    } else {
      const { data, error } = await supabase.auth.signUp({
        email: email.value,
        password: password.value,
        options: {
          emailRedirectTo: window.location.origin,
        },
      })
      if (error) {
        helperText.value = error.message
        return
      }
      if (!data.session) {
        ElMessage.success('注册成功，请查收邮件完成验证')
        emit('authenticated', null)
        resetForm()
        return
      }
      emit('authenticated', data.session)
      resetForm()
    }
  } finally {
    loading.value = false
  }
}

const resetForm = () => {
  email.value = ''
  password.value = ''
  helperText.value = ''
  visible.value = false
}
</script>

<template>
  <el-dialog
    v-model="visible"
    width="420px"
    destroy-on-close
    :show-close="false"
    class="auth-dialog"
  >
    <template #header>
      <div class="dialog-header">
        <h3>账户中心</h3>
        <el-tag size="small" type="info">Supabase Auth</el-tag>
      </div>
    </template>

    <el-tabs v-model="activeTab" stretch>
      <el-tab-pane label="登录" name="login" />
      <el-tab-pane label="注册" name="register" />
    </el-tabs>

    <el-form label-position="top" @submit.prevent>
      <el-form-item label="邮箱">
        <el-input v-model="email" auto-complete="email" placeholder="example@domain.com" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input
          v-model="password"
          type="password"
          show-password
          :placeholder="activeTab === 'register' ? `不少于 ${minPassword} 位` : '请输入密码'"
        />
      </el-form-item>
    </el-form>

    <p v-if="helperText" class="helper-text">{{ helperText }}</p>

    <el-button
      class="google-btn"
      :loading="loading"
      @click="handleGoogleLogin"
      type="primary"
      plain
      link="false"
    >
      使用 Google 快速登录
    </el-button>

    <div class="actions">
      <el-button @click="visible = false">取消</el-button>
      <el-button type="primary" :loading="loading" @click="handleSubmit">
        {{ activeTab === 'login' ? '登录' : '注册' }}
      </el-button>
    </div>
  </el-dialog>
</template>

<style scoped>
.auth-dialog :deep(.el-dialog__body) {
  padding-top: 0;
}

.dialog-header {
  display: flex;
  align-items: center;
  gap: 12px;
}

.dialog-header h3 {
  margin: 0;
}

.helper-text {
  color: #f56c6c;
  font-size: 13px;
  margin-bottom: 12px;
}

.actions {
  margin-top: 10px;
  display: flex;
  justify-content: flex-end;
  gap: 10px;
}

.google-btn {
  width: 100%;
  margin-bottom: 16px;
  justify-content: center;
}
</style>

