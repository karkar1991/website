<template>
  <el-dialog :model-value="modelValue" title="Two-factor login (2FA)" width="440px" @close="emit('update:modelValue', false)">
    <template v-if="session.me?.totp_enabled">
      <el-result icon="success" title="2FA is ON" sub-title="Login asks for the 6-digit code from your authenticator app." />
      <el-form @submit.prevent="disable">
        <el-form-item label="Code to turn off">
          <el-input v-model="code" maxlength="6" placeholder="123456" style="width: 140px" />
          <el-button type="danger" style="margin-left: 8px" :disabled="code.length !== 6" @click="disable">Turn off</el-button>
        </el-form-item>
      </el-form>
    </template>

    <template v-else>
      <p>Protect this account with Google Authenticator, Microsoft Authenticator or Authy.</p>
      <el-button v-if="!setup" type="primary" @click="start">Set up 2FA</el-button>
      <template v-else>
        <ol class="steps">
          <li>Open your authenticator app and scan this QR code:</li>
        </ol>
        <div style="text-align: center"><img :src="qr" alt="2FA QR code" width="200" height="200" /></div>
        <p style="text-align: center"><small>or enter the key: <code>{{ setup.secret }}</code></small></p>
        <ol class="steps" start="2"><li>Type the 6-digit code the app shows:</li></ol>
        <el-form @submit.prevent="enable" style="text-align: center">
          <el-input v-model="code" maxlength="6" placeholder="123456" style="width: 140px" />
          <el-button type="primary" style="margin-left: 8px" :disabled="code.length !== 6" @click="enable">Turn on</el-button>
        </el-form>
      </template>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import QRCode from 'qrcode'
import { http, loadSession, session } from '../api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const setup = ref(null)
const qr = ref('')
const code = ref('')

watch(() => props.modelValue, (open) => { if (open) { setup.value = null; code.value = '' } })

async function start() {
  const { data } = await http.post('/auth/2fa/setup')
  setup.value = data
  qr.value = await QRCode.toDataURL(data.otpauth_uri, { width: 200, margin: 1 })
}
async function enable() {
  await http.post('/auth/2fa/enable', { code: code.value })
  ElMessage.success('2FA is now on')
  await loadSession()
  emit('update:modelValue', false)
}
async function disable() {
  await http.post('/auth/2fa/disable', { code: code.value })
  ElMessage.success('2FA turned off')
  await loadSession()
  emit('update:modelValue', false)
}
</script>

<style scoped>
.steps { padding-left: 18px; margin: 8px 0; }
</style>
