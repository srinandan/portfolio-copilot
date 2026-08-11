<template>
  <div class="flex flex-col gap-lg w-full">
    <!-- Title and Subtitle -->
    <div class="flex flex-col gap-sm">
      <h1 class="font-headline-lg-mobile text-headline-lg-mobile text-on-background">Spending Analysis</h1>
      <p class="font-body-base text-body-base text-on-surface-variant max-w-lg">
        Analysis of transaction data, monthly spending breakdown, savings rate metrics, and liquidity reserves.
      </p>
    </div>

    <!-- Spending Summary Metrics -->
    <SpendingSummaryCard v-if="report" :report="report" />

    <!-- Anomaly Alert Card -->
    <AnomalyAlertCard
      v-if="report && report.anomalies.length > 0"
      :anomalies="report.anomalies"
      :narrative-summary="report.narrative_summary"
    />

    <!-- Category Breakdown Table -->
    <CategoryBreakdownTable
      v-if="report && report.category_breakdown"
      :categories="report.category_breakdown"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { SpendingReport } from '../types';
import { apiService } from '../services/api';
import SpendingSummaryCard from '../components/spending/SpendingSummaryCard.vue';
import CategoryBreakdownTable from '../components/spending/CategoryBreakdownTable.vue';
import AnomalyAlertCard from '../components/spending/AnomalyAlertCard.vue';

const report = ref<SpendingReport>({
  user_id: 'demo_user',
  total_income_usd: 18500.0,
  total_outflow_usd: 13227.5,
  savings_rate: 0.285,
  reserve_months: 8.2,
  category_breakdown: [],
  anomalies: [],
  narrative_summary: ''
});

onMounted(async () => {
  try {
    const data = await apiService.getSpendingReport();
    report.value = data;
  } catch {
    // Default fallback
  }
});
</script>
