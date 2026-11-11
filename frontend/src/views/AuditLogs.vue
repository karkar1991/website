<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <el-input v-model="f.action" placeholder="Action (e.g. deposit.)" clearable style="width: 200px" @keyup.enter="search" />
        <el-input v-model="f.admin_username" placeholder="Admin username" clearable style="width: 160px" @keyup.enter="search" />
        <el-input v-model="f.target_id" placeholder="Target ID" clearable style="width: 120px" @keyup.enter="search" />
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 240px)">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column label="Time" width="170"><template #default="{ row }">{{ dt(row.created_at) }}</template></el-table-column>
        <el-table-column prop="admin_name" label="Admin" width="120" />
        <el-table-column prop="action" label="Action" width="180" />
        <el-table-column prop="target_id" label="Target" width="100" />
        <el-table-column label="Detail" min-width="300">
          <template #default="{ row }"><code style="font-size: 12px">{{ JSON.stringify(row.detail) }}</code></template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="total, prev, pager, next" @current-change="load" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { dt, http } from '../api'

const f = reactive({ action: '', admin_username: '', target_id: '' })
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const p = { page: page.value, size: 50 }
    for (const k of Object.keys(f)) if (f[k]) p[k] = f[k]
    const { data } = await http.get('/admin/audit-logs', { params: p })
    rows.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}
function search() { page.value = 1; load() }
onMounted(load)
</script>
