<template>
  <el-drawer :model-value="!!modelValue" size="640px" :title="m ? `${m.username} (#${m.id})` : ''"
             @close="emit('update:modelValue', null)">
    <div v-if="m" v-loading="loading">
      <el-descriptions :column="2" border size="small">
        <el-descriptions-item label="Brand">{{ m.brand_name }}</el-descriptions-item>
        <el-descriptions-item label="VIP">{{ m.vip_name }}</el-descriptions-item>
        <el-descriptions-item label="Status"><el-tag :type="statusTag[m.status]" size="small">{{ m.status }}</el-tag></el-descriptions-item>
        <el-descriptions-item label="Registered">{{ dt(m.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="Name">{{ m.full_name }}</el-descriptions-item>
        <el-descriptions-item label="Phone">{{ m.phone }}</el-descriptions-item>
        <el-descriptions-item label="Inviter">{{ m.inviter_username }}</el-descriptions-item>
        <el-descriptions-item label="Top agent">{{ m.top_agent_username }}</el-descriptions-item>
        <el-descriptions-item label="Direct invites">{{ m.direct_invites }}</el-descriptions-item>
        <el-descriptions-item label="Whole downline">{{ m.downline_total }}</el-descriptions-item>
        <el-descriptions-item label="Balance"><b class="money">{{ money(m.balance) }} {{ m.currency }}</b></el-descriptions-item>
        <el-descriptions-item label="Frozen"><span class="money">{{ money(m.frozen) }}</span></el-descriptions-item>
      </el-descriptions>

      <div class="toolbar" style="margin-top: 12px" v-if="can('member.edit')">
        <el-select v-model="status" style="width: 140px">
          <el-option v-for="s in session.options.statuses" :key="s" :label="s" :value="s" />
        </el-select>
        <el-button @click="saveStatus" :disabled="status === m.status">Change status</el-button>
        <el-select v-model="tagIds" multiple placeholder="Tags" style="width: 220px">
          <el-option v-for="t in brandTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-button @click="saveTags">Save tags</el-button>
      </div>
      <div class="toolbar" v-if="can('finance.approve')">
        <el-input-number v-model="adj.amount" :step="1000" controls-position="right" style="width: 170px" />
        <el-input v-model="adj.note" placeholder="Reason (required)" style="width: 220px" />
        <el-button type="warning" @click="adjust" :disabled="!adj.amount || adj.note.length < 3">Adjust balance</el-button>
      </div>

      <el-tabs v-model="tab">
        <el-tab-pane label="Wallet ledger" name="ledger">
          <el-table :data="ledger" size="small" max-height="360">
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
          <el-tree :props="{ label: 'label', isLeaf: 'leaf' }" :load="loadChildren" lazy :key="m.id">
            <template #default="{ data }">
              <span>{{ data.label }} <el-tag v-if="data.status && data.status !== 'normal'" size="small" :type="statusTag[data.status]">{{ data.status }}</el-tag></span>
            </template>
          </el-tree>
        </el-tab-pane>
      </el-tabs>
    </div>
  </el-drawer>
</template>

<script setup>
import { computed, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { can, dt, http, money, session, statusTag } from '../api'

const props = defineProps({ modelValue: Number })
const emit = defineEmits(['update:modelValue', 'changed'])

const m = ref(null)
const ledger = ref([])
const loading = ref(false)
const tab = ref('ledger')
const status = ref('')
const tagIds = ref([])
const adj = reactive({ amount: 0, note: '' })
const brandTags = computed(() => session.options.tags.filter((t) => t.brand_id === m.value?.brand_id))

async function load() {
  if (!props.modelValue) { m.value = null; return }
  loading.value = true
  try {
    const { data } = await http.get(`/members/${props.modelValue}`)
    m.value = data
    status.value = data.status
    tagIds.value = data.tags.map((t) => t.id)
    if (can('finance.view')) {
      const r = await http.get('/finance/transactions', { params: { member_id: data.id, size: 100 } })
      ledger.value = r.data.rows
    }
  } finally {
    loading.value = false
  }
}

async function loadChildren(node, resolve) {
  const id = node.level === 0 ? m.value.id : node.data.id
  if (node.level === 0) return resolve([{ id, label: `${m.value.username} (#${id})`, status: m.value.status, leaf: !m.value.direct_invites }])
  const { data } = await http.get(`/members/${id}/children`)
  resolve(data.rows.map((c) => ({ id: c.id, label: `${c.username} (#${c.id}) · ${c.children} invites`, status: c.status, leaf: !c.children })))
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
