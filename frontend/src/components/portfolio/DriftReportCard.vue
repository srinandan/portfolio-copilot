<template>
  <div class="bg-surface-container-lowest rounded-xl p-lg shadow-sm border border-surface-variant flex flex-col gap-md" data-testid="drift-report-card">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-surface-variant pb-2">
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-primary-container">query_stats</span>
        <h3 class="font-title-sm text-title-sm text-on-surface">Portfolio Drift Report</h3>
      </div>
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">
        As of: {{ driftReport.as_of }}
      </span>
    </div>

    <!-- Boundary State: No Active IPS -->
    <div v-if="!driftReport.has_active_ips" class="p-lg text-center bg-surface-container-low rounded-lg" data-testid="no-ips-message">
      <p class="font-body-base text-sm text-on-surface-variant">
        No investment policy set yet. Complete Onboarding to set target allocation bands.
      </p>
    </div>

    <!-- Active Drift Report Grid -->
    <div v-else class="flex flex-col gap-md">
      <!-- Rebalance CTA Banner -->
      <div
        v-if="driftReport.rebalance_recommended"
        class="bg-secondary-fixed/20 border border-secondary/40 p-sm rounded-lg flex items-center justify-between"
        data-testid="rebalance-banner"
      >
        <div class="flex items-center gap-sm">
          <span class="material-symbols-outlined text-on-secondary-fixed">balance</span>
          <span class="font-body-mono text-xs font-semibold text-on-secondary-fixed">
            Rebalancing Recommended: Drift exceeds IPS threshold
          </span>
        </div>
        <StatusPill status="DRIFTED" label="ACTION REQUIRED" />
      </div>

      <!-- Drift Grid Table -->
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse" data-testid="drift-table">
          <thead>
            <tr class="border-b border-outline/20 font-label-caps text-label-caps text-on-surface-variant uppercase">
              <th class="py-2 pr-4">Asset Class</th>
              <th class="py-2 px-2 text-right">Current %</th>
              <th class="py-2 px-2 text-right">Target %</th>
              <th class="py-2 px-2 text-right">IPS Band</th>
              <th class="py-2 px-2 text-right">Drift %</th>
              <th class="py-2 pl-4 text-right">Status</th>
            </tr>
          </thead>
          <tbody class="font-body-mono text-sm divide-y divide-outline/10 tabular-nums">
            <tr v-for="band in driftReport.bands" :key="band.asset_class" data-testid="drift-row">
              <td class="py-2.5 pr-4 font-body-base font-medium text-on-surface">{{ band.asset_class }}</td>
              <td class="py-2.5 px-2 text-right text-on-surface font-semibold">{{ band.current_percent.toFixed(1) }}%</td>
              <td class="py-2.5 px-2 text-right text-on-surface-variant">{{ band.target_percent.toFixed(1) }}%</td>
              <td class="py-2.5 px-2 text-right text-on-surface-variant">
                [{{ band.min_percent.toFixed(0) }}% - {{ band.max_percent.toFixed(0) }}%]
              </td>
              <td
                :class="[
                  'py-2.5 px-2 text-right font-bold',
                  band.in_band ? 'text-on-surface-variant' : 'text-error'
                ]"
              >
                {{ band.in_band ? '0.0' : `+${band.drift_amount_percent.toFixed(1)}` }}%
              </td>
              <td class="py-2.5 pl-4 text-right">
                <StatusPill
                  :status="band.in_band ? 'PASS' : 'DRIFTED'"
                  :label="band.in_band ? 'PASS' : 'DRIFTED'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Unclassified Value Display -->
      <div
        class="border-t border-surface-variant pt-2 flex items-center justify-between text-xs text-on-surface-variant font-body-mono"
        data-testid="unclassified-value"
      >
        <span>Unclassified Holdings Value:</span>
        <span class="font-bold text-on-surface">
          ${{ driftReport.unclassified_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { DriftReport } from '../../types';
import StatusPill from '../common/StatusPill.vue';

defineProps<{
  driftReport: DriftReport;
}>();
</script>
