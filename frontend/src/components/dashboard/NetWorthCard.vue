<template>
  <section class="bg-surface-container rounded-xl p-lg shadow-sm flex flex-col gap-sm relative overflow-hidden border border-outline/10" data-testid="net-worth-card">
    <div class="flex items-center justify-between relative z-10">
      <h2 class="font-label-caps text-xs text-on-surface-variant uppercase tracking-wider">Total Net Worth</h2>
    </div>
    <div class="font-body-mono text-3xl sm:text-4xl font-bold text-on-surface relative z-10 tabular-nums" data-testid="net-worth-value">
      ${{ formattedNetWorth }}
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
  return props.totalValue.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
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
