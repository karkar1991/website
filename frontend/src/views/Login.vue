<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h2>Member Admin</h2>
      <el-form @submit.prevent="submit" label-position="top">
        <template v-if="!needOtp">
          <el-form-item label="Username">
            <el-input v-model="username" autocomplete="username" />
          </el-form-item>
          <el-form-item label="Password">
            <el-input v-model="password" type="password" show-password autocomplete="current-password" />
          </el-form-item>
        </template>
        <el-form-item v-else label="6-digit code from your authenticator app">
          <el-input ref="otpInput" v-model="otp" maxlength="6" inputmode="numeric" autocomplete="one-time-code" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="loading" style="width: 100%">
          {{ needOtp ? 'Verify' : 'Log in' }}
        </el-button>
        <el-button v-if="needOtp" link style="margin-top: 8px" @click="needOtp = false; otp = ''">Back</el-button>
      </el-form>
    </el-card>
  </div>
</template>

<script setup>
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { login } from '../api'

const router = useRouter()
const username = ref('')
const password = ref('')
const otp = ref('')
const needOtp = ref(false)
const otpInput = ref(null)
const loading = ref(false)

async function submit() {
  loading.value = true
  try {
    await login(username.value, password.value, needOtp.value ? otp.value : null)
    router.push('/')
  } catch (e) {
    const detail = e.response?.data?.detail
    if (detail === 'OTP_REQUIRED') {
      needOtp.value = true
      await nextTick()
      otpInput.value?.focus()
    } else {
      ElMessage.error(detail || 'Login failed')
    }
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-wrap { height: 100%; display: flex; align-items: center; justify-content: center; background: #1f2d3d; }
.login-card { width: 340px; }
h2 { margin: 0 0 16px; text-align: center; }
</style>
