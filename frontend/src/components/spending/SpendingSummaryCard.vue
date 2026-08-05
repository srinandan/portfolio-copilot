<template>
  <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-md w-full" data-testid="spending-summary-card">
    <!-- Total Income -->
    <div class="bg-surface-container rounded-xl p-md border border-outline/10 flex flex-col gap-xs shadow-sm">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Total Income</span>
      <span class="font-body-mono text-xl text-on-surface tabular-nums font-bold">
        ${{ formatCurrency(report.total_income_usd) }}
      </span>
      <span class="font-body-base text-xs text-on-surface-variant">Trailing 30 Days</span>
    </div>

    <!-- Total Outflow -->
    <div class="bg-surface-container rounded-xl p-md border border-outline/10 flex flex-col gap-xs shadow-sm">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Total Outflow</span>
      <span class="font-body-mono text-xl text-on-surface tabular-nums font-bold">
        ${{ formatCurrency(report.total_outflow_usd) }}
      </span>
      <span class="font-body-base text-xs text-on-surface-variant">Trailing 30 Days</span>
    </div>

    <!-- Savings Rate -->
    <div class="bg-surface-container rounded-xl p-md border border-outline/10 flex flex-col gap-xs shadow-sm">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Savings Rate</span>
      <span class="font-body-mono text-xl text-tertiary-container tabular-nums font-bold">
        {{ (report.savings_rate * 100).toFixed(1) }}%
      </span>
      <span class="font-body-base text-xs text-on-surface-variant">Net Savings / Income</span>
    </div>

    <!-- Reserve Months -->
    <div class="bg-surface-container rounded-xl p-md border border-outline/10 flex flex-col gap-xs shadow-sm">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Liquidity Reserve</span>
      <span class="font-body-mono text-xl text-primary tabular-nums font-bold">
        {{ report.reserve_months.toFixed(1) }} mo
      </span>
      <span class="font-body-base text-xs text-on-surface-variant">Cash / Avg Monthly Spend</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { SpendingReport } from '../../types';

defineProps<{
  report: SpendingReport;
}>();

function formatCurrency(val: number): string {
  return val.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
}
</script>
