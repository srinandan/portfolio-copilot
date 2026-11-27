<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="liabilities-step">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-surface">Current Liabilities &amp; Debt</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Self-report current debt obligations to capture your full net-worth picture and risk capacity.
      </p>
    </header>

    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden flex flex-col">
      <!-- Zero Debt Toggle -->
      <label class="p-lg flex items-center justify-between gap-md cursor-pointer border-b border-outline-variant">
        <div>
          <span class="font-sans text-heading font-semibold text-on-surface block">No outstanding debt</span>
          <span class="font-sans text-meta text-on-surface-variant">
            Check if you carry zero credit cards, mortgages, or loans.
          </span>
        </div>
        <input
          v-model="hasNoDebt"
          type="checkbox"
          class="w-5 h-5 accent-primary cursor-pointer shrink-0"
          data-testid="no-debt-toggle"
        />
      </label>

      <!-- Debt Rows -->
      <div v-if="!hasNoDebt" class="divide-y divide-outline-variant">
        <div
          v-for="(item, idx) in liabilities"
          :key="item.liability_id || idx"
          class="p-lg flex flex-col gap-md"
          data-testid="liability-row"
        >
          <div class="flex items-center justify-between">
            <span class="font-sans text-meta font-semibold text-on-surface">Liability #{{ idx + 1 }}</span>
            <button
              type="button"
              class="text-on-surface-variant hover:text-error transition-colors duration-150 ease-desk font-sans text-meta inline-flex items-center gap-1"
              data-testid="remove-liability-btn"
              @click="removeLiability(idx)"
            >
              <span class="material-symbols-outlined text-[16px]" aria-hidden="true">delete</span>
              <span>Remove</span>
            </button>
          </div>

          <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Description</label>
              <input
                v-model="item.description"
                type="text"
                placeholder="e.g. Premium Rewards Card, Mortgage"
                class="w-full bg-surface text-on-surface px-3 py-2 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest"
              />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Debt category</label>
              <select
                v-model="item.type"
                class="w-full bg-surface text-on-surface px-3 py-2 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest"
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

          <div class="grid grid-cols-1 md:grid-cols-3 gap-md">
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Balance (USD)</label>
              <input
                v-model.number="item.balance_usd"
                type="number"
                min="0"
                placeholder="0"
                class="w-full bg-surface text-on-surface px-3 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-liability-balance"
              />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Interest rate (APR %)</label>
              <input
                v-model.number="item.interest_rate_percent"
                type="number"
                min="0"
                max="100"
                step="0.01"
                placeholder="0"
                class="w-full bg-surface text-on-surface px-3 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-liability-apr"
              />
            </div>
            <div class="flex flex-col gap-1.5">
              <label class="font-sans text-meta font-medium text-on-surface-variant">Min monthly payment (USD)</label>
              <input
                v-model.number="item.minimum_payment_usd"
                type="number"
                min="0"
                placeholder="0"
                class="w-full bg-surface text-on-surface px-3 py-2 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest"
                data-testid="input-liability-min-payment"
              />
            </div>
          </div>

          <div
            v-if="item.interest_rate_percent >= 15"
            class="bg-secondary-fixed/70 text-on-secondary-fixed p-3 rounded-md font-sans text-meta flex items-center gap-2 border border-secondary-fixed-dim"
          >
            <span class="material-symbols-outlined text-[18px] shrink-0" aria-hidden="true">warning</span>
            <span>
              High-interest debt ({{ item.interest_rate_percent }}% APR) is tracked for debt-paydown prioritization before aggressive equity allocation.
            </span>
          </div>
        </div>

        <div class="p-md bg-surface-container-low/40">
          <button
            type="button"
            class="w-full border border-dashed border-outline-variant hover:border-primary text-primary py-2.5 rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-150 ease-desk bg-surface-container-lowest"
            data-testid="add-liability-btn"
            @click="addLiability"
          >
            <span class="material-symbols-outlined text-[18px]" aria-hidden="true">add</span>
            <span>Add another liability</span>
          </button>
        </div>
      </div>

      <!-- Summary Footer -->
      <div
        v-if="!hasNoDebt && liabilities.length > 0"
        class="px-lg py-3.5 border-t border-outline-variant bg-surface-container-low/50 flex justify-between items-center font-sans text-body tabular-nums"
      >
        <span class="text-on-surface-variant">Total reported liabilities</span>
        <span class="font-semibold text-on-surface" data-testid="total-liabilities-display">
          ${{ totalLiabilities.toLocaleString() }}
        </span>
      </div>
    </section>

    <div>
      <button
        type="button"
        class="w-full bg-primary text-on-primary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-primary-container"
        data-testid="confirm-liabilities-btn"
        @click="submitLiabilities"
      >
        <span>Continue to Risk Calibration</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
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
          description: 'Premium Rewards Card',
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
