<template>
  <el-dialog :model-value="modelValue" title="Import members" width="640px" @close="close">
    <el-steps :active="step" finish-status="success" simple style="margin-bottom: 16px">
      <el-step title="Choose file" /><el-step title="Check" /><el-step title="Import" />
    </el-steps>

    <el-form label-width="90px">
      <el-form-item label="Brand">
        <el-select v-model="brandId" @change="result = null; step = 0">
          <el-option v-for="b in session.options.brands" :key="b.id" :label="b.name" :value="b.id" />
        </el-select>
      </el-form-item>
      <el-form-item label="File">
        <input ref="fileInput" type="file" accept=".xlsx,.csv" @change="onFile" />
        <el-button link type="primary" style="margin-left: 8px" @click="template">Download template</el-button>
      </el-form-item>
    </el-form>

    <el-alert type="info" :closable="false" show-icon style="margin-bottom: 12px">
      Columns: username, full_name, phone, inviter_username, account_type (formal/test), vip_level (0-5),
      member_level (name), source_code. Inviter can be an existing member or a row above in the same file.
      Nothing is saved until every row is valid.
    </el-alert>

    <template v-if="result">
      <el-result v-if="result.imported" icon="success" :title="`${result.imported} members imported`" />
      <template v-else>
        <p>
          Rows: <b>{{ result.total_rows }}</b> · Valid: <b class="plus">{{ result.valid_rows }}</b> ·
          Errors: <b :class="result.error_count ? 'minus' : ''">{{ result.error_count }}</b>
        </p>
        <el-table v-if="result.errors.length" :data="result.errors" size="small" max-height="260" border>
          <el-table-column prop="row" label="Row" width="70" />
          <el-table-column prop="username" label="Username" width="150" />
          <el-table-column label="Problem"><template #default="{ row }">{{ row.errors.join('; ') }}</template></el-table-column>
        </el-table>
      </template>
    </template>

    <template #footer>
      <el-button @click="close">Close</el-button>
      <el-button :disabled="!file" :loading="busy" @click="run(true)">Check file</el-button>
      <el-button type="primary" :disabled="!result || result.error_count > 0 || !!result.imported || !result.total_rows"
                 :loading="busy" @click="run(false)">Import {{ result?.valid_rows || '' }} rows</el-button>
    </template>
  </el-dialog>
</template>

<script setup>
import { ref, watch } from 'vue'
import { download, http, session } from '../api'

const props = defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue', 'done'])

const brandId = ref(null)
const file = ref(null)
const fileInput = ref(null)
const result = ref(null)
const busy = ref(false)
const step = ref(0)

watch(() => props.modelValue, (open) => {
  if (open) {
    brandId.value = session.brandId || session.options.brands[0]?.id
    file.value = null
    result.value = null
    step.value = 0
    if (fileInput.value) fileInput.value.value = ''
  }
})

function onFile(e) {
  file.value = e.target.files[0] || null
  result.value = null
  step.value = file.value ? 1 : 0
}

async function run(dryRun) {
  busy.value = true
  try {
    const fd = new FormData()
    fd.append('brand_id', brandId.value)
    fd.append('dry_run', dryRun ? 'true' : 'false')
    fd.append('file', file.value)
    const { data } = await http.post('/members/import', fd)
    result.value = data
    step.value = data.imported ? 3 : data.error_count ? 1 : 2
    if (data.imported) emit('done')
  } finally {
    busy.value = false
  }
}

const template = () => download('/members/import-template', {}, 'member_import_template.xlsx')
const close = () => emit('update:modelValue', false)
</script>
