import axios from 'axios'
import { ElMessage } from 'element-plus'
import { reactive } from 'vue'

// ---------------- session store ----------------
export const session = reactive({
  me: null,          // { id, username, role, permissions, allowed_brands }
  options: { brands: [], vip_levels: [], member_levels: [], sources: [], tags: [], statuses: [], account_types: [] },
  brandId: null      // global brand filter (null = all allowed brands)
})

export const can = (perm) =>
  !!session.me && (session.me.permissions.includes('*') || session.me.permissions.includes(perm))

const tokens = {
  get access() { return localStorage.getItem('access_token') },
  get refresh() { return localStorage.getItem('refresh_token') },
  set(t) {
    localStorage.setItem('access_token', t.access_token)
    localStorage.setItem('refresh_token', t.refresh_token)
  },
  clear() {
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
  }
}
export const isLoggedIn = () => !!tokens.access

// ---------------- axios ----------------
export const http = axios.create({ baseURL: '/api', timeout: 60000 })

http.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`
  return cfg
})

let refreshing = null
http.interceptors.response.use(
  (r) => r,
  async (err) => {
    const cfg = err.config || {}
    const status = err.response?.status
    if (status === 401 && tokens.refresh && !cfg._retried && !cfg.url.startsWith('/auth/')) {
      cfg._retried = true
      try {
        refreshing ||= axios.post('/api/auth/refresh', { refresh_token: tokens.refresh })
        const { data } = await refreshing
        tokens.set(data)
        return http(cfg)
      } catch {
        logout()
      } finally {
        refreshing = null
      }
    } else if (status === 401) {
      logout()
    }
    if (!cfg.silent) {
      const detail = err.response?.data?.detail
      ElMessage.error(Array.isArray(detail) ? detail.map((d) => d.msg).join(', ') : detail || err.message)
    }
    return Promise.reject(err)
  }
)

export async function login(username, password, otp = null) {
  // silent: the login page shows its own messages (and handles OTP_REQUIRED)
  const { data } = await http.post('/auth/login', { username, password, otp }, { silent: true })
  tokens.set(data)
  await loadSession()
}

export async function loadSession() {
  const [me, opts] = await Promise.all([http.get('/auth/me'), http.get('/options')])
  session.me = me.data
  session.options = opts.data
}

export function logout() {
  tokens.clear()
  session.me = null
  if (location.pathname !== '/login') location.href = '/login'
}

// ---------------- helpers ----------------
export const brandParam = () => (session.brandId ? { brand_id: session.brandId } : {})

export const money = (v) =>
  v === null || v === undefined ? '' : Number(v).toLocaleString(undefined, { maximumFractionDigits: 2 })

export const dt = (v) => (v ? new Date(v).toLocaleString() : '')

export const statusTag = {
  normal: 'success', blacklist: 'danger', leaving: 'warning', left: 'info',
  pending: 'warning', approved: 'success', rejected: 'danger'
}

export async function download(url, params, filename) {
  const res = await http.get(url, { params, responseType: 'blob' })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(res.data)
  a.download = filename
  a.click()
  URL.revokeObjectURL(a.href)
}
