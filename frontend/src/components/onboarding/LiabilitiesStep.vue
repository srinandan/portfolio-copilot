<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="liabilities-step">
    <!-- Header -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">credit_card</span>
        <span>Turn 2 of 5</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Current Liabilities &amp; Debt</h1>
      <p class="font-body-base text-on-surface-variant">
        Self-report your current debt obligations to capture your full net-worth picture and risk capacity.
      </p>
    </div>

    <!-- Liabilities Container -->
    <div class="flex flex-col gap-md">
      <!-- Zero Liabilities Toggle -->
      <div class="bg-surface-container-lowest rounded-xl p-md border border-outline-variant shadow-sm flex items-center justify-between">
        <div>
          <h4 class="font-title-sm text-on-surface">No Outstanding Debt</h4>
          <p class="font-body-base text-xs text-on-surface-variant">Check if you carry zero credit cards, mortgages, or loans.</p>
        </div>
        <input
          v-model="hasNoDebt"
          type="checkbox"
          class="w-5 h-5 accent-primary-container cursor-pointer"
          data-testid="no-debt-toggle"
        />
      </div>

      <!-- Debt List -->
      <div v-if="!hasNoDebt" class="flex flex-col gap-md">
        <div
          v-for="(item, idx) in liabilities"
          :key="item.liability_id || idx"
          class="bg-surface-container-lowest rounded-xl p-md border border-outline-variant shadow-sm flex flex-col gap-md relative"
          data-testid="liability-row"
        >
          <div class="flex items-center justify-between border-b border-outline-variant/40 pb-sm">
            <span class="font-label-caps text-on-surface-variant uppercase">Liability #{{ idx + 1 }}</span>
            <button
              class="text-on-surface-variant hover:text-error transition-colors text-xs flex items-center gap-1"
              data-testid="remove-liability-btn"
              @click="removeLiability(idx)"
            >
              <span class="material-symbols-outlined text-[16px]">delete</span>
              <span>Remove</span>
            </button>
          </div>

          <!-- Description & Type -->
          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-on-surface-variant uppercase">Description</label>
              <input
                v-model="item.description"
                type="text"
                placeholder="e.g. Chase Sapphire, Mortgage"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-base text-sm"
              />
            </div>
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-on-surface-variant uppercase">Debt Category</label>
              <select
                v-model="item.type"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-base text-sm"
              >
                <option value="credit_card">Credit Card</option>
                <option value="mortgage">Mortgage</option>
                <option value="auto_loan">Auto Loan</option>
                <option value="student_loan">Student Loan</option>
                <option value="heloc">HELOC</option>
                <option value="other">Other</option>
              </select>
            </div>
          </div>

          <!-- Balance, APR, Min Payment -->
          <div class="grid grid-cols-1 md:grid-cols-3 gap-md">
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-on-surface-variant uppercase">Balance ($)</label>
              <input
                v-model.number="item.balance_usd"
                type="number"
                min="0"
                placeholder="0"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm tabular-nums"
                data-testid="input-liability-balance"
              />
            </div>
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-on-surface-variant uppercase">Interest Rate (APR %)</label>
              <input
                v-model.number="item.interest_rate_percent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                placeholder="0"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm tabular-nums"
                data-testid="input-liability-apr"
              />
            </div>
            <div class="flex flex-col gap-xs">
              <label class="font-label-caps text-on-surface-variant uppercase">Min Monthly Payment ($)</label>
              <input
                v-model.number="item.minimum_payment_usd"
                type="number"
                min="0"
                placeholder="0"
                class="w-full bg-surface-container text-on-surface p-sm rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono text-sm tabular-nums"
                data-testid="input-liability-min-payment"
              />
            </div>
          </div>

          <!-- High APR Warning -->
          <div
            v-if="item.interest_rate_percent >= 15"
            class="bg-amber-50 dark:bg-amber-950/30 text-amber-800 dark:text-amber-200 p-2.5 rounded text-xs flex items-center gap-2 border border-amber-200 dark:border-amber-800/40"
          >
            <span class="material-symbols-outlined text-[16px] text-amber-600">warning</span>
            <span>High-interest debt ({{ item.interest_rate_percent }}% APR) is tracked for debt-paydown prioritization before aggressive equity allocation.</span>
          </div>
        </div>

        <button
          type="button"
          class="w-full border border-dashed border-outline-variant hover:border-primary text-on-surface py-md rounded-xl font-title-sm text-sm flex items-center justify-center gap-2 transition-colors bg-surface-container-low"
          data-testid="add-liability-btn"
          @click="addLiability"
        >
          <span class="material-symbols-outlined text-[18px]">add</span>
          <span>Add Another Liability</span>
        </button>
      </div>

      <!-- Debt Summary Card -->
      <div v-if="!hasNoDebt && liabilities.length > 0" class="bg-surface-container p-md rounded-lg flex justify-between items-center text-sm font-body-mono">
        <span class="text-on-surface-variant">Total Reported Liabilities:</span>
        <span class="font-bold text-on-surface" data-testid="total-liabilities-display">${{ totalLiabilities.toLocaleString() }}</span>
      </div>
    </div>

    <!-- CTA -->
    <div class="mt-md">
      <button
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90"
        data-testid="confirm-liabilities-btn"
        @click="submitLiabilities"
      >
        <span>Continue to Risk Calibration</span>
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { LiabilityItem } from '../../types';

const props = withDefaults(
  defineProps<{
    initialLiabilities?: LiabilityItem[];
  }>(),
  {
    initialLiabilities: () => []
  }
);

const emit = defineEmits<{
  (e: 'next', liabilities: LiabilityItem[]): void;
}>();

const hasNoDebt = ref(false);
const liabilities = ref<LiabilityItem[]>(
  props.initialLiabilities && props.initialLiabilities.length > 0
    ? JSON.parse(JSON.stringify(props.initialLiabilities))
    : [
        {
          liability_id: 'liab_001',
          type: 'credit_card',
          description: 'Chase Sapphire Reserve',
          balance_usd: 4850,
          interest_rate_percent: 24.99,
          minimum_payment_usd: 150
        }
      ]
);

function addLiability() {
  liabilities.value.push({
    liability_id: `liab_${Date.now()}`,
    type: 'other',
    description: '',
    balance_usd: 0,
    interest_rate_percent: 0,
    minimum_payment_usd: 0
  });
}

function removeLiability(index: number) {
  liabilities.value.splice(index, 1);
  if (liabilities.value.length === 0) {
    hasNoDebt.value = true;
  }
}

const totalLiabilities = computed(() => {
  if (hasNoDebt.value) return 0;
  return liabilities.value.reduce((acc, item) => acc + (Number(item.balance_usd) || 0), 0);
});

function submitLiabilities() {
  const result = hasNoDebt.value ? [] : liabilities.value.filter(l => l.balance_usd > 0 || l.description.length > 0);
  emit('next', result);
}
</script>
