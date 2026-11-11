<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <div class="spacer" />
        <el-button v-if="manage" type="primary" icon="Plus" @click="edit()">Add channel</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="brand_name" label="Brand" width="130" />
        <el-table-column prop="name" label="Name" min-width="140" />
        <el-table-column prop="type" label="Type" width="100" />
        <el-table-column prop="account_name" label="Account name" min-width="140" />
        <el-table-column prop="account_no" label="Account no." min-width="140" />
        <el-table-column label="Limits" width="200"><template #default="{ row }">{{ money(row.min_amount) }} – {{ money(row.max_amount) }}</template></el-table-column>
        <el-table-column label="Active" width="90">
          <template #default="{ row }"><el-switch :model-value="row.is_active" :disabled="!manage" @change="(v) => toggle(row, v)" /></template>
        </el-table-column>
        <el-table-column v-if="manage" label="" width="90">
          <template #default="{ row }"><el-button size="small" @click="edit(row)">Edit</el-button></template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="open" :title="form.id ? 'Edit channel' : 'Add channel'" width="440px">
      <el-form label-width="120px">
        <el-form-item label="Brand" v-if="!form.id">
          <el-select v-model="form.brand_id"><el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" /></el-select>
        </el-form-item>
        <el-form-item label="Name"><el-input v-model="form.name" /></el-form-item>
        <el-form-item label="Type" v-if="!form.id">
          <el-select v-model="form.type"><el-option v-for="t in ['kbzpay', 'wavepay', 'bank', 'promptpay', 'other']" :key="t" :label="t" :value="t" /></el-select>
        </el-form-item>
        <el-form-item label="Account name"><el-input v-model="form.account_name" /></el-form-item>
        <el-form-item label="Account no."><el-input v-model="form.account_no" /></el-form-item>
        <el-form-item label="Min amount"><el-input-number v-model="form.min_amount" :min="0" :step="1000" /></el-form-item>
        <el-form-item label="Max amount"><el-input-number v-model="form.max_amount" :min="1" :step="100000" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="open = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { brandParam, can, http, money, session } from '../api'

const manage = computed(() => can('channel.manage'))
const rows = ref([])
const loading = ref(false)
const open = ref(false)
const form = reactive({})

async function load() {
  loading.value = true
  try { rows.value = (await http.get('/finance/channels', { params: brandParam() })).data } finally { loading.value = false }
}
function edit(row) {
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, row
    ? { ...row, min_amount: Number(row.min_amount), max_amount: Number(row.max_amount) }
    : { brand_id: session.brandId || session.options.brands[0]?.id, name: '', type: 'kbzpay', account_name: '', account_no: '', min_amount: 1000, max_amount: 5000000 })
  open.value = true
}
async function save() {
  const b = { name: form.name, account_name: form.account_name, account_no: form.account_no,
              min_amount: String(form.min_amount), max_amount: String(form.max_amount) }
  if (form.id) await http.patch(`/finance/channels/${form.id}`, b)
  else await http.post('/finance/channels', { ...b, brand_id: form.brand_id, type: form.type })
  ElMessage.success('Saved')
  open.value = false
  load()
}
async function toggle(row, v) {
  await http.patch(`/finance/channels/${row.id}`, { is_active: v })
  row.is_active = v
}
watch(() => session.brandId, load)
onMounted(load)
</script>
