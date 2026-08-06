<template>
  <div class="flex flex-col lg:flex-row gap-gutter w-full max-w-7xl mx-auto" data-testid="risk-calibration-step">
    <!-- Left Panel: Conversational Stream (40%) -->
    <div class="w-full lg:w-[40%] flex flex-col gap-md">
      <!-- Trust Header -->
      <div class="flex items-center gap-sm mb-sm mt-xs opacity-80">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim" style="font-variation-settings: 'FILL' 1;">
          shield_lock
        </span>
        <span class="font-body-mono text-label-caps text-on-surface-variant tracking-wider uppercase">
          Deterministic Risk Calibration • Turn 3 of 5
        </span>
      </div>

      <!-- Agent Message -->
      <div class="bg-surface-container rounded-xl rounded-tl-sm p-lg relative group shadow-sm border border-outline-variant">
        <div class="absolute -left-[1px] top-lg bottom-lg w-[3px] bg-secondary-fixed rounded-r-full"></div>
        <div class="flex items-center gap-3 mb-md">
          <div class="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center border border-outline-variant">
            <span class="material-symbols-outlined text-[16px] text-on-primary" style="font-variation-settings: 'FILL' 1;">
              smart_toy
            </span>
          </div>
          <div>
            <div class="font-title-sm text-body-base text-on-surface">Portfolio Copilot</div>
            <div class="font-body-mono text-[10px] text-on-surface-variant uppercase tracking-widest">System Agent</div>
          </div>
        </div>
        <p class="font-body-base text-on-surface-variant leading-relaxed mb-md">
          Per institutional fiduciary governance, your risk profile is not a subjective survey guess—it is derived deterministically from your investment timeline and psychological drawdown capacity.
        </p>
        <p class="font-body-base text-on-surface font-semibold">
          Suppose market volatility triggers a sudden 20% drawdown across global indices next week. How would you react?
        </p>
      </div>

      <!-- Reaction Options -->
      <div class="flex flex-col gap-sm mt-sm">
        <button
          v-for="opt in reactionOptions"
          :key="opt.id"
          type="button"
          class="w-full text-left group bg-surface-container-lowest rounded-lg p-md border transition-all duration-200 shadow-sm"
          :class="[
            selectedReaction === opt.id
              ? 'border-primary ring-2 ring-primary/20 bg-surface-container-low'
              : 'border-outline-variant hover:border-primary/50'
          ]"
          :data-testid="`reaction-opt-${opt.id}`"
          @click="selectedReaction = opt.id"
        >
          <div class="flex items-start gap-md">
            <div
              class="mt-1 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors"
              :class="selectedReaction === opt.id ? 'border-primary' : 'border-outline group-hover:border-primary/50'"
            >
              <div
                class="w-2.5 h-2.5 rounded-full bg-primary transition-transform"
                :class="selectedReaction === opt.id ? 'scale-100' : 'scale-0'"
              ></div>
            </div>
            <div>
              <div class="font-title-sm text-body-base text-on-surface group-hover:text-primary transition-colors">
                {{ opt.title }}
              </div>
              <div class="font-body-base text-[13px] text-on-surface-variant mt-1">
                {{ opt.description }}
              </div>
            </div>
          </div>
        </button>
      </div>

      <!-- Derived Tier Pill Card -->
      <div class="bg-surface-container-lowest p-md rounded-xl border border-outline-variant shadow-sm flex items-center justify-between mt-sm">
        <div>
          <span class="font-label-caps text-on-surface-variant uppercase text-xs block">Derived Risk Profile</span>
          <span class="font-title-sm text-on-surface capitalize text-lg" data-testid="derived-tier-display">
            {{ derivedTier }} Risk Tolerance
          </span>
        </div>
        <span
          class="font-label-caps px-3 py-1 rounded-full uppercase font-bold text-xs"
          :class="[
            derivedTier === 'aggressive' ? 'bg-primary-container text-on-primary' :
            derivedTier === 'moderate' ? 'bg-secondary-container text-on-secondary-container' :
            'bg-surface-container-high text-on-surface'
          ]"
        >
          {{ derivedTier }}
        </span>
      </div>

      <!-- Action Area -->
      <div class="mt-lg flex items-center justify-between">
        <div class="font-body-mono text-[11px] text-on-surface-variant uppercase tracking-widest flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-tertiary-fixed-dim animate-pulse"></div>
          Deterministic Calibration Active
        </div>
        <button
          class="bg-primary-container text-on-primary font-title-sm text-body-base px-xl py-3 rounded-md shadow-sm hover:bg-primary-container/90 transition-colors flex items-center gap-2"
          data-testid="confirm-risk-calibration-btn"
          @click="submitRiskCalibration"
        >
          <span>Review Target Bands</span>
          <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
        </button>
      </div>
    </div>

    <!-- Right Panel: Telemetry Model Canvas (60%) -->
    <div class="hidden lg:flex w-[60%] flex-col gap-lg sticky top-24">
      <div class="w-full max-w-md mx-auto my-auto">
        <div class="mb-lg">
          <h3 class="font-title-sm text-headline-md text-on-surface mb-2">Policy Calibration Preview</h3>
          <p class="font-body-base text-on-surface-variant">Deterministic mapping from {{ horizonYears }}-year horizon + {{ selectedReaction }} reaction.</p>
        </div>

        <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sm backdrop-blur-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-sm mb-md">
            <span class="font-body-mono text-[11px] text-on-surface-variant tracking-widest uppercase">Target Allocation Bands</span>
            <span class="font-body-mono text-[11px] text-on-tertiary-container font-semibold tracking-widest uppercase">
              MODEL GENERATED
            </span>
          </div>

          <div class="space-y-4">
            <div v-for="band in defaultBands" :key="band.asset_class">
              <div class="flex justify-between font-body-mono text-[12px] text-on-surface mb-1">
                <span>{{ band.asset_class }}</span>
                <span class="font-bold">{{ band.target_percent }}% (Band: {{ band.min_percent }}–{{ band.max_percent }}%)</span>
              </div>
              <div class="h-2 w-full bg-surface-container rounded-full overflow-hidden">
                <div
                  class="h-full bg-primary-container transition-all duration-500"
                  :style="{ width: `${band.target_percent}%` }"
                ></div>
              </div>
            </div>
          </div>

          <div class="mt-lg pt-md border-t border-outline-variant flex items-start gap-3">
            <span class="material-symbols-outlined text-[20px] text-on-surface-variant">info</span>
            <p class="font-body-base text-[12px] text-on-surface-variant leading-snug">
              Per SKILL.md rules, {{ horizonYears }}y horizon with '{{ selectedReaction }}' reaction maps to <strong>{{ derivedTier }}</strong> allocation. You will have the opportunity to override these bounds on the next turn.
            </p>
          </div>
        </div>
      </div>
    </div>
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
