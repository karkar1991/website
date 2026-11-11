<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <DateRange v-model="f.dates" @change="search" />
        <el-input v-model="f.username" placeholder="Member username" clearable style="width: 180px" @keyup.enter="search" />
        <el-select v-model="f.type" placeholder="Type" clearable style="width: 140px">
          <el-option v-for="t in ['deposit', 'withdraw', 'commission', 'adjust']" :key="t" :label="t" :value="t" />
        </el-select>
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 240px)">
        <el-table-column prop="id" label="ID" width="90" />
        <el-table-column label="Time" width="170"><template #default="{ row }">{{ dt(row.created_at) }}</template></el-table-column>
        <el-table-column prop="username" label="Member" min-width="120" />
        <el-table-column prop="type" label="Type" width="110" />
        <el-table-column label="Amount" width="140" align="right">
          <template #default="{ row }"><span class="money" :class="row.amount < 0 ? 'minus' : 'plus'">{{ money(row.amount) }}</span></template>
        </el-table-column>
        <el-table-column label="Balance after" width="140" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.balance_after) }}</span></template>
        </el-table-column>
        <el-table-column label="Reference" width="150"><template #default="{ row }">{{ row.ref_type }} #{{ row.ref_id.slice(0, 8) }}</template></el-table-column>
        <el-table-column prop="admin_name" label="By" width="110" />
        <el-table-column prop="note" label="Note" min-width="160" show-overflow-tooltip />
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="total, prev, pager, next" @current-change="load" />
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import DateRange from '../components/DateRange.vue'
import { brandParam, dt, http, money, session } from '../api'

const f = reactive({ dates: null, username: '', type: '' })
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const p = { ...brandParam(), page: page.value, size: 50 }
    if (f.username) p.username = f.username
    if (f.type) p.type = f.type
    if (f.dates) [p.date_from, p.date_to] = f.dates
    const { data } = await http.get('/finance/transactions', { params: p })
    rows.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}
function search() { page.value = 1; load() }
watch(() => session.brandId, search)
onMounted(load)
</script>
