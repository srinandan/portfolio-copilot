<template>
  <div class="flex flex-col gap-lg w-full">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-background">Portfolio</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Breakdown of your holdings based on uploaded documents.
      </p>
    </header>

    <!-- Total Value & Allocation Sheet -->
    <section class="w-full bg-surface-container-lowest rounded-xl shadow-sheet border border-outline-variant grid grid-cols-1 md:grid-cols-12 divide-y md:divide-y-0 md:divide-x divide-outline-variant overflow-hidden">
      <div class="md:col-span-5 p-lg flex flex-col justify-between gap-md">
        <div class="flex flex-col gap-1">
          <span class="font-sans text-meta font-medium text-on-surface-variant">Total Value</span>
          <h2 class="font-display text-display-figure font-medium text-on-surface tabular-nums">
            ${{ totalValueFormatted }}
          </h2>
        </div>
        <p v-if="formattedAsOf" class="font-sans text-meta text-on-surface-variant tabular-nums">
          {{ formattedAsOf }}
        </p>
      </div>

      <div class="md:col-span-7 p-lg flex flex-col sm:flex-row items-center gap-lg">
        <div class="w-32 h-32 relative shrink-0">
          <svg class="w-full h-full transform -rotate-90" viewBox="0 0 100 100" aria-label="Asset allocation breakdown">
            <circle
              class="text-surface-container-low"
              cx="50"
              cy="50"
              fill="transparent"
              r="40"
              stroke="currentColor"
              stroke-width="11"
            ></circle>
            <circle
              v-for="item in allocationBreakdown"
              :key="item.assetClass"
              class="transition-[stroke-dasharray,stroke-dashoffset] duration-300 ease-desk"
              cx="50"
              cy="50"
              fill="transparent"
              r="40"
              :stroke="item.strokeHex"
              :stroke-dasharray="item.dasharray"
              :stroke-dashoffset="item.dashoffset"
              stroke-width="11"
            ></circle>
          </svg>
        </div>

        <div class="flex flex-col divide-y divide-outline-variant/60 flex-1 w-full">
          <div
            v-for="item in allocationBreakdown"
            :key="item.assetClass"
            class="py-2 first:pt-0 last:pb-0 flex items-center justify-between gap-md"
            data-testid="allocation-row"
          >
            <div class="flex items-center gap-2.5 min-w-0">
              <span :class="['w-2.5 h-2.5 rounded-sm shrink-0', item.colorClass]" aria-hidden="true"></span>
              <span class="font-sans text-body text-on-surface truncate">{{ item.assetClass }}</span>
            </div>
            <span class="font-sans text-body font-medium text-on-surface tabular-nums">
              {{ item.percent.toFixed(1) }}%
            </span>
          </div>
        </div>
      </div>
    </section>

    <!-- Portfolio Drift Report -->
    <DriftReportCard v-if="driftReport" :drift-report="driftReport" />

    <!-- Top Holdings Ledger -->
    <TopHoldingsTable :positions="holdings.positions" />

    <!-- Advisory Equity Research -->
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
  strokeHex: string;
  dasharray: string;
  dashoffset: string;
}

const colorPalette = [
  { bg: 'bg-primary', hex: '#0f2342' },
  { bg: 'bg-primary-fixed', hex: '#1e40af' },
  { bg: 'bg-on-tertiary-container', hex: '#047857' },
  { bg: 'bg-secondary', hex: '#334e68' },
  { bg: 'bg-outline', hex: '#64748b' },
  { bg: 'bg-surface-dim', hex: '#94a3b8' }
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

  if (total <= 0 || Object.keys(map).length === 0 || (holdings.value.positions?.length ?? 0) === 0) {
    return [
      { assetClass: 'Stocks', valueUSD: 0, percent: 55, colorClass: colorPalette[0].bg, strokeHex: colorPalette[0].hex, dasharray: `${0.55 * 251.2} 251.2`, dashoffset: '0' },
      { assetClass: 'ETFs', valueUSD: 0, percent: 30, colorClass: colorPalette[1].bg, strokeHex: colorPalette[1].hex, dasharray: `${0.30 * 251.2} 251.2`, dashoffset: `${-0.55 * 251.2}` },
      { assetClass: 'Cash', valueUSD: 0, percent: 15, colorClass: colorPalette[2].bg, strokeHex: colorPalette[2].hex, dasharray: `${0.15 * 251.2} 251.2`, dashoffset: `${-0.85 * 251.2}` }
    ];
  }

  let accumulatedPercent = 0;
  const items: AllocationItem[] = [];
  const entries = Object.entries(map).sort((a, b) => b[1] - a[1]);

  entries.forEach(([assetClass, val], idx) => {
    const percent = (val / total) * 100;
    const swatch = colorPalette[idx % colorPalette.length];
    const segmentLength = (percent / 100) * 251.2;
    const offset = (accumulatedPercent / 100) * 251.2;
    accumulatedPercent += percent;

    items.push({
      assetClass,
      valueUSD: val,
      percent,
      colorClass: swatch.bg,
      strokeHex: swatch.hex,
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
