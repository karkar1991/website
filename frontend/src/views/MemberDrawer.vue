<template>
  <el-drawer :model-value="!!modelValue" size="680px" :title="m ? `${m.username} (#${m.id})` : ''"
             @close="emit('update:modelValue', null)">
    <div v-if="m" v-loading="loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Brand">{{ m.brand_name }}</el-descriptions-item>
        <el-descriptions-item label="Status"><el-tag :type="statusTag[m.status]" size="small">{{ m.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="Account type">{{ m.account_type }}</el-descriptions-item>
        <el-descriptions-item label="VIP / Level">{{ m.vip_name }} · {{ m.member_level }}</el-descriptions-item>
        <el-descriptions-item label="Name">{{ m.full_name }}</el-descriptions-item>
        <el-descriptions-item label="Phone">{{ m.phone }}</el-descriptions-item>
        <el-descriptions-item label="Inviter">{{ m.inviter_username }}</el-descriptions-item>
        <el-descriptions-item label="Top agent">{{ m.top_agent_username }}</el-descriptions-item>
        <el-descriptions-item label="Source">{{ m.source_name }}</el-descriptions-item>
        <el-descriptions-item label="Registered">{{ dt(m.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="Direct invites">{{ m.direct_invites }}</el-descriptions-item>
        <el-descriptions-item label="Whole downline">{{ m.downline_total }}</el-descriptions-item>
        <el-descriptions-item label="Balance"><b class="money">{{ money(m.balance) }} {{ m.currency }}</b></el-descriptions-item>
        <el-descriptions-item label="Frozen"><span class="money">{{ money(m.frozen) }}</span></el-descriptions-item>
      </el-descriptions>

      <el-tabs v-model="tab" style="margin-top: 12px">
        <el-tab-pane v-if="can('finance.view')" label="Wallet ledger" name="ledger">
          <div class="toolbar" v-if="can('finance.approve')">
            <el-input-number v-model="adj.amount" :step="1000" controls-position="right" style="width: 170px" />
            <el-input v-model="adj.note" placeholder="Reason (required)" style="width: 230px" />
            <el-button type="warning" @click="adjust" :disabled="!adj.amount || adj.note.length < 3">Adjust balance</el-button>
          </div>
          <el-table :data="ledger" size="small" max-height="380">
            <el-table-column label="Time" width="160"><template #default="{ row }">{{ dt(row.created_at) }}</template></el-table-column>
            <el-table-column prop="type" label="Type" width="100" />
            <el-table-column label="Amount" align="right">
              <template #default="{ row }"><span :class="row.amount < 0 ? 'minus' : 'plus'">{{ money(row.amount) }}</span></template>
            </el-table-column>
            <el-table-column label="Balance" align="right"><template #default="{ row }">{{ money(row.balance_after) }}</template></el-table-column>
            <el-table-column prop="note" label="Note" show-overflow-tooltip />
          </el-table>
        </el-tab-pane>

        <el-tab-pane label="Referral tree" name="tree">
          <el-tree ref="tree" :props="{ label: 'label', isLeaf: 'leaf' }" :load="loadChildren" lazy node-key="key"
                   :key="m.id" @node-click="onNodeClick">
            <template #default="{ data }">
              <span v-if="data.more" class="more">Load more…</span>
              <span v-else>{{ data.label }}
                <el-tag v-if="data.status && data.status !== 'normal'" size="small" :type="statusTag[data.status]">{{ data.status }}</el-tag>
              </span>
            </template>
          </el-tree>
        </el-tab-pane>

        <el-tab-pane v-if="can('member.edit')" label="Edit" name="edit">
          <el-form label-width="120px" style="max-width: 460px">
            <el-form-item label="Full name"><el-input v-model="edit.full_name" /></el-form-item>
            <el-form-item label="Phone"><el-input v-model="edit.phone" /></el-form-item>
            <el-form-item label="Account type">
              <el-radio-group v-model="edit.account_type"><el-radio value="formal">Formal</el-radio><el-radio value="test">Test</el-radio></el-radio-group>
            </el-form-item>
            <el-form-item label="VIP">
              <el-select v-model="edit.vip_level_id"><el-option v-for="v in brandList('vip_levels')" :key="v.id" :label="v.name" :value="v.id" /></el-select>
            </el-form-item>
            <el-form-item label="Member level">
              <el-select v-model="edit.member_level_id"><el-option v-for="l in brandList('member_levels')" :key="l.id" :label="l.name" :value="l.id" /></el-select>
            </el-form-item>
            <el-form-item label="Source">
              <el-select v-model="edit.source_id" clearable><el-option v-for="s in brandList('sources')" :key="s.id" :label="s.name" :value="s.id" /></el-select>
            </el-form-item>
            <el-form-item><el-button type="primary" @click="saveEdit">Save</el-button></el-form-item>
            <el-divider />
            <el-form-item label="Status">
              <el-select v-model="status" style="width: 150px">
                <el-option v-for="s in session.options.statuses" :key="s" :label="s" :value="s" />
              </el-select>
              <el-button style="margin-left: 8px" @click="saveStatus" :disabled="status === m.status">Change status</el-button>
            </el-form-item>
            <el-form-item label="Tags">
              <el-select v-model="tagIds" multiple style="width: 250px">
                <el-option v-for="t in brandList('tags')" :key="t.id" :label="t.name" :value="t.id" />
              </el-select>
              <el-button style="margin-left: 8px" @click="saveTags">Save tags</el-button>
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-drawer>
</template>

<script setup>
import { reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { can, dt, http, money, session, statusTag } from '../api'

const props = defineProps({ modelValue: Number })
const emit = defineEmits(['update:modelValue', 'changed'])

const m = ref(null)
const ledger = ref([])
const loading = ref(false)
const tab = ref(can('finance.view') ? 'ledger' : 'tree')
const status = ref('')
const tagIds = ref([])
const adj = reactive({ amount: 0, note: '' })
const edit = reactive({})
const tree = ref(null)
const brandList = (key) => session.options[key].filter((x) => x.brand_id === m.value?.brand_id)

async function load() {
  if (!props.modelValue) { m.value = null; return }
  loading.value = true
  try {
    const { data } = await http.get(`/members/${props.modelValue}`)
    m.value = data
    status.value = data.status
    tagIds.value = data.tags.map((t) => t.id)
    Object.assign(edit, { full_name: data.full_name, phone: data.phone, account_type: data.account_type,
      vip_level_id: data.vip_level_id, member_level_id: data.member_level_id, source_id: data.source_id })
    if (can('finance.view')) {
      const r = await http.get('/finance/transactions', { params: { member_id: data.id, size: 100 } })
      ledger.value = r.data.rows
    }
  } finally {
    loading.value = false
  }
}

// ---------- referral tree, 100 children per page with "Load more" ----------
const PAGE = 100
const toNode = (c) => ({ key: `m${c.id}`, id: c.id, label: `${c.username} (#${c.id}) · ${c.children} invites`, status: c.status, leaf: !c.children })

async function fetchChildren(parentId, page) {
  const { data } = await http.get(`/members/${parentId}/children`, { params: { page, size: PAGE } })
  const nodes = data.rows.map(toNode)
  if (data.has_more) nodes.push({ key: `more-${parentId}-${page}`, more: true, parentId, page: page + 1, leaf: true })
  return nodes
}

async function loadChildren(node, resolve) {
  if (node.level === 0) {
    return resolve([{ key: `m${m.value.id}`, id: m.value.id, label: `${m.value.username} (#${m.value.id})`,
      status: m.value.status, leaf: !m.value.direct_invites }])
  }
  resolve(await fetchChildren(node.data.id, 1))
}

async function onNodeClick(data, node) {
  if (!data.more) return
  const parent = node.parent
  const nodes = await fetchChildren(data.parentId, data.page)
  tree.value.remove(data)
  nodes.forEach((n) => tree.value.append(n, parent))
}

// ---------- actions ----------
async function saveEdit() {
  await http.patch(`/members/${m.value.id}`, { ...edit, full_name: edit.full_name || null, phone: edit.phone || null })
  ElMessage.success('Saved')
  emit('changed'); load()
}
async function saveStatus() {
  await http.patch(`/members/${m.value.id}/status`, { status: status.value })
  ElMessage.success('Status updated')
  emit('changed'); load()
}
async function saveTags() {
  await http.put(`/members/${m.value.id}/tags`, { tag_ids: tagIds.value })
  ElMessage.success('Tags saved')
}
async function adjust() {
  await http.post('/finance/adjust', { member_id: m.value.id, amount: String(adj.amount), note: adj.note })
  ElMessage.success('Balance adjusted')
  adj.amount = 0; adj.note = ''
  emit('changed'); load()
}

watch(() => props.modelValue, load)
</script>

<style scoped>
.more { color: #409eff; cursor: pointer; }
</style>
