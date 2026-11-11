<template>
  <div class="page">
    <div class="card">
      <el-tabs v-model="f.status" @tab-change="search">
        <el-tab-pane label="Pending" name="pending" />
        <el-tab-pane label="Approved" name="approved" />
        <el-tab-pane label="Rejected" name="rejected" />
        <el-tab-pane label="All" name="" />
      </el-tabs>
      <div class="toolbar">
        <el-date-picker v-model="f.dates" type="daterange" value-format="YYYY-MM-DD" start-placeholder="From"
                        end-placeholder="To" style="width: 260px" />
        <el-input v-model="f.username" placeholder="Member username" clearable style="width: 180px" @keyup.enter="search" />
        <el-button type="primary" icon="Search" @click="search">Search</el-button>
        <div class="spacer" />
        <span>Total: <b class="money">{{ money(totalAmount) }}</b> ({{ total }})</span>
        <el-button v-if="can('finance.create')" type="primary" plain icon="Plus" @click="openCreate">
          New {{ isDep ? 'deposit' : 'withdrawal' }}
        </el-button>
      </div>

      <el-table :data="rows" v-loading="loading" border stripe height="calc(100vh - 300px)">
        <el-table-column prop="id" label="ID" width="80" />
        <el-table-column prop="brand_name" label="Brand" width="120" />
        <el-table-column prop="username" label="Member" min-width="120" />
        <el-table-column label="Amount" width="150" align="right">
          <template #default="{ row }"><b class="money">{{ money(row.amount) }}</b> {{ row.currency }}</template>
        </el-table-column>
        <template v-if="isDep">
          <el-table-column prop="channel_name" label="Channel" width="130" />
          <el-table-column prop="reference_no" label="Reference" min-width="140" />
        </template>
        <template v-else>
          <el-table-column label="Pay to" min-width="200">
            <template #default="{ row }">{{ row.receive_method }} · {{ row.receive_account }}<br /><small>{{ row.receive_name }}</small></template>
          </el-table-column>
          <el-table-column prop="payout_ref" label="Payout ref" width="120" />
        </template>
        <el-table-column label="Status" width="100">
          <template #default="{ row }"><el-tag :type="statusTag[row.status]" size="small">{{ row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="Created" width="170"><template #default="{ row }">{{ dt(row.created_at) }}<br /><small>{{ row.created_by_name }}</small></template></el-table-column>
        <el-table-column label="Reviewed" width="170"><template #default="{ row }">{{ dt(row.reviewed_at) }}<br /><small>{{ row.reviewed_by_name }}</small></template></el-table-column>
        <el-table-column prop="note" label="Note" min-width="120" show-overflow-tooltip />
        <el-table-column v-if="can('finance.approve')" label="Action" width="170" fixed="right">
          <template #default="{ row }">
            <template v-if="row.status === 'pending'">
              <el-button size="small" type="success" @click="review(row, 'approve')">Approve</el-button>
              <el-button size="small" type="danger" @click="review(row, 'reject')">Reject</el-button>
            </template>
          </template>
        </el-table-column>
      </el-table>
      <div class="pager">
        <el-pagination v-model:current-page="page" :page-size="50" :total="total" layout="total, prev, pager, next"
                       @current-change="load" />
      </div>
    </div>

    <el-dialog v-model="createOpen" :title="isDep ? 'New deposit request' : 'New withdrawal request'" width="460px">
      <el-form label-width="130px">
        <el-form-item label="Member">
          <el-select v-model="form.member_id" filterable remote :remote-method="findMembers" placeholder="Type username"
                     style="width: 100%">
            <el-option v-for="o in memberOptions" :key="o.id" :value="o.id"
                       :label="`${o.username} · ${o.brand_name} · bal ${money(o.balance)}`" />
          </el-select>
        </el-form-item>
        <el-form-item label="Amount"><el-input-number v-model="form.amount" :min="1" :step="1000" style="width: 100%" /></el-form-item>
        <template v-if="isDep">
          <el-form-item label="Channel">
            <el-select v-model="form.channel_id" style="width: 100%">
              <el-option v-for="c in memberChannels" :key="c.id" :value="c.id" :disabled="!c.is_active"
                         :label="`${c.name} (${money(c.min_amount)} - ${money(c.max_amount)})`" />
            </el-select>
          </el-form-item>
          <el-form-item label="Reference no."><el-input v-model="form.reference_no" placeholder="transfer ID from slip" /></el-form-item>
          <el-form-item label="Proof URL"><el-input v-model="form.proof_url" /></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="Method">
            <el-select v-model="form.receive_method" style="width: 100%">
              <el-option v-for="t in ['kbzpay', 'wavepay', 'bank', 'promptpay', 'other']" :key="t" :value="t" :label="t" />
            </el-select>
          </el-form-item>
          <el-form-item label="Account"><el-input v-model="form.receive_account" /></el-form-item>
          <el-form-item label="Account name"><el-input v-model="form.receive_name" /></el-form-item>
        </template>
        <el-form-item label="Note"><el-input v-model="form.note" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createOpen = false">Cancel</el-button>
        <el-button type="primary" :loading="saving" @click="create">Submit</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { brandParam, can, dt, http, money, session, statusTag } from '../api'

const props = defineProps({ kind: { type: String, required: true } }) // deposits | withdrawals
const isDep = computed(() => props.kind === 'deposits')

const f = reactive({ status: 'pending', dates: null, username: '' })
const rows = ref([])
const total = ref(0)
const totalAmount = ref(0)
const page = ref(1)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const p = { ...brandParam(), page: page.value, size: 50 }
    if (f.status) p.status = f.status
    if (f.username) p.username = f.username
    if (f.dates) [p.date_from, p.date_to] = f.dates
    const { data } = await http.get(`/finance/${props.kind}`, { params: p })
    rows.value = data.rows
    total.value = data.total
    totalAmount.value = data.total_amount
  } finally {
    loading.value = false
  }
}
function search() { page.value = 1; load() }

async function review(row, action) {
  const isApprove = action === 'approve'
  const label = isDep.value ? 'deposit' : 'withdrawal'
  const msg = isApprove && !isDep.value
    ? `Pay ${money(row.amount)} to ${row.receive_method} ${row.receive_account} (${row.receive_name}), then enter the transfer ID:`
    : `${isApprove ? 'Approve' : 'Reject'} ${label} #${row.id} of ${money(row.amount)} for ${row.username}? Note:`
  const res = await ElMessageBox.prompt(msg, `${isApprove ? 'Approve' : 'Reject'} ${label}`, {
    confirmButtonText: isApprove ? 'Approve' : 'Reject',
    inputValidator: (v) => (isApprove && !isDep.value && !v ? 'Transfer ID is required' : true)
  }).catch(() => null)
  if (!res) return
  const body = isApprove && !isDep.value ? { payout_ref: res.value } : { note: res.value || null }
  const { data } = await http.post(`/finance/${props.kind}/${row.id}/${action}`, body)
  const extra = data.commissions?.length ? ` · ${data.commissions.length} commission(s) paid` : ''
  ElMessage.success(`#${row.id} ${data.status}${extra}`)
  load()
}

// ---------- create dialog ----------
const createOpen = ref(false)
const saving = ref(false)
const form = reactive({})
const memberOptions = ref([])
const channels = ref([])
const memberChannels = computed(() => {
  const mem = memberOptions.value.find((o) => o.id === form.member_id)
  return channels.value.filter((c) => !mem || c.brand_id === mem.brand_id)
})

async function findMembers(q) {
  if (!q) return
  const { data } = await http.get('/members', { params: { ...brandParam(), username_like: q, size: 20 } })
  memberOptions.value = data.rows
}
async function openCreate() {
  Object.assign(form, { member_id: null, amount: 10000, channel_id: null, reference_no: '', proof_url: '',
                        receive_method: 'kbzpay', receive_account: '', receive_name: '', note: '',
                        request_key: crypto.randomUUID() })
  if (isDep.value) channels.value = (await http.get('/finance/channels', { params: brandParam() })).data
  createOpen.value = true
}
async function create() {
  saving.value = true
  try {
    const b = { member_id: form.member_id, amount: String(form.amount), note: form.note || null, request_key: form.request_key }
    if (isDep.value) Object.assign(b, { channel_id: form.channel_id, reference_no: form.reference_no || null, proof_url: form.proof_url || null })
    else Object.assign(b, { receive_method: form.receive_method, receive_account: form.receive_account, receive_name: form.receive_name })
    await http.post(`/finance/${props.kind}`, b)
    ElMessage.success('Request created')
    createOpen.value = false
    f.status = 'pending'
    search()
  } finally {
    saving.value = false
  }
}

watch(() => session.brandId, search)
onMounted(load)
</script>
