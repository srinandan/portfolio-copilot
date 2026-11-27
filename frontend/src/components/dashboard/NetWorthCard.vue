<template>
  <section
    :class="[
      'flex flex-col gap-2',
      embedded
        ? 'p-lg'
        : 'bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet'
    ]"
    data-testid="net-worth-card"
  >
    <div class="flex items-baseline justify-between gap-md flex-wrap">
      <h2 class="font-sans text-meta font-medium text-on-surface-variant">Total Net Worth</h2>
      <p v-if="formattedAsOf" class="font-sans text-meta text-on-surface-variant tabular-nums">
        {{ formattedAsOf }}
      </p>
    </div>

    <div
      class="font-display text-display-figure font-medium text-on-surface tabular-nums tracking-tight"
      data-testid="net-worth-value"
    >
      ${{ formattedNetWorth }}
    </div>

    <p
      v-if="cashUsd !== undefined && cashUsd > 0"
      class="font-sans text-meta text-on-surface-variant tabular-nums"
    >
      Includes ${{ formattedCash }} in cash and equivalents
    </p>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    totalValue?: number;
    cashUsd?: number;
    asOf?: string;
    embedded?: boolean;
  }>(),
  {
    totalValue: 0,
    cashUsd: undefined,
    asOf: undefined,
    embedded: false
  }
);

const formattedNetWorth = computed(() => {
  return props.totalValue.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
});

const formattedCash = computed(() => {
  return (props.cashUsd ?? 0).toLocaleString('en-US', {
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
