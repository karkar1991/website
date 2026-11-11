<template>
  <div class="page">
    <div class="card">
      <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
        A traffic source records where a member came from (Facebook ads, TikTok, telesale team, a referral link ...).
        Set it when adding or importing members, then compare sources on the Reports page.
      </el-alert>
      <div class="toolbar">
        <div class="spacer" />
        <el-button v-if="can('source.manage')" type="primary" icon="Plus" @click="openAdd">Add source</el-button>
      </div>
      <el-table :data="rows" border stripe>
        <el-table-column label="Brand" width="140"><template #default="{ row }">{{ brandName(row.brand_id) }}</template></el-table-column>
        <el-table-column prop="code" label="Code" width="180" />
        <el-table-column label="Name">
          <template #default="{ row }">
            <el-input v-if="editing === row.id" v-model="editName" size="small" style="width: 220px" @keyup.enter="saveName(row)" />
            <span v-else>{{ row.name }}</span>
          </template>
        </el-table-column>
        <el-table-column label="Active" width="90">
          <template #default="{ row }"><el-switch :model-value="row.is_active" :disabled="!can('source.manage')" @change="(v) => patch(row, { is_active: v })" /></template>
        </el-table-column>
        <el-table-column v-if="can('source.manage')" label="" width="120">
          <template #default="{ row }">
            <el-button v-if="editing === row.id" size="small" type="primary" @click="saveName(row)">Save</el-button>
            <el-button v-else size="small" @click="editing = row.id; editName = row.name">Rename</el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-dialog v-model="addOpen" title="Add traffic source" width="420px">
      <el-form label-width="80px">
        <el-form-item label="Brand">
          <el-select v-model="form.brand_id"><el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" /></el-select>
        </el-form-item>
        <el-form-item label="Code"><el-input v-model="form.code" placeholder="e.g. fb_nov_2026 (a-z, 0-9, _ -)" /></el-form-item>
        <el-form-item label="Name"><el-input v-model="form.name" placeholder="Facebook ads – November" /></el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="addOpen = false">Cancel</el-button>
        <el-button type="primary" @click="add">Add</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { can, http, loadSession, session } from '../api'

const rows = computed(() => session.options.sources.filter((s) => !session.brandId || s.brand_id === session.brandId))
const brandName = (id) => session.options.brands.find((b) => b.id === id)?.name
const editing = ref(null)
const editName = ref('')
const addOpen = ref(false)
const form = reactive({})

function openAdd() {
  Object.assign(form, { brand_id: session.brandId || session.options.brands[0]?.id, code: '', name: '' })
  addOpen.value = true
}
async function add() {
  await http.post('/sources', { ...form, code: form.code.trim().toLowerCase() })
  ElMessage.success('Source added')
  addOpen.value = false
  await loadSession()
}
async function patch(row, body) {
  await http.patch(`/sources/${row.id}`, body)
  await loadSession()
}
async function saveName(row) {
  await patch(row, { name: editName.value })
  editing.value = null
}
</script>
