<template>
  <div class="page">
    <div class="card">
      <div class="toolbar">
        <div class="spacer" />
        <el-button type="primary" icon="Plus" @click="edit()">Add admin</el-button>
      </div>
      <el-table :data="rows" v-loading="loading" border stripe>
        <el-table-column prop="id" label="ID" width="70" />
        <el-table-column prop="username" label="Username" />
        <el-table-column prop="role" label="Role" width="140" />
        <el-table-column label="Brands"><template #default="{ row }">{{ row.allowed_brands.map(brandName).join(', ') }}</template></el-table-column>
        <el-table-column label="2FA" width="80">
          <template #default="{ row }"><el-tag size="small" :type="row.totp_enabled ? 'success' : 'warning'">{{ row.totp_enabled ? 'ON' : 'OFF' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="Last login" width="170"><template #default="{ row }">{{ dt(row.last_login_at) }}</template></el-table-column>
        <el-table-column label="Active" width="80">
          <template #default="{ row }"><el-switch :model-value="row.is_active" @change="(v) => patch(row.id, { is_active: v })" /></template>
        </el-table-column>
        <el-table-column label="" width="250">
          <template #default="{ row }">
            <el-button size="small" @click="edit(row)">Edit</el-button>
            <el-button v-if="isLocked(row)" size="small" type="warning" @click="patch(row.id, { unlock: true })">Unlock</el-button>
            <el-popconfirm v-if="row.totp_enabled" title="Turn off 2FA for this admin (lost phone)?" @confirm="patch(row.id, { reset_2fa: true })">
              <template #reference><el-button size="small" type="danger" plain>Reset 2FA</el-button></template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-card style="margin-top: 12px">
      <template #header>Roles</template>
      <el-table :data="roles" size="small">
        <el-table-column prop="name" label="Role" width="160" />
        <el-table-column label="Permissions"><template #default="{ row }"><el-tag v-for="p in row.permissions" :key="p" size="small" style="margin: 2px">{{ p }}</el-tag></template></el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="open" :title="form.id ? `Edit ${form.username}` : 'Add admin'" width="440px">
      <el-form label-width="120px">
        <el-form-item label="Username" v-if="!form.id"><el-input v-model="form.username" /></el-form-item>
        <el-form-item :label="form.id ? 'New password' : 'Password'"><el-input v-model="form.password" type="password" show-password placeholder="min 8 characters" /></el-form-item>
        <el-form-item label="Role">
          <el-select v-model="form.role_id"><el-option v-for="r in roles" :key="r.id" :label="r.name" :value="r.id" /></el-select>
        </el-form-item>
        <el-form-item label="Brands">
          <el-select v-model="form.allowed_brands" multiple style="width: 100%">
            <el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="open = false">Cancel</el-button>
        <el-button type="primary" @click="save">Save</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { dt, http, session } from '../api'

const rows = ref([])
const roles = ref([])
const loading = ref(false)
const open = ref(false)
const form = reactive({})
const isLocked = (row) => row.locked_until && new Date(row.locked_until) > new Date()
const brandName = (id) => session.options.brands.find((b) => b.id === id)?.name || `#${id}`

async function load() {
  loading.value = true
  try {
    const [u, r] = await Promise.all([http.get('/admin/users'), http.get('/admin/roles')])
    rows.value = u.data
    roles.value = r.data
  } finally {
    loading.value = false
  }
}
function edit(row) {
  Object.keys(form).forEach((k) => delete form[k])
  Object.assign(form, row ? { id: row.id, username: row.username, role_id: row.role_id, allowed_brands: [...row.allowed_brands], password: '' }
    : { username: '', password: '', role_id: roles.value[0]?.id, allowed_brands: [] })
  open.value = true
}
async function patch(id, body) {
  await http.patch(`/admin/users/${id}`, body)
  ElMessage.success('Saved')
  load()
}
async function save() {
  if (form.id) {
    const b = { role_id: form.role_id, allowed_brands: form.allowed_brands }
    if (form.password) b.password = form.password
    await patch(form.id, b)
  } else {
    await http.post('/admin/users', { username: form.username, password: form.password, role_id: form.role_id, allowed_brands: form.allowed_brands })
    ElMessage.success('Admin created')
    load()
  }
  open.value = false
}
onMounted(load)
</script>
