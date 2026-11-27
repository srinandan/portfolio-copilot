<template>
  <section
    class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 divide-y sm:divide-y-0 sm:divide-x divide-outline-variant w-full overflow-hidden"
    data-testid="spending-summary-card"
  >
    <!-- Total Income -->
    <div class="p-lg flex flex-col gap-1">
      <span class="font-sans text-meta font-medium text-on-surface-variant">Total income</span>
      <span class="font-sans text-heading font-semibold text-on-surface tabular-nums">
        ${{ formatCurrency(report.total_income_usd) }}
      </span>
      <span class="font-sans text-meta text-on-surface-variant">Trailing 30 days</span>
    </div>

    <!-- Total Outflow -->
    <div class="p-lg flex flex-col gap-1">
      <span class="font-sans text-meta font-medium text-on-surface-variant">Total outflow</span>
      <span class="font-sans text-heading font-semibold text-on-surface tabular-nums">
        ${{ formatCurrency(report.total_outflow_usd) }}
      </span>
      <span class="font-sans text-meta text-on-surface-variant">Trailing 30 days</span>
    </div>

    <!-- Savings Rate -->
    <div class="p-lg flex flex-col gap-1 sm:border-t lg:border-t-0 border-outline-variant">
      <span class="font-sans text-meta font-medium text-on-surface-variant">Savings rate</span>
      <span class="font-sans text-heading font-semibold text-on-tertiary-container tabular-nums">
        {{ (report.savings_rate * 100).toFixed(1) }}%
      </span>
      <span class="font-sans text-meta text-on-surface-variant">Net savings / income</span>
    </div>

    <!-- Reserve Months -->
    <div class="p-lg flex flex-col gap-1 sm:border-t lg:border-t-0 border-outline-variant">
      <span class="font-sans text-meta font-medium text-on-surface-variant">Liquidity reserve</span>
      <span class="font-sans text-heading font-semibold text-primary tabular-nums">
        {{ report.reserve_months.toFixed(1) }} mo
      </span>
      <span class="font-sans text-meta text-on-surface-variant">Cash / avg monthly spend</span>
    </div>
  </section>
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
