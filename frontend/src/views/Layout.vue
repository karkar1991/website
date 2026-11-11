<template>
  <el-container style="height: 100%">
    <el-aside width="210px" class="aside">
      <div class="logo">Member Admin</div>
      <el-menu :default-active="$route.path" router background-color="#1f2d3d" text-color="#bfcbd9"
               active-text-color="#409eff">
        <el-menu-item v-for="m in menu" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
          <el-badge v-if="m.badge && badges[m.badge]" :value="badges[m.badge]" :max="99" class="menu-badge" />
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <strong>{{ $route.meta.title }}</strong>
        <div class="spacer" />
        <el-select v-model="session.brandId" placeholder="All brands" clearable style="width: 200px">
          <el-option v-for="b in session.options.brands" :key="b.id" :label="`${b.name} (${b.currency})`" :value="b.id" />
        </el-select>

        <el-popover v-if="can('finance.view')" placement="bottom-end" :width="340" trigger="click">
          <template #reference>
            <el-badge :value="pendingTotal" :hidden="!pendingTotal" :max="99">
              <el-button circle icon="Bell" />
            </el-badge>
          </template>
          <div class="bell-head">
            <router-link to="/deposits">Pending deposits: <b>{{ note.pending_deposits }}</b></router-link>
            <router-link to="/withdrawals">Pending withdrawals: <b>{{ note.pending_withdrawals }}</b></router-link>
          </div>
          <el-empty v-if="!note.latest?.length" :image-size="60" description="Nothing waiting" />
          <div v-for="n in note.latest" :key="n.kind + n.id" class="bell-item"
               @click="$router.push(n.kind === 'deposit' ? '/deposits' : '/withdrawals')">
            <el-tag size="small" :type="n.kind === 'deposit' ? 'success' : 'danger'">{{ n.kind }}</el-tag>
            #{{ n.id }} · {{ n.username }} · <b>{{ money(n.amount) }}</b> {{ n.currency }}
            <div><small>{{ dt(n.created_at) }}</small></div>
          </div>
          <el-checkbox v-model="sound" size="small" style="margin-top: 6px">Sound for new requests</el-checkbox>
        </el-popover>

        <el-dropdown @command="onCommand">
          <span class="user">{{ session.me?.username }} · {{ session.me?.role }}
            <el-icon v-if="!session.me?.totp_enabled" color="#e6a23c" title="2FA is off"><WarningFilled /></el-icon>
            <el-icon><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item command="2fa" icon="Lock">Two-factor login (2FA): {{ session.me?.totp_enabled ? 'ON' : 'OFF' }}</el-dropdown-item>
              <el-dropdown-item command="logout" icon="SwitchButton" divided>Log out</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main style="padding: 0">
        <router-view v-if="allowed" :key="$route.fullPath" />
        <el-result v-else icon="warning" title="No permission" />
      </el-main>
    </el-container>
    <TwoFactorDialog v-model="twoFaOpen" />
  </el-container>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElNotification } from 'element-plus'
import { can, dt, http, logout, money, session } from '../api'
import TwoFactorDialog from '../components/TwoFactorDialog.vue'

const route = useRoute()
const all = [
  { path: '/members', title: 'Members', icon: 'User', perm: 'member.view' },
  { path: '/agents', title: 'Agents', icon: 'Share', perm: 'member.view' },
  { path: '/deposits', title: 'Deposits', icon: 'Download', perm: 'finance.view', badge: 'deposits' },
  { path: '/withdrawals', title: 'Withdrawals', icon: 'Upload', perm: 'finance.view', badge: 'withdrawals' },
  { path: '/transactions', title: 'Ledger', icon: 'Tickets', perm: 'finance.view' },
  { path: '/channels', title: 'Payment channels', icon: 'CreditCard', perm: 'finance.view' },
  { path: '/reports', title: 'Reports', icon: 'DataLine', perm: 'finance.view' },
  { path: '/sources', title: 'Traffic sources', icon: 'Promotion', perm: 'member.view' },
  { path: '/admins', title: 'Admin users', icon: 'Setting', perm: 'admin.manage' },
  { path: '/audit', title: 'Audit log', icon: 'Document', perm: 'audit.view' }
]
const menu = computed(() => all.filter((m) => can(m.perm)))
const allowed = computed(() => !route.meta.perm || can(route.meta.perm))

// ---------- notifications: poll every 15 s ----------
const note = reactive({ pending_deposits: 0, pending_withdrawals: 0, latest: [] })
const badges = computed(() => ({ deposits: note.pending_deposits, withdrawals: note.pending_withdrawals }))
const pendingTotal = computed(() => note.pending_deposits + note.pending_withdrawals)
let lastSeen = null
let timer = null
let storedSound = true
try { storedSound = localStorage.getItem('notify_sound') !== 'off' } catch { /* ignore */ }
const sound = ref(storedSound)
watch(sound, (v) => { try { localStorage.setItem('notify_sound', v ? 'on' : 'off') } catch { /* ignore */ } })

function beep() {
  try {
    const ctx = new AudioContext()
    const o = ctx.createOscillator()
    o.frequency.value = 880
    o.connect(ctx.destination)
    o.start()
    o.stop(ctx.currentTime + 0.15)
  } catch { /* browser blocked audio */ }
}

async function poll() {
  if (!can('finance.view') || document.hidden) return
  try {
    const { data } = await http.get('/notifications', { silent: true })
    const ids = `${data.last_deposit_id}-${data.last_withdrawal_id}`
    if (lastSeen !== null && ids !== lastSeen && data.latest.length) {
      const n = data.latest[0]
      ElNotification({ title: `New ${n.kind}`, message: `#${n.id} · ${n.username} · ${money(n.amount)} ${n.currency}`, type: 'warning' })
      if (sound.value) beep()
    }
    lastSeen = ids
    Object.assign(note, data)
  } catch { /* shown by interceptor only when not silent */ }
}

const twoFaOpen = ref(false)
function onCommand(cmd) {
  if (cmd === 'logout') logout()
  if (cmd === '2fa') twoFaOpen.value = true
}

onMounted(() => { poll(); timer = setInterval(poll, 15000) })
onBeforeUnmount(() => clearInterval(timer))
</script>

<style scoped>
.aside { background: #1f2d3d; }
.aside :deep(.el-menu) { border-right: none; }
.menu-badge { margin-left: auto; display: flex; align-items: center; line-height: 1; }
.menu-badge :deep(.el-badge__content) { position: static; transform: none; }
.logo { color: #fff; font-weight: 600; padding: 18px 20px; font-size: 16px; }
.header { display: flex; align-items: center; gap: 14px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.spacer { flex: 1; }
.user { cursor: pointer; display: flex; align-items: center; gap: 4px; }
.bell-head { display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 13px; }
.bell-item { padding: 6px 4px; border-top: 1px solid #f0f0f0; cursor: pointer; font-size: 13px; }
.bell-item:hover { background: #f5f7fa; }
</style>
