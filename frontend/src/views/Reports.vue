<template>
  <div class="page">
    <div class="toolbar">
      <DateRange v-model="dates" @change="load" />
      <el-checkbox v-model="includeTest" @change="load">Include test accounts</el-checkbox>
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
      <el-tabs v-model="tab">
        <el-tab-pane label="Daily" name="daily">
          <el-table :data="daily" border stripe size="small" height="calc(100vh - 520px)" style="min-height: 260px">
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
        </el-tab-pane>
        <el-tab-pane label="By traffic source" name="sources">
          <el-table :data="sources" border stripe size="small" height="calc(100vh - 520px)" style="min-height: 260px">
            <el-table-column prop="brand_name" label="Brand" width="130" />
            <el-table-column prop="source_name" label="Source" min-width="160" />
            <el-table-column prop="new_members" label="New members" width="130" align="right" />
            <el-table-column prop="depositors" label="Depositors" width="120" align="right" />
            <el-table-column label="Conversion" width="120" align="right"><template #default="{ row }">{{ row.conversion_pct }}%</template></el-table-column>
            <el-table-column label="Deposits" align="right"><template #default="{ row }">{{ money(row.deposits) }} <small>{{ row.currency }}</small></template></el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref, watch } from 'vue'
import { brandParam, http, money, session } from '../api'
import DateRange from '../components/DateRange.vue'

const dates = ref(null)
const includeTest = ref(false)
const tab = ref('daily')
const summary = ref([])
const daily = ref([])
const sources = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const p = { ...brandParam(), include_test: includeTest.value }
    if (dates.value) [p.date_from, p.date_to] = dates.value
    const [s, d, src] = await Promise.all([
      http.get('/reports/summary', { params: p }),
      http.get('/reports/daily', { params: p }),
      http.get('/reports/sources', { params: p })
    ])
    summary.value = s.data
    daily.value = d.data
    sources.value = src.data
  } finally {
    loading.value = false
  }
}
watch(() => session.brandId, load)
onMounted(load)
</script>
