<template>
  <div class="date-range">
    <el-radio-group :model-value="quick" size="default" @change="pick">
      <el-radio-button value="today">Today</el-radio-button>
      <el-radio-button value="yesterday">Yesterday</el-radio-button>
      <el-radio-button value="week">Week</el-radio-button>
      <el-radio-button value="month">Month</el-radio-button>
    </el-radio-group>
    <el-date-picker :model-value="modelValue" type="daterange" value-format="YYYY-MM-DD" unlink-panels
                    :start-placeholder="placeholder" end-placeholder="to" style="width: 240px"
                    @update:model-value="(v) => emit('update:modelValue', v)" />
  </div>
</template>

<script setup>
// Quick buttons like the WG backend (日 / 周 / 月) plus a free date range.
import { computed } from 'vue'

const props = defineProps({ modelValue: Array, placeholder: { type: String, default: 'From' } })
const emit = defineEmits(['update:modelValue', 'change'])

const fmt = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`

function range(kind) {
  const now = new Date()
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate())
  if (kind === 'today') return [fmt(today), fmt(today)]
  if (kind === 'yesterday') { const y = new Date(today); y.setDate(y.getDate() - 1); return [fmt(y), fmt(y)] }
  if (kind === 'week') { const s = new Date(today); s.setDate(s.getDate() - ((s.getDay() + 6) % 7)); return [fmt(s), fmt(today)] }
  return [fmt(new Date(today.getFullYear(), today.getMonth(), 1)), fmt(today)]
}

const quick = computed(() => {
  if (!props.modelValue) return ''
  return ['today', 'yesterday', 'week', 'month'].find((k) => {
    const r = range(k)
    return r[0] === props.modelValue[0] && r[1] === props.modelValue[1]
  }) || ''
})

function pick(kind) {
  const v = range(kind)
  emit('update:modelValue', v)
  emit('change', v)
}
</script>

<style scoped>
.date-range { display: inline-flex; gap: 6px; align-items: center; }
</style>
