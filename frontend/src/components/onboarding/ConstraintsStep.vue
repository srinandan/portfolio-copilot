<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="constraints-step">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-surface">Constraints &amp; Guardrails</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Define concentration limits, sector exclusions, liquidity reserves, and trade approval thresholds.
      </p>
    </header>

    <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
      <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-1.5">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Emergency liquidity reserve</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="reserveMonths"
              type="number"
              min="1"
              max="36"
              class="w-full bg-surface text-on-surface px-3.5 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
              data-testid="input-reserve-months"
            />
            <span class="font-sans text-meta text-on-surface-variant shrink-0">months</span>
          </div>
          <span class="font-sans text-meta text-on-surface-variant">Recommended: 3 to 6 months of living expenses.</span>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Max single-stock concentration</label>
          <div class="flex items-center gap-2">
            <input
              v-model.number="concentrationLimit"
              type="number"
              min="1"
              max="50"
              class="w-full bg-surface text-on-surface px-3.5 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
              data-testid="input-concentration-limit"
            />
            <span class="font-sans text-meta text-on-surface-variant shrink-0">%</span>
          </div>
          <span class="font-sans text-meta text-on-surface-variant">Default limit: 15% per holding.</span>
        </div>
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-md pt-md border-t border-outline-variant">
        <div class="flex flex-col gap-1.5">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Account type</label>
          <select
            v-model="accountType"
            class="w-full bg-surface text-on-surface px-3.5 py-2 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest"
            data-testid="select-account-type"
          >
            <option value="taxable">Individual Taxable Brokerage</option>
            <option value="retirement">Retirement (IRA / Roth / 401k)</option>
          </select>
        </div>

        <div class="flex flex-col justify-center gap-1.5">
          <span class="font-sans text-meta font-medium text-on-surface-variant">Tax-loss harvesting</span>
          <label class="flex items-center gap-2.5 cursor-pointer py-1.5">
            <input
              v-model="taxLossHarvesting"
              type="checkbox"
              class="w-5 h-5 accent-primary cursor-pointer"
              data-testid="toggle-tax-loss"
            />
            <span class="font-sans text-body text-on-surface">Enable automated TLH scans</span>
          </label>
        </div>
      </div>

      <div class="flex flex-col gap-1.5 pt-md border-t border-outline-variant">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Excluded tickers (comma-separated)</label>
        <input
          v-model="excludedTickersStr"
          type="text"
          placeholder="e.g. TSLA, XOM, BABA"
          class="w-full bg-surface text-on-surface px-3.5 py-2 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest"
          data-testid="input-excluded-tickers"
        />
      </div>

      <div class="flex flex-col gap-1.5">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Excluded sectors (comma-separated)</label>
        <input
          v-model="excludedSectorsStr"
          type="text"
          placeholder="e.g. tobacco, defense, fossil_fuels"
          class="w-full bg-surface text-on-surface px-3.5 py-2 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest"
          data-testid="input-excluded-sectors"
        />
      </div>

      <div class="flex flex-col gap-3 pt-md border-t border-outline-variant">
        <div>
          <h2 class="font-sans text-heading font-semibold text-on-surface">Human-in-the-Loop Trade Sign-off Thresholds</h2>
          <p class="font-sans text-meta text-on-surface-variant">
            Autonomous trades exceeding these limits pause for your explicit sign-off before execution.
          </p>
        </div>

        <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
          <div class="flex flex-col gap-1.5">
            <label class="font-sans text-meta font-medium text-on-surface-variant">Require approval above (USD)</label>
            <div class="relative">
              <span class="absolute left-3.5 top-1/2 -translate-y-1/2 font-sans text-body text-on-surface-variant">$</span>
              <input
                v-model.number="approvalAboveUsd"
                type="number"
                min="0"
                placeholder="1000"
                class="w-full bg-surface text-on-surface pl-8 pr-3.5 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-approval-usd"
              />
            </div>
          </div>

          <div class="flex flex-col gap-1.5">
            <label class="font-sans text-meta font-medium text-on-surface-variant">Require approval above (% of portfolio)</label>
            <div class="relative">
              <input
                v-model.number="approvalAbovePct"
                type="number"
                min="0.1"
                max="100"
                placeholder="5"
                class="w-full bg-surface text-on-surface pl-3.5 pr-8 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-approval-pct"
              />
              <span class="absolute right-3.5 top-1/2 -translate-y-1/2 font-sans text-body text-on-surface-variant">%</span>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div>
      <button
        type="button"
        class="w-full bg-primary text-on-primary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-primary-container"
        data-testid="confirm-constraints-btn"
        @click="submitConstraints"
      >
        <span>Review &amp; Initialize IPS</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
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
      account_type: accountType.value,
      tax_loss_harvesting_enabled: taxLossHarvesting.value
    },
    thresholds: {
      approval_required_above_usd: Number(approvalAboveUsd.value) || 1000,
      approval_required_above_percent: Number(approvalAbovePct.value) || 5
    }
  });
}
</script>
