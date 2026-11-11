<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <DateRange v-model="f.dates" placeholder="Period from" @change="search" />
        <el-input v-model="f.username" placeholder="Agent username" clearable style="width: 170px" @keyup.enter="search" />
        <el-checkbox v-model="f.top_only" @change="search">Top agents only</el-checkbox>
        <el-select v-model="f.sort" style="width: 190px" @change="search">
          <el-option label="Sort: direct invites" value="direct" />
          <el-option label="Sort: new members" value="new_members" />
          <el-option label="Sort: team deposits" value="deposits" />
          <el-option label="Sort: commission earned" value="commission" />
        </el-select>
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
        <div class="spacer" />
        <small v-if="period">Period: {{ period }}</small>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 250px)">
        <el-table-column prop="brand_name" label="Brand" width="120" />
        <el-table-column label="Agent" min-width="160">
          <template #default="{ row }">
            <el-link type="primary" @click="detailId = row.id">{{ row.username }}</el-link> <small>#{{ row.id }}</small>
            <el-tag v-if="row.depth === 0" size="small" type="success" effect="plain" style="margin-left: 4px">top</el-tag>
            <el-tag v-if="row.status !== 'normal'" size="small" :type="statusTag[row.status]" style="margin-left: 4px">{{ row.status }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="Direct invites" width="120" align="right">
          <template #default="{ row }"><el-link @click="openInvites(row)">{{ row.direct }}</el-link></template>
        </el-table-column>
        <el-table-column prop="downline" label="Whole team" width="110" align="right" />
        <el-table-column prop="new_members" label="New in period" width="120" align="right" />
        <el-table-column label="Team deposits" width="160" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.deposits) }}</span> <small>{{ row.currency }}</small></template>
        </el-table-column>
        <el-table-column label="Commission earned" width="160" align="right">
          <template #default="{ row }"><span class="money plus">{{ money(row.commission) }}</span></template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="total, prev, pager, next, jumper" @current-change="load" />
      </div>
    </div>
    <MemberDrawer v-model="detailId" />
  </div>
</template>

<script setup>
import { onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { brandParam, http, money, session, statusTag } from '../api'
import DateRange from '../components/DateRange.vue'
import MemberDrawer from './MemberDrawer.vue'

const router = useRouter()
const f = reactive({ dates: null, username: '', top_only: false, sort: 'direct' })
const rows = ref([])
const total = ref(0)
const page = ref(1)
const loading = ref(false)
const period = ref('')
const detailId = ref(null)

async function load() {
  loading.value = true
  try {
    const p = { ...brandParam(), page: page.value, size: 50, sort: f.sort, top_only: f.top_only }
    if (f.username) p.username = f.username
    if (f.dates) [p.date_from, p.date_to] = f.dates
    const { data } = await http.get('/agents', { params: p })
    rows.value = data.rows
    total.value = data.total
    period.value = `${data.date_from} → ${data.date_to}`
  } finally {
    loading.value = false
  }
}
function search() { page.value = 1; load() }
const openInvites = (row) => router.push({ path: '/members', query: { inviter: row.username, brand: row.brand_id } })

watch(() => session.brandId, search)
onMounted(load)
</script>
