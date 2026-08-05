<template>
  <section class="bg-surface-container rounded-xl p-lg shadow-sm flex flex-col gap-sm relative overflow-hidden border border-outline/10">
    <div class="flex items-center justify-between relative z-10">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Total Net Worth</h2>
      <div class="flex items-center gap-xs text-tertiary-fixed-dim bg-tertiary-container/30 px-2 py-1 rounded">
        <span class="material-symbols-outlined text-[16px]">trending_up</span>
        <span class="font-body-mono text-body-mono">+2.4%</span>
      </div>
    </div>
    <div class="font-display-lg text-display-lg text-on-surface relative z-10 tabular-nums">
      <span class="font-body-mono text-[32px]">$</span>{{ formattedNetWorth }}<span class="font-body-mono text-[24px] text-on-surface-variant">.00</span>
    </div>
    <p class="font-body-mono text-body-mono text-on-surface-variant relative z-10">Updated today, 09:41 AM</p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    totalValue?: number;
  }>(),
  {
    totalValue: 1248500
  }
);

const formattedNetWorth = computed(() => {
  return props.totalValue.toLocaleString('en-US');
});
</script>
