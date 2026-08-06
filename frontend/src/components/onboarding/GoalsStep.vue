<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="goals-step">
    <!-- Header -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-on-surface-variant font-label-caps uppercase tracking-wider">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim">flag</span>
        <span>Turn 1 of 5</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Financial Goals &amp; Horizon</h1>
      <p class="font-body-base text-on-surface-variant">
        Define your primary objectives, target timelines, and liquidity buffer requirements.
      </p>
    </div>

    <!-- Goals Card -->
    <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sm flex flex-col gap-md">
      <div class="flex items-center justify-between border-b border-outline-variant pb-sm">
        <h3 class="font-title-sm text-on-surface">Primary Goal</h3>
        <span class="font-label-caps text-on-surface-variant uppercase">Required for IPS</span>
      </div>

      <!-- Goal Name -->
      <div class="flex flex-col gap-xs">
        <label class="font-label-caps text-on-surface-variant uppercase">Goal Name / Description</label>
        <input
          v-model="goalName"
          type="text"
          placeholder="e.g. Retirement Compounding & Financial Independence"
          class="w-full bg-surface-container text-on-surface p-md rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-base"
          data-testid="input-goal-name"
        />
      </div>

      <!-- Target Amount & Date Grid -->
      <div class="grid grid-cols-1 md:grid-cols-2 gap-md">
        <div class="flex flex-col gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Target Amount ($ USD)</label>
          <div class="relative">
            <span class="absolute left-3 top-1/2 -translate-y-1/2 font-body-mono text-on-surface-variant">$</span>
            <input
              v-model.number="targetAmount"
              type="number"
              min="0"
              placeholder="1000000"
              class="w-full bg-surface-container text-on-surface pl-8 p-md rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono tabular-nums"
              data-testid="input-target-amount"
            />
          </div>
        </div>

        <div class="flex flex-col gap-xs">
          <label class="font-label-caps text-on-surface-variant uppercase">Target Date</label>
          <input
            v-model="targetDate"
            type="date"
            class="w-full bg-surface-container text-on-surface p-md rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono"
            data-testid="input-target-date"
            @change="updateHorizonFromDate"
          />
        </div>
      </div>

      <!-- Time Horizon in Years -->
      <div class="flex flex-col gap-xs mt-sm">
        <div class="flex justify-between items-center">
          <label class="font-label-caps text-on-surface-variant uppercase">Time Horizon (Years)</label>
          <span class="font-body-mono text-on-surface font-bold" data-testid="time-horizon-val">{{ timeHorizonYears }} years</span>
        </div>
        <input
          v-model.number="timeHorizonYears"
          type="range"
          min="1"
          max="40"
          class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary-container"
          data-testid="slider-time-horizon"
        />
      </div>

      <!-- Near-Term Liquidity / Upcoming Expenses -->
      <div class="flex flex-col gap-xs mt-sm pt-md border-t border-outline-variant/50">
        <label class="font-label-caps text-on-surface-variant uppercase">Known Near-Term Expenses ($ USD)</label>
        <div class="relative">
          <span class="absolute left-3 top-1/2 -translate-y-1/2 font-body-mono text-on-surface-variant">$</span>
          <input
            v-model.number="upcomingExpenses"
            type="number"
            min="0"
            placeholder="0"
            class="w-full bg-surface-container text-on-surface pl-8 p-md rounded-lg border border-outline-variant focus:outline-none focus:ring-2 focus:ring-primary-container font-body-mono tabular-nums"
            data-testid="input-upcoming-expenses"
          />
        </div>
        <p class="font-body-base text-xs text-on-surface-variant mt-1">
          Sum of major anticipated capital outlays within the next 12 months (e.g. tuition, home renovation).
        </p>
      </div>
    </div>

    <!-- CTA -->
    <div class="mt-md">
      <button
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!isValid"
        data-testid="confirm-goals-btn"
        @click="submitGoals"
      >
        <span>Continue to Liabilities &amp; Debt</span>
        <span class="material-symbols-outlined">arrow_forward</span>
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
