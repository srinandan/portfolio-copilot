<template>
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-lg w-full max-w-6xl mx-auto items-start" data-testid="risk-calibration-step">
    <!-- Left Column: Calibration Prompt & Choices -->
    <div class="lg:col-span-6 flex flex-col gap-md">
      <header class="flex flex-col gap-1">
        <h1 class="font-display text-page-title font-medium text-on-surface">Risk Calibration</h1>
        <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
          Your risk profile is derived deterministically from your investment horizon and your drawdown reaction.
        </p>
      </header>

      <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant border-l-4 border-l-primary shadow-sheet flex flex-col gap-2">
        <span class="font-sans text-meta font-semibold text-primary">Drawdown scenario</span>
        <p class="font-sans text-body text-on-surface font-medium max-w-[65ch]">
          Suppose market volatility triggers a sudden 20% drawdown across global indices next week. How would you react?
        </p>
      </div>

      <!-- Radio Selection Group -->
      <div class="flex flex-col gap-2.5" role="radiogroup" aria-label="Drawdown reaction">
        <button
          v-for="opt in reactionOptions"
          :key="opt.id"
          type="button"
          role="radio"
          :aria-checked="selectedReaction === opt.id"
          class="w-full text-left bg-surface-container-lowest rounded-xl p-md border transition-[border-color,background-color] duration-150 ease-desk shadow-sheet"
          :class="[
            selectedReaction === opt.id
              ? 'border-primary bg-surface-container-low/60'
              : 'border-outline-variant hover:border-primary/50'
          ]"
          :data-testid="`reaction-opt-${opt.id}`"
          @click="selectedReaction = opt.id"
        >
          <div class="flex items-start gap-3">
            <span
              class="mt-1 w-4 h-4 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors duration-150 ease-desk"
              :class="selectedReaction === opt.id ? 'border-primary' : 'border-outline'"
            >
              <span
                class="w-2 h-2 rounded-full bg-primary transition-transform duration-150 ease-desk"
                :class="selectedReaction === opt.id ? 'scale-100' : 'scale-0'"
              ></span>
            </span>
            <div class="flex flex-col gap-0.5">
              <span class="font-sans text-body font-semibold text-on-surface">{{ opt.title }}</span>
              <span class="font-sans text-meta text-on-surface-variant">{{ opt.description }}</span>
            </div>
          </div>
        </button>
      </div>

      <!-- Derived Profile Summary -->
      <div class="bg-surface-container-lowest px-lg py-4 rounded-xl border border-outline-variant shadow-sheet flex items-center justify-between gap-md">
        <div class="flex flex-col">
          <span class="font-sans text-meta text-on-surface-variant">Derived risk profile</span>
          <span class="font-sans text-heading font-semibold capitalize text-on-surface" data-testid="derived-tier-display">
            {{ derivedTier }} Risk Tolerance
          </span>
        </div>
        <span class="font-sans text-meta font-semibold capitalize text-primary">
          {{ derivedTier }}
        </span>
      </div>

      <div class="pt-2">
        <button
          type="button"
          class="w-full bg-primary text-on-primary font-sans text-body font-medium py-3.5 px-lg rounded-md hover:bg-primary-container transition-colors duration-200 ease-desk inline-flex items-center justify-center gap-2"
          data-testid="confirm-risk-calibration-btn"
          @click="submitRiskCalibration"
        >
          <span>Review Target Bands</span>
          <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
        </button>
      </div>
    </div>

    <!-- Right Column: Live Policy Model Preview -->
    <aside class="lg:col-span-6 lg:sticky lg:top-24">
      <div class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden flex flex-col">
        <div class="p-lg border-b border-outline-variant flex flex-col gap-1">
          <h2 class="font-sans text-heading font-semibold text-on-surface">Policy Calibration Preview</h2>
          <p class="font-sans text-meta text-on-surface-variant tabular-nums">
            Deterministic mapping from {{ horizonYears }}-year horizon and "{{ selectedReaction.replace('_', ' ') }}" reaction.
          </p>
        </div>

        <div class="p-lg flex flex-col gap-md">
          <div v-for="band in defaultBands" :key="band.asset_class" class="flex flex-col gap-1.5">
            <div class="flex justify-between items-baseline font-sans text-body tabular-nums">
              <span class="font-medium text-on-surface">{{ band.asset_class }}</span>
              <span class="font-semibold text-on-surface">
                {{ band.target_percent }}%
                <span class="text-meta font-normal text-on-surface-variant">
                  ({{ band.min_percent }}%-{{ band.max_percent }}%)
                </span>
              </span>
            </div>
            <div class="h-2 w-full bg-surface-container-low rounded-full overflow-hidden">
              <div
                class="h-full bg-primary transition-[width] duration-200 ease-desk rounded-full"
                :style="{ width: `${band.target_percent}%` }"
              ></div>
            </div>
          </div>
        </div>

        <div class="px-lg py-4 border-t border-outline-variant bg-surface-container-low/40 flex items-start gap-2.5">
          <span class="material-symbols-outlined text-[18px] text-outline mt-0.5 shrink-0" aria-hidden="true">info</span>
          <p class="font-sans text-meta text-on-surface-variant max-w-[65ch]">
            A {{ horizonYears }}-year horizon with a "{{ selectedReaction.replace('_', ' ') }}" reaction maps to a
            <strong class="text-on-surface font-semibold">{{ derivedTier }}</strong> allocation. You can adjust target weights and tolerance bands on the next step.
          </p>
        </div>
      </div>
    </aside>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { RiskToleranceTier, DrawdownReaction, AllocationBand } from '../../types';
import { deriveRiskTolerance, getDefaultAllocationBands } from '../../services/onboarding';

interface ReactionOption {
  id: DrawdownReaction;
  title: string;
  description: string;
}

const props = withDefaults(
  defineProps<{
    initialHorizonYears?: number;
    initialReaction?: DrawdownReaction;
  }>(),
  {
    initialHorizonYears: 15,
    initialReaction: 'hold'
  }
);

const emit = defineEmits<{
  (e: 'next', payload: {
    drawdownReaction: DrawdownReaction;
    riskTolerance: RiskToleranceTier;
    defaultBands: AllocationBand[];
  }): void;
}>();

const horizonYears = ref(props.initialHorizonYears);
const selectedReaction = ref<DrawdownReaction>(props.initialReaction);

const reactionOptions: ReactionOption[] = [
  {
    id: 'buy_more',
    title: 'Buy More (Opportunistic Growth)',
    description: 'Deploy reserve cash into depressed valuations to accelerate long-term capital accumulation.'
  },
  {
    id: 'hold',
    title: 'Hold Steady (Discipline & Rebalancing)',
    description: 'Maintain policy weights, ignore short-term noise, and let time compound returns.'
  },
  {
    id: 'sell',
    title: 'Sell to Capital Preservation',
    description: 'Liquidate equities to cash or short-duration treasuries to prevent further portfolio drawdown.'
  }
];

const derivedTier = computed<RiskToleranceTier>(() => {
  return deriveRiskTolerance(horizonYears.value, selectedReaction.value);
});

const defaultBands = computed<AllocationBand[]>(() => {
  return getDefaultAllocationBands(derivedTier.value);
});

function submitRiskCalibration() {
  emit('next', {
    drawdownReaction: selectedReaction.value,
    riskTolerance: derivedTier.value,
    defaultBands: JSON.parse(JSON.stringify(defaultBands.value))
  });
}
</script>
