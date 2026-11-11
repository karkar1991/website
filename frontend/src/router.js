import { createRouter, createWebHistory } from 'vue-router'
import { isLoggedIn, loadSession, session } from './api'
import Layout from './views/Layout.vue'

const routes = [
  { path: '/login', component: () => import('./views/Login.vue') },
  {
    path: '/',
    component: Layout,
    redirect: '/members',
    children: [
      { path: 'members', component: () => import('./views/Members.vue'), meta: { title: 'Members', perm: 'member.view' } },
      { path: 'agents', component: () => import('./views/Agents.vue'), meta: { title: 'Agents', perm: 'member.view' } },
      { path: 'sources', component: () => import('./views/Sources.vue'), meta: { title: 'Traffic sources', perm: 'member.view' } },
      { path: 'deposits', component: () => import('./views/Requests.vue'), props: { kind: 'deposits' }, meta: { title: 'Deposits', perm: 'finance.view' } },
      { path: 'withdrawals', component: () => import('./views/Requests.vue'), props: { kind: 'withdrawals' }, meta: { title: 'Withdrawals', perm: 'finance.view' } },
      { path: 'transactions', component: () => import('./views/Transactions.vue'), meta: { title: 'Ledger', perm: 'finance.view' } },
      { path: 'channels', component: () => import('./views/Channels.vue'), meta: { title: 'Payment channels', perm: 'finance.view' } },
      { path: 'reports', component: () => import('./views/Reports.vue'), meta: { title: 'Reports', perm: 'finance.view' } },
      { path: 'admins', component: () => import('./views/Admins.vue'), meta: { title: 'Admin users', perm: 'admin.manage' } },
      { path: 'audit', component: () => import('./views/AuditLogs.vue'), meta: { title: 'Audit log', perm: 'audit.view' } }
    ]
  },
  { path: '/:pathMatch(.*)*', redirect: '/' }
]

const router = createRouter({ history: createWebHistory(), routes })

router.beforeEach(async (to) => {
  if (to.path === '/login') return true
  if (!isLoggedIn()) return '/login'
  if (!session.me) {
    try { await loadSession() } catch { return '/login' }
  }
  return true
})

export default router
