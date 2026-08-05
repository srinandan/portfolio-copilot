<template>
  <section class="bg-surface-container rounded-xl p-lg shadow-sm flex flex-col gap-md border border-outline/10">
    <h3 class="font-title-sm text-title-sm text-on-surface border-b border-outline/20 pb-2">Asset Allocation</h3>
    <div class="flex flex-col gap-4">
      <div v-for="item in allocations" :key="item.label" class="flex items-center justify-between">
        <div class="flex items-center gap-sm">
          <div :class="['w-3 h-3 rounded-full', item.colorClass]"></div>
          <span class="font-body-mono text-body-mono text-on-surface">{{ item.label }}</span>
        </div>
        <div class="flex items-center gap-md">
          <span class="font-body-base text-body-base text-on-surface-variant">{{ item.percent }}%</span>
          <span class="font-body-mono text-body-mono text-on-surface w-[80px] text-right tabular-nums">{{ item.amount }}</span>
        </div>
      </div>
    </div>
    <div class="h-2.5 w-full flex rounded-full overflow-hidden mt-sm opacity-90">
      <div
        v-for="item in allocations"
        :key="item.label"
        :class="[item.colorClass, 'h-full transition-all duration-300']"
        :style="{ width: `${item.percent}%` }"
      ></div>
    </div>
  </section>
</template>

<script setup lang="ts">
const allocations = [
  { label: 'Equities (US)', percent: 55, amount: '$686.6K', colorClass: 'bg-primary-fixed' },
  { label: 'Equities (Intl)', percent: 25, amount: '$312.1K', colorClass: 'bg-secondary-fixed' },
  { label: 'Fixed Income', percent: 15, amount: '$187.2K', colorClass: 'bg-tertiary-fixed-dim' },
  { label: 'Cash/Equiv', percent: 5, amount: '$62.4K', colorClass: 'bg-outline' }
];
</script>
