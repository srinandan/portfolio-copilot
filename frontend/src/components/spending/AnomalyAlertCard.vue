<template>
  <div
    v-if="anomalies && anomalies.length > 0"
    class="bg-error-container/20 border border-error/40 rounded-xl p-md flex flex-col gap-sm shadow-sm"
    data-testid="anomaly-alert-card"
  >
    <div class="flex items-center justify-between">
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-error">warning</span>
        <h3 class="font-title-sm text-title-sm text-on-surface">Spending Anomalies Detected</h3>
      </div>
      <span class="font-label-caps text-label-caps bg-error text-on-error px-2 py-0.5 rounded uppercase">
        {{ anomalies.length }} Flagged
      </span>
    </div>

    <div class="flex flex-col gap-xs mt-xs">
      <div
        v-for="anom in anomalies"
        :key="anom.category"
        class="bg-surface-container-lowest/80 p-sm rounded-lg flex flex-col sm:flex-row sm:items-center justify-between gap-xs border border-surface-variant"
        data-testid="anomaly-item"
      >
        <div class="flex flex-col">
          <span class="font-body-mono text-xs font-bold uppercase text-on-surface">{{ anom.category }}</span>
          <span class="font-body-base text-sm text-on-surface-variant">{{ anom.description }}</span>
        </div>
        <div class="flex flex-col items-start sm:items-end tabular-nums font-body-mono text-xs">
          <span class="text-error font-semibold">Spend: ${{ anom.amount_usd.toFixed(2) }}</span>
          <span class="text-on-surface-variant">3-Mo Avg: ${{ anom.trailing_average_usd.toFixed(2) }}</span>
        </div>
      </div>
    </div>

    <p v-if="narrativeSummary" class="font-body-base text-xs text-on-surface-variant italic mt-1">
      {{ narrativeSummary }}
    </p>
  </div>
</template>

<script setup lang="ts">
import type { SpendingAnomaly } from '../../types';

defineProps<{
  anomalies: SpendingAnomaly[];
  narrativeSummary?: string;
}>();
</script>
