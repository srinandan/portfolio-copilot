<template>
  <section
    :class="[
      'flex flex-col gap-md',
      embedded
        ? 'p-lg'
        : 'bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet'
    ]"
  >
    <div class="flex items-baseline justify-between gap-md">
      <h3 class="font-sans text-heading font-semibold text-on-surface">Asset Allocation</h3>
      <span class="font-sans text-meta text-on-surface-variant">
        {{ hasLiveHoldings ? 'Current mix' : 'Baseline model' }}
      </span>
    </div>

    <!-- Proportion Bar -->
    <div class="h-2.5 w-full flex rounded-full overflow-hidden bg-surface-container-low gap-[2px]">
      <div
        v-for="item in allocations"
        :key="item.label"
        :class="[item.colorClass, 'h-full transition-[width] duration-200 ease-desk first:rounded-l-full last:rounded-r-full']"
        :style="{ width: `${item.percent}%` }"
      ></div>
    </div>

    <!-- Breakdown Rows -->
    <div class="divide-y divide-outline-variant/60">
      <div
        v-for="item in allocations"
        :key="item.label"
        class="py-2.5 first:pt-0 last:pb-0 flex items-center justify-between gap-md"
      >
        <div class="flex items-center gap-2.5 min-w-0">
          <span :class="['w-2.5 h-2.5 rounded-sm shrink-0', item.colorClass]" aria-hidden="true"></span>
          <span class="font-sans text-body text-on-surface truncate">{{ item.label }}</span>
        </div>
        <div class="flex items-center gap-lg shrink-0 tabular-nums">
          <span class="font-sans text-meta text-on-surface-variant w-12 text-right">{{ item.percent }}%</span>
          <span class="font-sans text-body font-medium text-on-surface w-24 text-right">{{ item.amount }}</span>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { HoldingsSnapshot } from '../../types';

const props = withDefaults(
  defineProps<{
    holdings?: HoldingsSnapshot;
    embedded?: boolean;
  }>(),
  {
    holdings: undefined,
    embedded: false
  }
);

const seriesColors = [
  'bg-primary',
  'bg-primary-fixed',
  'bg-on-tertiary-container',
  'bg-outline',
  'bg-secondary'
];

const fallbackAllocations = [
  { label: 'Equities (US)', percent: 55, amount: '$686.6K', colorClass: 'bg-primary' },
  { label: 'Equities (Intl)', percent: 25, amount: '$312.1K', colorClass: 'bg-primary-fixed' },
  { label: 'Fixed Income', percent: 15, amount: '$187.2K', colorClass: 'bg-on-tertiary-container' },
  { label: 'Cash/Equiv', percent: 5, amount: '$62.4K', colorClass: 'bg-outline' }
];

function formatCompactUsd(val: number): string {
  if (val >= 1_000_000) return `$${(val / 1_000_000).toFixed(2)}M`;
  if (val >= 1_000) return `$${(val / 1_000).toFixed(1)}K`;
  return `$${val.toFixed(0)}`;
}

const hasLiveHoldings = computed(() => {
  return Boolean(props.holdings && (props.holdings.positions?.length || 0) > 0 && props.holdings.total_value_usd > 0);
});

const allocations = computed(() => {
  if (!hasLiveHoldings.value || !props.holdings) {
    return fallbackAllocations;
  }

  const buckets: Record<string, number> = {};
  for (const pos of props.holdings.positions) {
    const cls = pos.asset_class || 'Other';
    const val = pos.current_value_usd ?? pos.market_value_usd ?? (pos.quantity * (pos.current_price_usd ?? 0));
    buckets[cls] = (buckets[cls] || 0) + val;
  }
  if (props.holdings.cash_usd > 0) {
    buckets['Cash/Equiv'] = (buckets['Cash/Equiv'] || 0) + props.holdings.cash_usd;
  }

  const total = Object.values(buckets).reduce((sum, v) => sum + v, 0);
  if (total <= 0) return fallbackAllocations;

  return Object.entries(buckets)
    .sort((a, b) => b[1] - a[1])
    .map(([label, val], idx) => ({
      label,
      percent: Math.round((val / total) * 100),
      amount: formatCompactUsd(val),
      colorClass: seriesColors[idx % seriesColors.length]
    }));
});
</script>
