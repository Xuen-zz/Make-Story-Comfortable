<script setup lang="ts">
import { useWorkflowCanvas } from '@/composables/useWorkflowCanvas'

const props = defineProps<{
  id: string
  data: {
    label: string
    color?: string
  }
}>()

const wf = useWorkflowCanvas()

function onLabelChange(val: string) {
  const node = wf.nodes.value.find(n => n.id === props.id)
  if (node) node.data.label = val
}
</script>

<template>
  <div
    class="w-full h-full rounded-2xl border-2 border-dashed border-zinc-600/55 bg-zinc-400/[0.03] pointer-events-auto relative"
  >
    <div class="px-3 py-1.5 flex items-center justify-between bg-[#1b1e25]/95 rounded-t-xl border-b border-[#2a2e39]">
      <input
        :value="data.label"
        @input="onLabelChange(($event.target as HTMLInputElement).value)"
        class="!bg-transparent !border-0 text-xs font-bold text-zinc-200 focus:outline-none nodrag w-full"
      />
      <button
        @click.stop="wf.deleteNode(id)"
        type="button"
        title="删除分组框（不删内部节点时请先拖出）"
        class="text-xs text-rose-400 hover:text-rose-300 ml-2 nodrag cursor-pointer"
      >
        ✕
      </button>
    </div>
  </div>
</template>
