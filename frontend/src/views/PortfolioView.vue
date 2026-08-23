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
        <p v-if="formattedAsOf" class="font-body-mono text-xs text-on-surface-variant mt-1">
          {{ formattedAsOf }}
        </p>
      </div>

      <div class="flex items-center gap-md z-10">
        <div class="w-24 h-24 relative flex-shrink-0">
          <svg class="w-full h-full transform -rotate-90 drop-shadow-sm" viewBox="0 0 100 100">
            <circle class="text-surface-variant opacity-30" cx="50" cy="50" fill="transparent" r="40" stroke="currentColor" stroke-width="12"></circle>
            <circle
              v-for="item in allocationBreakdown"
              :key="item.assetClass"
              class="drop-shadow-sm transition-all duration-500"
              :class="item.colorClass.replace('bg-', 'text-')"
              cx="50"
              cy="50"
              fill="transparent"
              r="40"
              stroke="currentColor"
              :stroke-dasharray="item.dasharray"
              :stroke-dashoffset="item.dashoffset"
              stroke-width="12"
            ></circle>
          </svg>
        </div>
        <div class="flex flex-col gap-2 flex-1">
          <div
            v-for="item in allocationBreakdown"
            :key="item.assetClass"
            class="flex items-center justify-between"
            data-testid="allocation-row"
          >
            <div class="flex items-center gap-2">
              <div :class="['w-2 h-2 rounded-full', item.colorClass]"></div>
              <span class="font-body-base text-body-base text-on-surface">{{ item.assetClass }}</span>
            </div>
            <span class="font-body-mono text-body-mono text-on-surface">{{ item.percent.toFixed(1) }}%</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Portfolio Drift Report Card -->
    <DriftReportCard v-if="driftReport" :drift-report="driftReport" />

    <!-- Top Holdings Table -->
    <TopHoldingsTable :positions="holdings.positions" />

    <!-- Advisory equity research (issue #344) -->
    <EquityAnalyzer />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import type { HoldingsSnapshot, DriftReport } from '../types';
import { apiService } from '../services/api';
import TopHoldingsTable from '../components/portfolio/TopHoldingsTable.vue';
import DriftReportCard from '../components/portfolio/DriftReportCard.vue';
import EquityAnalyzer from '../components/portfolio/EquityAnalyzer.vue';

interface AllocationItem {
  assetClass: string;
  valueUSD: number;
  percent: number;
  colorClass: string;
  dasharray: string;
  dashoffset: string;
}

const colorPalette = [
  'bg-primary-fixed',
  'bg-tertiary-fixed-dim',
  'bg-secondary',
  'bg-primary',
  'bg-tertiary',
  'bg-surface-variant'
];

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

const formattedAsOf = computed(() => {
  if (!holdings.value.as_of) return '';
  const d = new Date(holdings.value.as_of);
  if (isNaN(d.getTime())) {
    return `As of ${holdings.value.as_of}`;
  }
  const dateStr = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
  return `Updated ${dateStr}`;
});

const allocationBreakdown = computed<AllocationItem[]>(() => {
  const map: Record<string, number> = {};

  for (const pos of holdings.value.positions || []) {
    const cls = pos.asset_class || 'Other';
    const val = pos.market_value_usd ?? pos.current_value_usd ?? (pos.quantity * (pos.current_price_usd ?? 0));
    map[cls] = (map[cls] || 0) + val;
  }

  const cash = holdings.value.cash_usd || 0;
  if (cash > 0) {
    map['Cash'] = (map['Cash'] || 0) + cash;
  }

  const total = holdings.value.total_value_usd || Object.values(map).reduce((a, b) => a + b, 0);

  if (total <= 0 || Object.keys(map).length === 0) {
    return [
      { assetClass: 'Stocks', valueUSD: 0, percent: 55, colorClass: 'bg-primary-fixed', dasharray: `${0.55 * 251.2} 251.2`, dashoffset: '0' },
      { assetClass: 'ETFs', valueUSD: 0, percent: 30, colorClass: 'bg-tertiary-fixed-dim', dasharray: `${0.30 * 251.2} 251.2`, dashoffset: `${-0.55 * 251.2}` },
      { assetClass: 'Cash', valueUSD: 0, percent: 15, colorClass: 'bg-secondary', dasharray: `${0.15 * 251.2} 251.2`, dashoffset: `${-0.85 * 251.2}` }
    ];
  }

  let accumulatedPercent = 0;
  const items: AllocationItem[] = [];
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]);

  entries.forEach(([assetClass, val], idx) => {
    const percent = (val / total) * 100;
    const colorClass = colorPalette[idx % colorPalette.length];
    const segmentLength = (percent / 100) * 251.2;
    const offset = (accumulatedPercent / 100) * 251.2;
    accumulatedPercent += percent;

    items.push({
      assetClass,
      valueUSD: val,
      percent,
      colorClass,
      dasharray: `${segmentLength} 251.2`,
      dashoffset: `${-offset}`
    });
  });

  return items;
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
