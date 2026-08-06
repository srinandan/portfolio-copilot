<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="constraints-step">
    <!-- Header -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">gavel</span>
        <span>Turn 5 of 5 • Policy Rules &amp; Guardrails</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Constraints &amp; Guardrails</h1>
      <p class="font-body-base text-on-surface-variant">
        Define concentration limits, ethical/sector exclusions, liquidity reserves, and trade sign-off thresholds.
      </p>
    </div>

    <!-- Constraints Form -->
    <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sm flex flex-col gap-md">
      <!-- Reserve Months & Concentration Limit -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Emergency Liquidity Reserve</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="reserveMonths"
              type="number"
              min="1"
              max="36"
              class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono"
              data-testid="input-reserve-months"
            />
            <span class="font-body-base text-xs text-on-surface-variant">months</span>
          </div>
          <span class="text-[11px] text-on-surface-variant">Recommended: 3–6 months of living expenses.</span>
        </div>

        <div class="flex flex-col gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Max Single-Stock Concentration</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="concentrationLimit"
              type="number"
              min="1"
              max="50"
              class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono"
              data-testid="input-concentration-limit"
            />
            <span class="font-body-base text-xs text-on-surface-variant">%</span>
          </div>
          <span class="text-[11px] text-on-surface-variant">Default limit: 15% per holding.</span>
        </div>
      </div>

      <!-- Account Type & Tax Loss Harvesting -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-md pt-sm border-t border-outline-variant/40">
        <div class="flex flex-col gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Account Type</label>
          <select
            v-model="accountType"
            class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-base text-sm"
            data-testid="select-account-type"
          >
            <option value="taxable">Individual Taxable Brokerage</option>
            <option value="ira">Traditional IRA</option>
            <option value="roth_ira">Roth IRA</option>
            <option value="401k">Solo 401(k)</option>
          </select>
        </div>

        <div class="flex flex-col justify-center gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Tax-Loss Harvesting</label>
          <label class="flex items-center gap-3 cursor-pointer mt-1">
            <input
              v-model="taxLossHarvesting"
              type="checkbox"
              class="w-5 h-5 accent-primary-container cursor-pointer"
              data-testid="toggle-tax-loss"
            />
            <span class="font-body-base text-sm text-on-surface">Enable automated TLH scans</span>
          </label>
        </div>
      </div>

      <!-- Ticker & Sector Exclusions -->
      <div class="flex flex-col gap-xs pt-sm border-t border-outline-variant/40">
        <label class="font-label-caps text-on-surface-variant uppercase">Excluded Tickers (Comma-separated)</label>
        <input
          v-model="excludedTickersStr"
          type="text"
          placeholder="e.g. TSLA, XOM, BABA"
          class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm"
          data-testid="input-excluded-tickers"
        />
      </div>

      <div class="flex flex-col gap-xs">
        <label class="font-label-caps text-on-surface-variant uppercase">Excluded Sectors (Comma-separated)</label>
        <input
          v-model="excludedSectorsStr"
          type="text"
          placeholder="e.g. tobacco, defense, fossil_fuels"
          class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm"
          data-testid="input-excluded-sectors"
        />
      </div>

      <!-- HITL Trade Approval Thresholds -->
      <div class="flex flex-col gap-xs pt-sm border-t border-outline-variant/40">
        <label class="font-title-sm text-on-surface">Human-in-the-Loop Trade Sign-off Thresholds</label>
        <p class="font-body-base text-xs text-on-surface-variant mb-2">
          Autonomous trades exceeding these limits will be suspended for explicit Human Sign-off before execution.
        </p>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-on-surface-variant uppercase">Require Approval Above ($ USD)</label>
            <div class="relative">
              <span class="absolute left-3 top-1/2 -translate-y-1/2 font-body-mono text-on-surface-variant">$</span>
              <input
                v-model.number="approvalAboveUsd"
                type="number"
                min="0"
                placeholder="1000"
                class="w-full bg-surface-container text-on-surface pl-8 p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm"
                data-testid="input-approval-usd"
              />
            </div>
          </div>

          <div class="flex flex-col gap-xs">
            <label class="font-label-caps text-on-surface-variant uppercase">Require Approval Above (% of Portfolio)</label>
            <div class="relative">
              <input
                v-model.number="approvalAbovePct"
                type="number"
                min="0.1"
                max="100"
                placeholder="5"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm"
                data-testid="input-approval-pct"
              />
              <span class="absolute right-3 top-1/2 -translate-y-1/2 font-body-mono text-on-surface-variant">%</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- CTA -->
    <div class="mt-md">
      <button
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90"
        data-testid="confirm-constraints-btn"
        @click="submitConstraints"
      >
        <span>Review &amp; Initialize IPS</span>
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import type { IPSConstraints, ApprovalThresholds } from '../../types';

const props = withDefaults(
  defineProps<{
    initialReserveMonths?: number;
    initialConstraints?: IPSConstraints;
    initialThresholds?: ApprovalThresholds;
  }>(),
  {
    initialReserveMonths: 6,
    initialConstraints: () => ({
      concentration_limit_percent: 15,
      excluded_tickers: [],
      excluded_sectors: [],
      account_type: 'taxable',
      tax_loss_harvesting_enabled: true
    }),
    initialThresholds: () => ({
      approval_required_above_usd: 1000,
      approval_required_above_percent: 5
    })
  }
);

const emit = defineEmits<{
  (e: 'next', payload: {
    reserveMonths: number;
    constraints: IPSConstraints;
    thresholds: ApprovalThresholds;
  }): void;
}>();

const reserveMonths = ref(props.initialReserveMonths);
const concentrationLimit = ref(props.initialConstraints.concentration_limit_percent || 15);
const accountType = ref(props.initialConstraints.account_type || 'taxable');
const taxLossHarvesting = ref(props.initialConstraints.tax_loss_harvesting_enabled ?? true);
const excludedTickersStr = ref((props.initialConstraints.excluded_tickers || []).join(', '));
const excludedSectorsStr = ref((props.initialConstraints.excluded_sectors || []).join(', '));

const approvalAboveUsd = ref(props.initialThresholds.approval_required_above_usd || 1000);
const approvalAbovePct = ref(props.initialThresholds.approval_required_above_percent || 5);

function submitConstraints() {
  const excluded_tickers = excludedTickersStr.value
    .split(',')
    .map(s => s.trim().toUpperCase())
    .filter(Boolean);

  const excluded_sectors = excludedSectorsStr.value
    .split(',')
    .map(s => s.trim().toLowerCase())
    .filter(Boolean);

  emit('next', {
    reserveMonths: Number(reserveMonths.value) || 6,
    constraints: {
      concentration_limit_percent: Number(concentrationLimit.value) || 15,
      excluded_tickers,
      excluded_sectors,
      account_type: accountType.value as any,
      tax_loss_harvesting_enabled: taxLossHarvesting.value
    },
    thresholds: {
      approval_required_above_usd: Number(approvalAboveUsd.value) || 1000,
      approval_required_above_percent: Number(approvalAbovePct.value) || 5
    }
  });
}
</script>
