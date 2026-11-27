<template>
  <section
    class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden flex flex-col"
    data-testid="drift-report-card"
  >
    <!-- Header -->
    <div class="px-lg py-4 border-b border-outline-variant flex items-baseline justify-between gap-md flex-wrap">
      <h3 class="font-sans text-heading font-semibold text-on-surface">Portfolio Drift Report</h3>
      <span class="font-sans text-meta text-on-surface-variant tabular-nums">
        As of {{ driftReport.as_of }}
      </span>
    </div>

    <!-- Boundary State: No Active IPS -->
    <div v-if="!driftReport.has_active_ips" class="p-lg text-center" data-testid="no-ips-message">
      <p class="font-sans text-body text-on-surface-variant">
        No investment policy set yet. Complete Onboarding to set target allocation bands.
      </p>
    </div>

    <!-- Active Drift Report -->
    <div v-else class="flex flex-col">
      <!-- Rebalance Banner -->
      <div
        v-if="driftReport.rebalance_recommended"
        class="bg-secondary-fixed/70 border-b border-secondary-fixed-dim px-lg py-3 flex items-center justify-between gap-md flex-wrap"
        data-testid="rebalance-banner"
      >
        <div class="flex items-center gap-2.5">
          <span class="material-symbols-outlined text-[18px] text-on-secondary-fixed" aria-hidden="true">balance</span>
          <span class="font-sans text-meta font-semibold text-on-secondary-fixed">
            Rebalancing Recommended: Drift exceeds IPS threshold
          </span>
        </div>
        <StatusPill status="DRIFTED" label="Action required" />
      </div>

      <!-- Drift Table with Inline Target-Band Tracks -->
      <div class="overflow-x-auto">
        <table class="w-full text-left border-collapse" data-testid="drift-table">
          <thead>
            <tr class="border-b border-outline-variant bg-surface-container-low/50 font-sans text-meta font-medium text-on-surface-variant">
              <th class="py-2.5 pl-md sm:pl-lg pr-3">Asset class</th>
              <th class="py-2.5 px-4 hidden md:table-cell w-44">Band position</th>
              <th class="py-2.5 px-2 sm:px-3 text-right">Current</th>
              <th class="py-2.5 px-3 text-right hidden sm:table-cell">Target</th>
              <th class="py-2.5 px-3 text-right hidden sm:table-cell">IPS band</th>
              <th class="py-2.5 px-2 sm:px-3 text-right">Drift</th>
              <th class="py-2.5 pl-2 pr-md sm:pr-lg text-right">Status</th>
            </tr>
          </thead>
          <tbody class="font-sans text-body divide-y divide-outline-variant/60 tabular-nums">
            <tr v-for="band in driftReport.bands" :key="band.asset_class" data-testid="drift-row">
              <td class="py-3 pl-md sm:pl-lg pr-3 font-medium text-on-surface">{{ band.asset_class }}</td>
              <td class="py-3 px-4 hidden md:table-cell">
                <div class="relative h-2.5 w-full rounded-full bg-surface-container-low overflow-hidden">
                  <!-- Target tolerance bracket -->
                  <div
                    class="absolute inset-y-0 bg-primary/15 border-x border-primary/40"
                    :style="{
                      left: `${Math.max(0, Math.min(100, band.min_percent))}%`,
                      width: `${Math.max(2, Math.min(100, band.max_percent) - Math.max(0, band.min_percent))}%`
                    }"
                  ></div>
                  <!-- Actual fill bar -->
                  <div
                    :class="[
                      'h-full rounded-full transition-[width] duration-200 ease-desk',
                      band.in_band ? 'bg-primary' : 'bg-on-secondary-fixed'
                    ]"
                    :style="{ width: `${Math.max(0, Math.min(100, band.current_percent))}%` }"
                  ></div>
                </div>
              </td>
              <td class="py-3 px-2 sm:px-3 text-right font-semibold text-on-surface">{{ band.current_percent.toFixed(1) }}%</td>
              <td class="py-3 px-3 text-right text-on-surface-variant hidden sm:table-cell">{{ band.target_percent.toFixed(1) }}%</td>
              <td class="py-3 px-3 text-right text-meta text-on-surface-variant hidden sm:table-cell">
                {{ band.min_percent.toFixed(0) }}%-{{ band.max_percent.toFixed(0) }}%
              </td>
              <td
                :class="[
                  'py-3 px-2 sm:px-3 text-right font-semibold',
                  band.in_band ? 'text-on-surface-variant' : 'text-error'
                ]"
              >
                {{ band.in_band ? '0.0' : `+${band.drift_amount_percent.toFixed(1)}` }}%
              </td>
              <td class="py-3 pl-2 pr-md sm:pr-lg text-right">
                <StatusPill
                  :status="band.in_band ? 'PASS' : 'DRIFTED'"
                  :label="band.in_band ? 'PASS' : 'DRIFTED'"
                />
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <!-- Unclassified Value Footer -->
      <div
        class="border-t border-outline-variant bg-surface-container-low/40 px-lg py-3 flex items-center justify-between font-sans text-meta text-on-surface-variant tabular-nums"
        data-testid="unclassified-value"
      >
        <span>Unclassified Holdings Value:</span>
        <span class="font-semibold text-on-surface">
          ${{ driftReport.unclassified_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
        </span>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import type { DriftReport } from '../../types';
import StatusPill from '../common/StatusPill.vue';

defineProps<{
  driftReport: DriftReport;
}>();
</script>
