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
        <DateRange v-model="f.dates" placeholder="Registered from" @change="search" />
        <el-input v-model="f.username" placeholder="Exact username" clearable style="width: 150px" @keyup.enter="search" />
        <el-input v-model="f.username_like" placeholder="Username contains" clearable style="width: 150px" @keyup.enter="search" />
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
        <el-button @click="reset">Reset</el-button>
        <el-button link type="primary" @click="more = !more">{{ more ? 'Less filters' : 'More filters' }}</el-button>
        <div class="spacer" />
        <el-button v-if="can('member.edit')" type="primary" plain icon="Plus" @click="openCreate">Add member</el-button>
        <el-button v-if="can('member.edit')" icon="Upload" @click="importOpen = true">Import</el-button>
        <el-button v-if="can('member.export')" icon="Download" :loading="exporting" @click="exportXlsx">Export</el-button>
      </div>
      <div class="toolbar" v-show="more">
        <el-input v-model="f.inviter" placeholder="Inviter username" clearable style="width: 150px" @keyup.enter="search" />
        <el-input v-model="f.phone" placeholder="Phone" clearable style="width: 140px" @keyup.enter="search" />
        <el-select v-model="f.account_type" placeholder="Account type" clearable style="width: 130px">
          <el-option label="Formal" value="formal" /><el-option label="Test" value="test" />
        </el-select>
        <el-select v-model="f.vip_level" placeholder="VIP" clearable style="width: 100px">
          <el-option v-for="l in vipLevels" :key="l" :label="`VIP${l}`" :value="l" />
        </el-select>
        <el-select v-model="f.member_level_id" placeholder="Member level" clearable style="width: 160px">
          <el-option v-for="l in byBrand(session.options.member_levels)" :key="l.id" :label="label(l.name, l)" :value="l.id" />
        </el-select>
        <el-select v-model="f.source_id" placeholder="Source" clearable style="width: 170px">
          <el-option v-for="s in byBrand(session.options.sources)" :key="s.id" :label="label(s.name, s)" :value="s.id" />
        </el-select>
        <el-select v-model="f.tag_id" placeholder="Tag" clearable style="width: 150px">
          <el-option v-for="t in byBrand(session.options.tags)" :key="t.id" :label="label(t.name, t)" :value="t.id" />
        </el-select>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 340px)"
                @selection-change="(s) => (selected = s)" @row-dblclick="(r) => (detailId = r.id)">
        <el-table-column type="selection" width="40" fixed />
        <el-table-column v-if="show.brand" prop="brand_name" label="Brand" width="120" />
        <el-table-column label="ID" width="90" fixed>
          <template #default="{ row }"><el-link type="primary" @click="detailId = row.id">{{ row.id }}</el-link></template>
        </el-table-column>
        <el-table-column label="Username" min-width="150">
          <template #default="{ row }">
            <el-tag size="small" type="warning" effect="plain" style="margin-right: 4px">{{ row.vip_name }}</el-tag>
            {{ row.username }}
          </template>
        </el-table-column>
        <el-table-column v-if="show.status" label="Status" width="100">
          <template #default="{ row }"><el-tag :type="statusTag[row.status]" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column v-if="show.account_type" label="Account type" width="110">
          <template #default="{ row }"><el-tag :type="row.account_type === 'test' ? 'info' : 'primary'" size="small" effect="plain">{{ row.account_type }}</el-tag></template>
        </el-table-column>
        <el-table-column v-if="show.member_level" prop="member_level" label="Level" width="100" />
        <el-table-column v-if="show.full_name" prop="full_name" label="Name" width="120" />
        <el-table-column v-if="show.phone" prop="phone" label="Phone" width="120" />
        <el-table-column v-if="show.inviter" label="Inviter" min-width="130">
          <template #default="{ row }">{{ row.inviter_username }}<br /><small>{{ row.inviter_id }}</small></template>
        </el-table-column>
        <el-table-column v-if="show.top_agent" label="Top agent" min-width="130">
          <template #default="{ row }">{{ row.top_agent_username }}<br /><small>{{ row.top_agent_id }}</small></template>
        </el-table-column>
        <el-table-column v-if="show.source" prop="source_name" label="Source" width="120" />
        <el-table-column v-if="show.balance" label="Balance" width="140" align="right">
          <template #default="{ row }"><span class="money">{{ money(row.balance) }} {{ row.currency }}</span></template>
        </el-table-column>
        <el-table-column v-if="show.created_at" label="Registered" width="170">
          <template #default="{ row }">{{ dt(row.created_at) }}</template>
        </el-table-column>
        <el-table-column width="44" fixed="right" align="center">
          <template #header>
            <el-popover placement="bottom-end" :width="190" trigger="click">
              <template #reference><el-icon style="cursor: pointer"><Setting /></el-icon></template>
              <div style="font-weight: 600; margin-bottom: 6px">Columns</div>
              <el-checkbox v-for="(lbl, key) in columnLabels" :key="key" v-model="show[key]" :label="lbl"
                           style="display: flex; height: 26px" />
            </el-popover>
          </template>
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

    <!-- add member -->
    <el-dialog v-model="createOpen" title="Add member" width="460px">
      <el-form label-width="120px">
        <el-form-item label="Brand">
          <el-select v-model="newM.brand_id" @change="newM.member_level_id = newM.source_id = null">
            <el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Username"><el-input v-model="newM.username" /></el-form-item>
        <el-form-item label="Full name"><el-input v-model="newM.full_name" /></el-form-item>
        <el-form-item label="Phone"><el-input v-model="newM.phone" /></el-form-item>
        <el-form-item label="Inviter"><el-input v-model="newM.inviter_username" placeholder="username (optional)" /></el-form-item>
        <el-form-item label="Account type">
          <el-radio-group v-model="newM.account_type"><el-radio value="formal">Formal</el-radio><el-radio value="test">Test</el-radio></el-radio-group>
        </el-form-item>
        <el-form-item label="Member level">
          <el-select v-model="newM.member_level_id" clearable placeholder="lowest">
            <el-option v-for="l in session.options.member_levels.filter((x) => x.brand_id === newM.brand_id)" :key="l.id" :label="l.name" :value="l.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="Source">
          <el-select v-model="newM.source_id" clearable>
            <el-option v-for="s in session.options.sources.filter((x) => x.brand_id === newM.brand_id && x.is_active)" :key="s.id" :label="s.name" :value="s.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">Cancel</el-button>
        <el-button type="primary" @click="create">Create</el-button>
      </template>
    </el-dialog>

    <ImportDialog v-model="importOpen" @done="search" />
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { brandParam, can, download, dt, http, money, session, statusTag } from '../api'
import DateRange from '../components/DateRange.vue'
import ImportDialog from '../components/ImportDialog.vue'
import MemberDrawer from './MemberDrawer.vue'

const blank = () => ({ status: '', dates: null, username: '', username_like: '', inviter: '', phone: '',
  account_type: null, vip_level: null, member_level_id: null, source_id: null, tag_id: null })
const f = reactive(blank())
const more = ref(false)
const rows = ref([])
const total = ref(0)
const page = ref(1)
const size = ref(100)
const loading = ref(false)
const exporting = ref(false)
const selected = ref([])
const detailId = ref(null)
const importOpen = ref(false)

// ---------- column chooser (remembered in this browser) ----------
const columnLabels = { brand: 'Brand', status: 'Status', account_type: 'Account type', member_level: 'Level',
  full_name: 'Name', phone: 'Phone', inviter: 'Inviter', top_agent: 'Top agent', source: 'Source',
  balance: 'Balance', created_at: 'Registered' }
const defaults = { brand: true, status: true, account_type: true, member_level: true, full_name: false, phone: false,
  inviter: true, top_agent: true, source: false, balance: true, created_at: true }
let saved = {}
try { saved = JSON.parse(localStorage.getItem('member_columns') || '{}') } catch { saved = {} }
const show = reactive({ ...defaults, ...saved })
watch(show, (v) => { try { localStorage.setItem('member_columns', JSON.stringify(v)) } catch { /* ignore */ } })

// ---------- options ----------
const vipLevels = computed(() => [...new Set(session.options.vip_levels.map((v) => v.level))])
const byBrand = (list) => list.filter((x) => !session.brandId || x.brand_id === session.brandId)
const brandName = (id) => session.options.brands.find((b) => b.id === id)?.name
const label = (name, x) => (session.brandId ? name : `${name} · ${brandName(x.brand_id)}`)

function params() {
  const p = { ...brandParam() }
  for (const k of ['status', 'username', 'username_like', 'inviter', 'phone', 'account_type', 'vip_level',
    'member_level_id', 'source_id', 'tag_id']) {
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
  const { data } = await http.post('/members/bulk-status', { ids: selected.value.map((r) => r.id), status, note: res.value })
  ElMessage.success(`${data.updated} updated`)
  load()
}

const createOpen = ref(false)
const newM = reactive({})
function openCreate() {
  Object.assign(newM, { brand_id: session.brandId || session.options.brands[0]?.id, username: '', full_name: '', phone: '',
    inviter_username: '', account_type: 'formal', member_level_id: null, source_id: null })
  createOpen.value = true
}
async function create() {
  const body = { ...newM, inviter_username: newM.inviter_username || null }
  const { data } = await http.post('/members', body)
  ElMessage.success(`Member ${data.username} created`)
  createOpen.value = false
  search()
}

const route = useRoute()
watch(() => session.brandId, search)
onMounted(() => {
  // opened from the Agents page: show that agent's direct invites
  if (route.query.inviter) {
    f.inviter = String(route.query.inviter)
    more.value = true
    if (route.query.brand && Number(route.query.brand) !== session.brandId) {
      session.brandId = Number(route.query.brand) // the watcher reloads
      return
    }
  }
  load()
})
</script>
