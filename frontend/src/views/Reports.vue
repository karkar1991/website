<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="From"
                      end-placeholder="To" style="width: 260px" />
      <el-button type="primary" icon="Search" @click="load">Show</el-button>
    </div>

    <el-row :gutter="12" v-loading="loading">
      <el-col v-for="s in summary" :key="s.brand_id" :span="24 / Math.min(summary.length || 1, 2)" style="margin-bottom: 12px">
        <div class="card">
          <h3 style="margin-top: 0">{{ s.brand_name }} <small>({{ s.currency }})</small></h3>
          <el-row :gutter="12">
            <el-col :span="6"><el-statistic title="New members" :value="s.new_members" /></el-col>
            <el-col :span="6"><el-statistic title="Deposits" :value="Number(s.deposits)" /></el-col>
            <el-col :span="6"><el-statistic title="Withdrawals" :value="Number(s.withdrawals)" /></el-col>
            <el-col :span="6"><el-statistic title="Commissions" :value="Number(s.commissions)" /></el-col>
          </el-row>
          <el-row :gutter="12" style="margin-top: 12px">
            <el-col :span="6"><el-statistic title="Total members" :value="s.total_members" /></el-col>
            <el-col :span="6"><el-statistic title="Wallet balances" :value="Number(s.total_balance)" /></el-col>
            <el-col :span="6"><el-statistic title="Pending deposits" :value="s.pending_deposits" /></el-col>
            <el-col :span="6"><el-statistic title="Pending withdrawals" :value="s.pending_withdrawals" /></el-col>
          </el-row>
        </div>
      </el-col>
    </el-row>

    <div class="card">
      <h3 style="margin-top: 0">Daily</h3>
      <el-table :data="daily" border stripe size="small" height="calc(100vh - 470px)">
        <el-table-column prop="day" label="Day" width="120" />
        <el-table-column prop="brand_name" label="Brand" width="130" />
        <el-table-column prop="new_members" label="New members" width="120" align="right" />
        <el-table-column label="Deposits" align="right"><template #default="{ row }">{{ money(row.deposits) }}</template></el-table-column>
        <el-table-column label="Withdrawals" align="right"><template #default="{ row }">{{ money(row.withdrawals) }}</template></el-table-column>
        <el-table-column label="Commissions" align="right"><template #default="{ row }">{{ money(row.commissions) }}</template></el-table-column>
        <el-table-column label="Net" align="right">
          <template #default="{ row }"><b :class="row.net < 0 ? 'minus' : 'plus'">{{ money(row.net) }}</b></template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { brandParam, http, money, session } from '../api'

const dates = ref(null)
const summary = ref([])
const daily = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const p = { ...brandParam() }
    if (dates.value) [p.date_from, p.date_to] = dates.value
    const [s, d] = await Promise.all([http.get('/reports/summary', { params: p }), http.get('/reports/daily', { params: p })])
    summary.value = s.data
    daily.value = d.data
  } finally {
    loading.value = false
  }
}
watch(() => session.brandId, load)
onMounted(load)
</script>
