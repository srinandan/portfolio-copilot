<template>
  <section
    v-if="anomalies && anomalies.length > 0"
    class="bg-surface-container-lowest border border-error/30 border-l-4 border-l-error rounded-xl shadow-sheet overflow-hidden flex flex-col"
    data-testid="anomaly-alert-card"
  >
    <div class="px-lg py-4 bg-error-container/40 border-b border-error/20 flex items-baseline justify-between gap-md flex-wrap">
      <div class="flex items-center gap-2">
        <span class="material-symbols-outlined text-[20px] text-error" aria-hidden="true">warning</span>
        <h3 class="font-sans text-heading font-semibold text-on-surface">Spending Anomalies Detected</h3>
      </div>
      <span class="font-sans text-meta font-semibold text-on-error-container tabular-nums">
        {{ anomalies.length }} flagged
      </span>
    </div>

    <div class="divide-y divide-outline-variant/60">
      <div
        v-for="anom in anomalies"
        :key="anom.category"
        class="px-lg py-3.5 flex flex-col sm:flex-row sm:items-center justify-between gap-sm"
        data-testid="anomaly-item"
      >
        <div class="flex flex-col gap-0.5">
          <span class="font-sans text-body font-semibold capitalize text-on-surface">{{ anom.category }}</span>
          <span class="font-sans text-body text-on-surface-variant max-w-[65ch]">{{ anom.description }}</span>
        </div>
        <div class="flex flex-col items-start sm:items-end tabular-nums shrink-0">
          <span class="font-sans text-body font-semibold text-error">Spend: ${{ anom.amount_usd.toFixed(2) }}</span>
          <span class="font-sans text-meta text-on-surface-variant">3-mo avg: ${{ anom.trailing_average_usd.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <div
      v-if="narrativeSummary"
      class="px-lg py-3 border-t border-outline-variant/60 bg-surface-container-low/40"
    >
      <p class="font-sans text-meta text-on-surface-variant max-w-[65ch]">
        {{ narrativeSummary }}
      </p>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { SpendingAnomaly } from '../../types';

defineProps<{
  anomalies: SpendingAnomaly[];
  narrativeSummary?: string;
}>();
</script>
