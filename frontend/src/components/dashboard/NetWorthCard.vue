<template>
  <section class="bg-surface-container rounded-xl p-lg shadow-sm flex flex-col gap-sm relative overflow-hidden border border-outline/10">
    <div class="flex items-center justify-between relative z-10">
      <h2 class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Total Net Worth</h2>
    </div>
    <div class="font-display-lg text-display-lg text-on-surface relative z-10 tabular-nums">
      <span class="font-body-mono text-[32px]">$</span>{{ formattedNetWorth }}<span class="font-body-mono text-[24px] text-on-surface-variant">.00</span>
    </div>
    <p v-if="formattedAsOf" class="font-body-mono text-xs text-on-surface-variant relative z-10">
      {{ formattedAsOf }}
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    totalValue?: number;
    asOf?: string;
  }>(),
  {
    totalValue: 0,
    asOf: undefined
  }
);

const formattedNetWorth = computed(() => {
  return props.totalValue.toLocaleString('en-US');
});

const formattedAsOf = computed(() => {
  if (!props.asOf) return '';
  const d = new Date(props.asOf);
  if (isNaN(d.getTime())) {
    return `As of ${props.asOf}`;
  }
  const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  const timeStr = d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
  return `Updated ${dateStr}, ${timeStr}`;
});
</script>
