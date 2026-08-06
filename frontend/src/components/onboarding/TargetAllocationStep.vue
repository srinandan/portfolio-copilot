<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="target-allocation-step">
    <!-- Header Section -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-secondary">
        <span class="material-symbols-outlined text-[16px]">pie_chart</span>
        <span class="font-label-caps uppercase tracking-wider">Asset Allocation Review</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Target Bands</h1>
      <p class="font-body-base text-on-surface-variant">
        Adjust your target allocation based on your projected risk profile and selected goals.
      </p>
    </div>

    <!-- Active Chart Area (Bento Layout) -->
    <div class="bg-surface-container rounded-xl p-lg flex flex-col gap-lg relative overflow-hidden shadow-sm border border-outline-variant">
      <div class="flex justify-between items-end relative z-10">
        <div>
          <span class="font-label-caps text-on-surface-variant uppercase tracking-wider block mb-1">Projected Return</span>
          <div class="flex items-baseline gap-sm">
            <span class="font-display-lg text-on-surface" data-testid="projected-return">{{ projectedReturn }}</span>
            <span class="font-body-base text-on-tertiary-container flex items-center bg-tertiary-fixed-dim/20 px-2 py-0.5 rounded-full text-xs">
              <span class="material-symbols-outlined text-[14px]">trending_up</span>
              +0.4%
            </span>
          </div>
        </div>
        <div class="text-right">
          <span class="font-label-caps text-on-surface-variant uppercase tracking-wider block mb-1">Risk Score</span>
          <span class="font-headline-md text-on-surface capitalize" data-testid="risk-score">{{ computedRiskScore }}</span>
        </div>
      </div>

      <!-- Donut Chart Visualization (Inline SVG) -->
      <div class="relative w-48 h-48 mx-auto flex items-center justify-center z-10">
        <svg aria-label="Asset Allocation Chart" class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <!-- Equities Arc -->
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="transparent"
            stroke="#131b2e"
            stroke-width="12"
            :stroke-dasharray="`${arcEquity.len} 251.2`"
            :stroke-dashoffset="arcEquity.offset"
            class="transition-all duration-500 ease-out"
          ></circle>
          <!-- Fixed Income Arc -->
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="transparent"
            stroke="#b9c7e0"
            stroke-width="12"
            :stroke-dasharray="`${arcFixed.len} 251.2`"
            :stroke-dashoffset="arcFixed.offset"
            class="transition-all duration-500 ease-out"
          ></circle>
          <!-- Cash Arc -->
          <circle
            cx="50"
            cy="50"
            r="40"
            fill="transparent"
            stroke="#565e74"
            stroke-width="12"
            :stroke-dasharray="`${arcCash.len} 251.2`"
            :stroke-dashoffset="arcCash.offset"
            class="transition-all duration-500 ease-out"
          ></circle>
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span class="font-title-sm text-on-surface" data-testid="total-percent-display">{{ totalAllocation }}%</span>
          <span class="font-label-caps text-on-surface-variant">Total</span>
        </div>
      </div>
    </div>

    <!-- Sliders Section -->
    <div class="flex flex-col gap-md">
      <!-- Equities -->
      <div class="bg-surface-container-lowest rounded-lg p-md shadow-sm border border-outline-variant flex flex-col gap-md">
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-sm">
            <div class="w-3 h-3 rounded-full bg-primary-container"></div>
            <span class="font-title-sm text-on-surface">Equities</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="equity"
              type="number"
              min="0"
              max="100"
              class="w-16 bg-surface-container text-center font-body-mono py-1 px-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-container border border-outline-variant"
              data-testid="input-equity"
            />
            <span class="font-body-base text-on-surface-variant">%</span>
          </div>
        </div>
        <div class="relative w-full h-8 flex items-center">
          <input
            v-model.number="equity"
            type="range"
            min="0"
            max="100"
            class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary-container"
            data-testid="slider-equity"
          />
        </div>
      </div>

      <!-- Fixed Income -->
      <div class="bg-surface-container-lowest rounded-lg p-md shadow-sm border border-outline-variant flex flex-col gap-md">
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-sm">
            <div class="w-3 h-3 rounded-full bg-secondary-fixed-dim"></div>
            <span class="font-title-sm text-on-surface">Fixed Income</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="fixedIncome"
              type="number"
              min="0"
              max="100"
              class="w-16 bg-surface-container text-center font-body-mono py-1 px-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-container border border-outline-variant"
              data-testid="input-fixed"
            />
            <span class="font-body-base text-on-surface-variant">%</span>
          </div>
        </div>
        <div class="relative w-full h-8 flex items-center">
          <input
            v-model.number="fixedIncome"
            type="range"
            min="0"
            max="100"
            class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-secondary"
            data-testid="slider-fixed"
          />
        </div>
      </div>

      <!-- Cash & Equivalents -->
      <div class="bg-surface-container-lowest rounded-lg p-md shadow-sm border border-outline-variant flex flex-col gap-md">
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-sm">
            <div class="w-3 h-3 rounded-full bg-surface-tint"></div>
            <span class="font-title-sm text-on-surface">Cash &amp; Equiv.</span>
          </div>
          <div class="flex items-center gap-2">
            <input
              v-model.number="cash"
              type="number"
              min="0"
              max="100"
              class="w-16 bg-surface-container text-center font-body-mono py-1 px-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-container border border-outline-variant"
              data-testid="input-cash"
            />
            <span class="font-body-base text-on-surface-variant">%</span>
          </div>
        </div>
        <div class="relative w-full h-8 flex items-center">
          <input
            v-model.number="cash"
            type="range"
            min="0"
            max="100"
            class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-surface-tint"
            data-testid="slider-cash"
          />
        </div>
      </div>

      <!-- Warning Toast if total != 100 -->
      <div
        v-if="totalAllocation !== 100"
        class="bg-error-container text-on-error-container p-4 rounded-lg flex items-center gap-sm transition-opacity"
        data-testid="allocation-warning"
      >
        <span class="material-symbols-outlined text-error">warning</span>
        <span class="font-body-base text-body-base">
          Total allocation must equal 100%. Currently: <span class="font-body-mono font-bold">{{ totalAllocation }}</span>%
        </span>
      </div>
    </div>

    <!-- Confirm Button -->
    <div class="mt-md">
      <button
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="totalAllocation !== 100"
        data-testid="confirm-allocation-btn"
        @click="confirmAllocation"
      >
        <span>Confirm Allocation</span>
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { TargetAllocationInput } from '../../types';

const props = withDefaults(
  defineProps<{
    initialAllocation?: TargetAllocationInput;
  }>(),
  {
    initialAllocation: () => ({ equity: 60, fixed_income: 30, cash: 10 })
  }
);

const emit = defineEmits<{
  (e: 'confirm', allocation: TargetAllocationInput): void;
}>();

const equity = ref<number>(props.initialAllocation.equity);
const fixedIncome = ref<number>(props.initialAllocation.fixed_income);
const cash = ref<number>(props.initialAllocation.cash);

const totalAllocation = computed(() => (Number(equity.value) || 0) + (Number(fixedIncome.value) || 0) + (Number(cash.value) || 0));

const CIRCUMFERENCE = 251.2; // 2 * pi * 40

const arcEquity = computed(() => {
  const pct = Math.max(0, equity.value) / 100;
  return {
    len: pct * CIRCUMFERENCE,
    offset: '0'
  };
});

const arcFixed = computed(() => {
  const pct = Math.max(0, fixedIncome.value) / 100;
  return {
    len: pct * CIRCUMFERENCE,
    offset: `-${arcEquity.value.len}`
  };
});

const arcCash = computed(() => {
  const pct = Math.max(0, cash.value) / 100;
  return {
    len: pct * CIRCUMFERENCE,
    offset: `-${arcEquity.value.len + arcFixed.value.len}`
  };
});

const projectedReturn = computed(() => {
  const ret = (equity.value * 0.08) + (fixedIncome.value * 0.04) + (cash.value * 0.01);
  return ret.toFixed(1) + '%';
});

const computedRiskScore = computed(() => {
  if (equity.value >= 70) return 'Aggressive';
  if (equity.value >= 40) return 'Moderate';
  return 'Conservative';
});

function confirmAllocation() {
  if (totalAllocation.value === 100) {
    emit('confirm', {
      equity: equity.value,
      fixed_income: fixedIncome.value,
      cash: cash.value
    });
  }
}
</script>
