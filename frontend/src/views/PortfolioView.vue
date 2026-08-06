<template>
  <div class="flex flex-col gap-lg w-full">
    <div class="flex flex-col gap-sm">
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Portfolio</h1>
      <p class="font-body-base text-body-base text-on-surface-variant max-w-sm">
        Breakdown of your holdings based on uploaded documents.
      </p>
    </div>

    <!-- Total Value & Allocation Chart Card -->
    <div class="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant flex flex-col p-lg gap-lg relative overflow-hidden">
      <div class="absolute top-0 right-0 p-md opacity-20 pointer-events-none">
        <img alt="Portfolio Chart Icon" class="w-24 h-24 object-contain" src="/images/chart_icon.png" />
      </div>
      <div class="flex flex-col gap-xs z-10">
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Total Value</span>
        <h2 class="font-display-lg text-display-lg text-on-background tabular-nums">${{ totalValueFormatted }}</h2>
        <div class="flex items-center gap-sm mt-1">
          <span class="inline-flex items-center gap-xs px-2 py-1 rounded-md bg-tertiary-fixed/20 text-on-tertiary-fixed font-body-mono text-[11px] font-bold">
            <span class="material-symbols-outlined text-[14px]">trending_up</span>
            +2.4%
          </span>
          <span class="font-body-base text-body-base text-on-surface-variant text-sm">Today</span>
        </div>
      </div>

      <div class="flex items-center gap-md z-10">
        <div class="w-24 h-24 relative flex-shrink-0">
          <svg class="w-full h-full transform -rotate-90 drop-shadow-sm" viewBox="0 0 100 100">
            <circle class="text-surface-variant opacity-30" cx="50" cy="50" fill="transparent" r="40" stroke="currentColor" stroke-width="12"></circle>
            <circle class="text-primary-fixed drop-shadow-sm" cx="50" cy="50" fill="transparent" r="40" stroke="currentColor" stroke-dasharray="251.2" stroke-dashoffset="62.8" stroke-width="12"></circle>
            <circle class="text-tertiary-fixed-dim drop-shadow-sm" cx="50" cy="50" fill="transparent" r="40" stroke="currentColor" stroke-dasharray="251.2" stroke-dashoffset="200.9" stroke-width="12"></circle>
            <circle class="text-secondary drop-shadow-sm" cx="50" cy="50" fill="transparent" r="40" stroke="currentColor" stroke-dasharray="251.2" stroke-dashoffset="238.6" stroke-width="12"></circle>
          </svg>
        </div>
        <div class="flex flex-col gap-2 flex-1">
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-primary-fixed"></div>
              <span class="font-body-base text-body-base text-on-surface">Stocks</span>
            </div>
            <span class="font-body-mono text-body-mono text-on-surface">55%</span>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-tertiary-fixed-dim"></div>
              <span class="font-body-base text-body-base text-on-surface">ETFs</span>
            </div>
            <span class="font-body-mono text-body-mono text-on-surface">30%</span>
          </div>
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2">
              <div class="w-2 h-2 rounded-full bg-secondary"></div>
              <span class="font-body-base text-body-base text-on-surface">Cash</span>
            </div>
            <span class="font-body-mono text-body-mono text-on-surface">15%</span>
          </div>
        </div>
      </div>

      <div class="mt-4 flex items-start gap-sm bg-surface-container-low p-3 rounded-lg border border-surface-variant z-10">
        <span class="material-symbols-outlined text-on-surface-variant text-[20px]">info</span>
        <p class="font-body-base text-body-base text-on-surface-variant text-sm">
          Data derived entirely from manual document uploads. Last verified on <span class="font-body-mono text-body-mono">2023-10-24</span>.
        </p>
      </div>
    </div>

    <!-- Portfolio Drift Report Card -->
    <DriftReportCard v-if="driftReport" :drift-report="driftReport" />

    <!-- Top Holdings Table -->
    <TopHoldingsTable :positions="holdings.positions" />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import type { HoldingsSnapshot, DriftReport } from '../types';
import { apiService } from '../services/api';
import TopHoldingsTable from '../components/portfolio/TopHoldingsTable.vue';
import DriftReportCard from '../components/portfolio/DriftReportCard.vue';

const holdings = ref<HoldingsSnapshot>({
  total_value_usd: 1248500,
  cash_usd: 62400,
  as_of: '2023-10-24',
  positions: []
});

const driftReport = ref<DriftReport>({
  as_of: '2023-10-24',
  has_active_ips: true,
  rebalance_recommended: false,
  unclassified_value_usd: 0,
  bands: []
});

const totalValueFormatted = computed(() => {
  return holdings.value.total_value_usd.toLocaleString('en-US', {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2
  });
});

onMounted(async () => {
  try {
    const [holdingsData, driftData] = await Promise.all([
      apiService.getHoldings(),
      apiService.getDriftReport()
    ]);
    holdings.value = holdingsData;
    driftReport.value = driftData;
  } catch {
    // Default values
  }
});
</script>
