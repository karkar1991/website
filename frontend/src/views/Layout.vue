<template>
  <el-container style="height: 100%">
    <el-aside width="210px" class="aside">
      <div class="logo">Member Admin</div>
      <el-menu :default-active="$route.path" router background-color="#1f2d3d" text-color="#bfcbd9"
               active-text-color="#409eff">
        <el-menu-item v-for="m in menu" :key="m.path" :index="m.path">
          <el-icon><component :is="m.icon" /></el-icon>
          <span>{{ m.title }}</span>
        </el-menu-item>
      </el-menu>
    </el-aside>
    <el-container>
      <el-header class="header">
        <strong>{{ $route.meta.title }}</strong>
        <div class="spacer" />
        <el-select v-model="session.brandId" placeholder="All brands" clearable style="width: 200px">
          <el-option v-for="b in session.options.brands" :key="b.id" :label="`${b.name} (${b.currency})`"
                     :value="b.id" />
        </el-select>
        <el-dropdown @command="logout">
          <span class="user">{{ session.me?.username }} · {{ session.me?.role }}
            <el-icon><ArrowDown /></el-icon></span>
          <template #dropdown>
            <el-dropdown-menu><el-dropdown-item command="logout">Log out</el-dropdown-item></el-dropdown-menu>
          </template>
        </el-dropdown>
      </el-header>
      <el-main style="padding: 0">
        <router-view v-if="allowed" :key="$route.fullPath" />
        <el-result v-else icon="warning" title="No permission" />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup>
import { computed } from 'vue'
import { useRoute } from 'vue-router'
import { can, logout, session } from '../api'

const route = useRoute()
const all = [
  { path: '/members', title: 'Members', icon: 'User', perm: 'member.view' },
  { path: '/deposits', title: 'Deposits', icon: 'Download', perm: 'finance.view' },
  { path: '/withdrawals', title: 'Withdrawals', icon: 'Upload', perm: 'finance.view' },
  { path: '/transactions', title: 'Ledger', icon: 'Tickets', perm: 'finance.view' },
  { path: '/channels', title: 'Payment channels', icon: 'CreditCard', perm: 'finance.view' },
  { path: '/reports', title: 'Reports', icon: 'DataLine', perm: 'finance.view' },
  { path: '/admins', title: 'Admin users', icon: 'Setting', perm: 'admin.manage' },
  { path: '/audit', title: 'Audit log', icon: 'Document', perm: 'audit.view' }
]
const menu = computed(() => all.filter((m) => can(m.perm)))
const allowed = computed(() => !route.meta.perm || can(route.meta.perm))
</script>

<style scoped>
.aside { background: #1f2d3d; }
.aside :deep(.el-menu) { border-right: none; }
.logo { color: #fff; font-weight: 600; padding: 18px 20px; font-size: 16px; }
.header { display: flex; align-items: center; gap: 12px; background: #fff; border-bottom: 1px solid #e4e7ed; }
.spacer { flex: 1; }
.user { cursor: pointer; display: flex; align-items: center; gap: 4px; }
</style>
