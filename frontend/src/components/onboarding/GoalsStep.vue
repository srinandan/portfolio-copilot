<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="goals-step">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-surface">Financial Goals &amp; Horizon</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Define your primary objective, target timeline, and near-term liquidity requirements.
      </p>
    </header>

    <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-md">
      <div class="flex items-baseline justify-between border-b border-outline-variant pb-3">
        <h2 class="font-sans text-heading font-semibold text-on-surface">Primary goal</h2>
        <span class="font-sans text-meta text-on-surface-variant">Required for IPS</span>
      </div>

      <div class="flex flex-col gap-1.5">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Goal name or description</label>
        <input
          v-model="goalName"
          type="text"
          placeholder="e.g. Retirement Compounding & Financial Independence"
          class="w-full bg-surface text-on-surface px-3.5 py-2.5 rounded-md border border-outline-variant font-sans text-body focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
          data-testid="input-goal-name"
        />
      </div>

      <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-1.5">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Target amount (USD)</label>
          <div class="relative">
            <span class="absolute left-3.5 top-1/2 -translate-y-1/2 font-sans text-body text-on-surface-variant">$</span>
            <input
              v-model.number="targetAmount"
              type="number"
              min="0"
              placeholder="1000000"
              class="w-full bg-surface text-on-surface pl-8 pr-3.5 py-2.5 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
              data-testid="input-target-amount"
            />
          </div>
        </div>

        <div class="flex flex-col gap-1.5">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Target date</label>
          <input
            v-model="targetDate"
            type="date"
            class="w-full bg-surface text-on-surface px-3.5 py-2.5 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
            data-testid="input-target-date"
            @change="updateHorizonFromDate"
          />
        </div>
      </div>

      <div class="flex flex-col gap-2 pt-2">
        <div class="flex justify-between items-baseline">
          <label class="font-sans text-meta font-medium text-on-surface-variant">Time horizon</label>
          <span class="font-sans text-body font-semibold text-on-surface tabular-nums" data-testid="time-horizon-val">
            {{ timeHorizonYears }} years
          </span>
        </div>
        <input
          v-model.number="timeHorizonYears"
          type="range"
          min="1"
          max="40"
          class="w-full h-2 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
          data-testid="slider-time-horizon"
        />
      </div>

      <div class="flex flex-col gap-1.5 pt-md border-t border-outline-variant">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Known near-term expenses (USD)</label>
        <div class="relative">
          <span class="absolute left-3.5 top-1/2 -translate-y-1/2 font-sans text-body text-on-surface-variant">$</span>
          <input
            v-model.number="upcomingExpenses"
            type="number"
            min="0"
            placeholder="0"
            class="w-full bg-surface text-on-surface pl-8 pr-3.5 py-2.5 rounded-md border border-outline-variant font-sans text-body tabular-nums focus:bg-surface-container-lowest transition-colors duration-150 ease-desk"
            data-testid="input-upcoming-expenses"
          />
        </div>
        <p class="font-sans text-meta text-on-surface-variant">
          Major anticipated capital outlays within the next 12 months (tuition, home renovation).
        </p>
      </div>
    </section>

    <div>
      <button
        type="button"
        class="w-full bg-primary text-on-primary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-primary-container disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!isValid"
        data-testid="confirm-goals-btn"
        @click="submitGoals"
      >
        <span>Continue to Liabilities &amp; Debt</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { Goal } from '../../types';

const props = withDefaults(
  defineProps<{
    initialGoals?: Goal[];
    initialHorizonYears?: number;
    initialUpcomingExpenses?: number;
  }>(),
  {
    initialGoals: () => [
      {
        name: 'Retirement Compounding & Growth',
        target_amount_usd: 1500000,
        target_date: '2039-12-31'
      }
    ],
    initialHorizonYears: 15,
    initialUpcomingExpenses: 0
  }
);

const emit = defineEmits<{
  (e: 'next', payload: {
    goals: Goal[];
    timeHorizonYears: number;
    knownUpcomingExpensesUsd: number;
  }): void;
}>();

const goalName = ref(props.initialGoals[0]?.name || 'Retirement Compounding & Growth');
const targetAmount = ref(props.initialGoals[0]?.target_amount_usd || 1500000);
const targetDate = ref(props.initialGoals[0]?.target_date || '2039-12-31');
const timeHorizonYears = ref(props.initialHorizonYears);
const upcomingExpenses = ref(props.initialUpcomingExpenses);

function updateHorizonFromDate() {
  if (targetDate.value) {
    const targetYear = new Date(targetDate.value).getFullYear();
    const currentYear = new Date().getFullYear();
    const diff = Math.max(1, targetYear - currentYear);
    timeHorizonYears.value = Math.min(40, diff);
  }
}

const isValid = computed(() => {
  return goalName.value.trim().length > 0 && targetAmount.value > 0 && timeHorizonYears.value > 0;
});

function submitGoals() {
  if (!isValid.value) return;

  const goal: Goal = {
    name: goalName.value.trim(),
    target_amount_usd: Number(targetAmount.value),
    target_date: targetDate.value || '2039-12-31'
  };

  emit('next', {
    goals: [goal],
    timeHorizonYears: Number(timeHorizonYears.value),
    knownUpcomingExpensesUsd: Number(upcomingExpenses.value) || 0
  });
}
</script>
