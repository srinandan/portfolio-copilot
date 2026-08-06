<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="target-allocation-step">
    <!-- Header Section -->
    <div class="flex flex-col gap-sm">
      <div class="flex items-center gap-xs text-secondary">
        <span class="material-symbols-outlined text-[16px]">pie_chart</span>
        <span class="font-label-caps uppercase tracking-wider">Turn 4 of 5 • Asset Allocation &amp; Drift Bands</span>
      </div>
      <h1 class="font-headline-lg-mobile text-on-surface">Target Allocation &amp; Bands</h1>
      <p class="font-body-base text-on-surface-variant">
        Review and override default target weights and tolerance bands (min–max) used downstream for rebalancing alerts.
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
              Baseline Model
            </span>
          </div>
        </div>
        <div class="text-right">
          <span class="font-label-caps text-on-surface-variant uppercase tracking-wider block mb-1">Risk Profile Tier</span>
          <span class="font-headline-md text-on-surface capitalize" data-testid="risk-score">{{ computedRiskScore }}</span>
        </div>
      </div>

      <!-- Donut Chart Visualization (Inline SVG) -->
      <div class="relative w-48 h-48 mx-auto flex items-center justify-center z-10">
        <svg aria-label="Asset Allocation Chart" class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <circle
            v-for="(arc, idx) in chartArcs"
            :key="idx"
            cx="50"
            cy="50"
            r="40"
            fill="transparent"
            :stroke="arc.color"
            stroke-width="12"
            :stroke-dasharray="`${arc.len} 251.2`"
            :stroke-dashoffset="arc.offset"
            class="transition-all duration-500 ease-out"
          ></circle>
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span class="font-title-sm text-on-surface" data-testid="total-percent-display">{{ totalTargetPercent }}%</span>
          <span class="font-label-caps text-on-surface-variant">Total Target</span>
        </div>
      </div>
    </div>

    <!-- Bands & Sliders Section -->
    <div class="flex flex-col gap-md">
      <div
        v-for="(band, idx) in bands"
        :key="band.asset_class"
        class="bg-surface-container-lowest rounded-lg p-md shadow-sm border border-outline-variant flex flex-col gap-md"
        data-testid="band-row"
      >
        <!-- Header & Target Input -->
        <div class="flex justify-between items-center">
          <div class="flex items-center gap-sm">
            <div
              class="w-3 h-3 rounded-full"
              :class="[
                idx === 0 ? 'bg-primary-container' :
                idx === 1 ? 'bg-secondary-fixed' :
                'bg-surface-tint'
              ]"
            ></div>
            <span class="font-title-sm text-on-surface">{{ band.asset_class }}</span>
          </div>
          <div class="flex items-center gap-2">
            <label class="font-label-caps text-xs text-on-surface-variant uppercase">Target:</label>
            <input
              v-model.number="band.target_percent"
              type="number"
              min="0"
              max="100"
              class="w-16 bg-surface-container text-center font-body-mono py-1 px-2 rounded focus:outline-none focus:ring-2 focus:ring-primary-container border border-outline-variant"
              :data-testid="`input-target-${idx}`"
            />
            <span class="font-body-base text-on-surface-variant">%</span>
          </div>
        </div>

        <!-- Target Slider -->
        <div class="relative w-full h-6 flex items-center">
          <input
            v-model.number="band.target_percent"
            type="range"
            min="0"
            max="100"
            class="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-primary-container"
            :data-testid="`slider-target-${idx}`"
          />
        </div>

        <!-- Tolerance Bands (Min & Max Bounds) -->
        <div class="bg-surface-container-low p-sm rounded-md flex items-center justify-between gap-md border border-outline-variant/30 text-xs">
          <span class="font-label-caps text-on-surface-variant uppercase">Drift Bounds:</span>
          <div class="flex items-center gap-sm">
            <div class="flex items-center gap-1">
              <span class="text-on-surface-variant">Min:</span>
              <input
                v-model.number="band.min_percent"
                type="number"
                min="0"
                max="100"
                class="w-14 bg-surface-container text-center font-body-mono py-0.5 px-1 rounded border border-outline-variant"
                :data-testid="`input-min-${idx}`"
              />
              <span class="text-on-surface-variant">%</span>
            </div>
            <span class="text-outline-variant">–</span>
            <div class="flex items-center gap-1">
              <span class="text-on-surface-variant">Max:</span>
              <input
                v-model.number="band.max_percent"
                type="number"
                min="0"
                max="100"
                class="w-14 bg-surface-container text-center font-body-mono py-0.5 px-1 rounded border border-outline-variant"
                :data-testid="`input-max-${idx}`"
              />
              <span class="text-on-surface-variant">%</span>
            </div>
          </div>
        </div>

        <!-- Invalid Band Bounds Warning -->
        <div
          v-if="band.min_percent > band.target_percent || band.target_percent > band.max_percent"
          class="text-xs text-error font-body-mono flex items-center gap-1"
        >
          <span class="material-symbols-outlined text-[14px]">error</span>
          <span>Constraint violation: Min ({{ band.min_percent }}%) &le; Target ({{ band.target_percent }}%) &le; Max ({{ band.max_percent }}%) required.</span>
        </div>
      </div>

      <!-- Warning Toast if total != 100 -->
      <div
        v-if="totalTargetPercent !== 100"
        class="bg-error-container text-on-error-container p-4 rounded-lg flex items-center gap-sm transition-opacity"
        data-testid="allocation-warning"
      >
        <span class="material-symbols-outlined text-error">warning</span>
        <span class="font-body-base text-body-base">
          Total target allocation must equal 100%. Currently: <span class="font-body-mono font-bold">{{ totalTargetPercent }}</span>%
        </span>
      </div>
    </div>

    <!-- Confirm Button -->
    <div class="mt-md">
      <button
        class="w-full bg-primary-container text-on-primary py-md px-lg rounded-lg font-title-sm flex items-center justify-center gap-sm transition-colors shadow-md hover:bg-primary-container/90 disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!isValid"
        data-testid="confirm-allocation-btn"
        @click="confirmAllocation"
      >
        <span>Continue to Policy Constraints</span>
        <span class="material-symbols-outlined">arrow_forward</span>
      </button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue';
import type { AllocationBand } from '../../types';

const props = withDefaults(
  defineProps<{
    initialBands?: AllocationBand[];
  }>(),
  {
    initialBands: () => [
      { asset_class: 'Equities (US & Global)', target_percent: 60, min_percent: 50, max_percent: 70 },
      { asset_class: 'Fixed Income (Bonds)', target_percent: 30, min_percent: 20, max_percent: 40 },
      { asset_class: 'Cash & Equivalents', target_percent: 10, min_percent: 5, max_percent: 15 }
    ]
  }
);

const emit = defineEmits<{
  (e: 'confirm', bands: AllocationBand[]): void;
}>();

const bands = ref<AllocationBand[]>(JSON.parse(JSON.stringify(props.initialBands)));

watch(
  () => props.initialBands,
  (newBands) => {
    if (newBands && newBands.length > 0) {
      bands.value = JSON.parse(JSON.stringify(newBands));
    }
  },
  { deep: true }
);

const totalTargetPercent = computed(() => {
  return bands.value.reduce((sum, b) => sum + (Number(b.target_percent) || 0), 0);
});

const CIRCUMFERENCE = 251.2;
const arcColors = ['#131b2e', '#b9c7e0', '#565e74'];

const chartArcs = computed(() => {
  let accumulatedOffset = 0;
  return bands.value.map((band, idx) => {
    const pct = Math.max(0, band.target_percent) / 100;
    const len = pct * CIRCUMFERENCE;
    const offset = -accumulatedOffset;
    accumulatedOffset += len;
    return {
      len,
      offset: `${offset}`,
      color: arcColors[idx % arcColors.length]
    };
  });
});

const projectedReturn = computed(() => {
  const eq = bands.value[0]?.target_percent || 0;
  const fi = bands.value[1]?.target_percent || 0;
  const cash = bands.value[2]?.target_percent || 0;
  const ret = (eq * 0.08) + (fi * 0.04) + (cash * 0.01);
  return ret.toFixed(1) + '%';
});

const computedRiskScore = computed(() => {
  const eq = bands.value[0]?.target_percent || 0;
  if (eq >= 70) return 'Aggressive';
  if (eq >= 40) return 'Moderate';
  return 'Conservative';
});

const isValid = computed(() => {
  if (totalTargetPercent.value !== 100) return false;
  return bands.value.every(
    b => b.min_percent <= b.target_percent && b.target_percent <= b.max_percent && b.min_percent >= 0 && b.max_percent <= 100
  );
});

function confirmAllocation() {
  if (isValid.value) {
    emit('confirm', JSON.parse(JSON.stringify(bands.value)));
  }
}
</script>
