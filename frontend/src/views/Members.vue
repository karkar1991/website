<template>
  <div class="page">
    <div class="card">
      <el-tabs v-model="f.status" @tab-change="search">
        <el-tab-pane label="All members" name="" />
        <el-tab-pane label="Blacklist" name="blacklist" />
        <el-tab-pane label="Leaving" name="leaving" />
        <el-tab-pane label="Left" name="left" />
      </el-tabs>

      <div class="toolbar">
        <el-date-picker v-model="f.dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="Registered from"
                        end-placeholder="to" style="width: 260px" />
        <el-input v-model="f.username" placeholder="Exact username" clearable style="width: 160px" @keyup.enter="search" />
        <el-input v-model="f.username_like" placeholder="Username contains" clearable style="width: 160px" @keyup.enter="search" />
        <el-input v-model="f.inviter" placeholder="Inviter username" clearable style="width: 160px" @keyup.enter="search" />
        <el-select v-model="f.vip_level" placeholder="VIP" clearable style="width: 100px">
          <el-option v-for="l in vipLevels" :key="l" :label="`VIP${l}`" :value="l" />
        </el-select>
        <el-select v-model="f.tag_id" placeholder="Tag" clearable style="width: 150px">
          <el-option v-for="t in tags" :key="t.id" :label="tagLabel(t)" :value="t.id" />
        </el-select>
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
        <el-button @click="reset">Reset</el-button>
        <div class="spacer" />
        <el-button v-if="can('member.edit')" type="primary" plain icon="Plus" @click="openCreate">Add member</el-button>
        <el-button v-if="can('member.export')" icon="Download" :loading="exporting" @click="exportXlsx">Export</el-button>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 330px)"
                @selection-change="(s) => (selected = s)" @row-dblclick="(r) => (detailId = r.id)">
        <el-table-column type="selection" width="40" />
        <el-table-column prop="brand_name" label="Brand" width="120" />
        <el-table-column label="ID" width="90">
          <template #default="{ row }"><el-link type="primary" @click="detailId = row.id">{{ row.id }}</el-link></template>
        </el-table-column>
        <el-table-column label="Username" min-width="140">
          <template #default="{ row }">
            <el-tag size="small" type="warning" effect="plain" style="margin-right: 4px">{{ row.vip_name }}</el-tag>
            {{ row.username }}
          </template>
        </el-table-column>
        <el-table-column label="Status" width="100">
          <template #default="{ row }"><el-tag :type="statusTag[row.status]" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column prop="full_name" label="Name" width="120" />
        <el-table-column label="Inviter" min-width="130">
          <template #default="{ row }">{{ row.inviter_username }}<br /><small>{{ row.inviter_id }}</small></template>
        </el-table-column>
        <el-table-column label="Top agent" min-width="130">
          <template #default="{ row }">{{ row.top_agent_username }}<br /><small>{{ row.top_agent_id }}</small></template>
        </el-table-column>
        <el-table-column label="Balance" width="140" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.balance) }} {{ row.currency }}</span></template>
        </el-table-column>
        <el-table-column label="Registered" width="170">
          <template #default="{ row }">{{ dt(row.created_at) }}</template>
        </el-table-column>
      </el-table>

      <div class="pager" style="justify-content: space-between">
        <div v-if="can('member.edit')">
          <el-dropdown :disabled="!selected.length" @command="bulk">
            <el-button>Bulk action ({{ selected.length }}) <el-icon><ArrowDown /></el-icon></el-button>
            <template #dropdown>
              <el-dropdown-menu>
                <el-dropdown-item v-for="s in session.options.statuses" :key="s" :command="s">Set status: {{ s }}</el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>
        </div>
        <el-pagination v-model:current-page="page" v-model:page-size="size" :total="total"
                       :page-sizes="[50, 100, 200, 500]" layout="total, sizes, prev, pager, next, jumper"
                       @current-change="load" @size-change="search" />
      </div>
    </div>

    <MemberDrawer v-model="detailId" @changed="load" />

    <el-dialog v-model="createOpen" title="Add member" width="420px">
      <el-form label-width="110px">
        <el-form-item label="Brand">
          <el-select v-model="newM.brand_id"><el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" /></el-select>
        </el-form-item>
        <el-form-item label="Username"><el-input v-model="newM.username" /></el-form-item>
        <el-form-item label="Full name"><el-input v-model="newM.full_name" /></el-form-item>
        <el-form-item label="Phone"><el-input v-model="newM.phone" /></el-form-item>
        <el-form-item label="Inviter"><el-input v-model="newM.inviter_username" placeholder="username (optional)" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">Cancel</el-button>
        <el-button type="primary" @click="create">Create</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { brandParam, can, download, dt, http, money, session, statusTag } from '../api'
import MemberDrawer from './MemberDrawer.vue'

const blank = () => ({ status: '', dates: null, username: '', username_like: '', inviter: '', vip_level: null, tag_id: null })
const f = reactive(blank())
const rows = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(100)
const loading = ref(false)
const exporting = ref(false)
const selected = ref([])
const detailId = ref(null)

const vipLevels = computed(() => [...new Set(session.options.vip_levels.map((v) => v.level))])
const tags = computed(() => session.options.tags.filter((t) => !session.brandId || t.brand_id === session.brandId))
const brandName = (id) => session.options.brands.find((b) => b.id === id)?.name
const tagLabel = (t) => (session.brandId ? t.name : `${t.name} · ${brandName(t.brand_id)}`)

function params() {
  const p = { ...brandParam() }
  for (const k of ['status', 'username', 'username_like', 'inviter', 'vip_level', 'tag_id']) {
    if (f[k] !== '' && f[k] !== null) p[k] = f[k]
  }
  if (f.dates) [p.date_from, p.date_to] = f.dates
  return p
}

async function load() {
  loading.value = true
  try {
    const { data } = await http.get('/members', { params: { ...params(), page: page.value, size: size.value } })
    rows.value = data.rows
    total.value = data.total
  } finally {
    loading.value = false
  }
}
function search() { page.value = 1; load() }
function reset() { Object.assign(f, blank()); search() }

async function exportXlsx() {
  exporting.value = true
  try { await download('/members/export', params(), 'members.xlsx') } finally { exporting.value = false }
}

async function bulk(status) {
  const res = await ElMessageBox.prompt(
    `Set ${selected.value.length} member(s) to "${status}"? Optional note:`, 'Bulk status', { inputValue: '' }
  ).catch(() => null)
  if (!res) return
  const note = res.value
  const { data } = await http.post('/members/bulk-status', { ids: selected.value.map((r) => r.id), status, note })
  ElMessage.success(`${data.updated} updated`)
  load()
}

const createOpen = ref(false)
const newM = reactive({})
function openCreate() {
  Object.assign(newM, { brand_id: session.brandId || session.options.brands[0]?.id, username: '', full_name: '', phone: '', inviter_username: '' })
  createOpen.value = true
}
async function create() {
  const body = { ...newM, inviter_username: newM.inviter_username || null }
  const { data } = await http.post('/members', body)
  ElMessage.success(`Member ${data.username} created`)
  createOpen.value = false
  search()
}

watch(() => session.brandId, search)
onMounted(load)
</script>
