<template>
  <div class="flex flex-col gap-lg max-w-2xl mx-auto w-full" data-testid="target-allocation-step">
    <header class="flex flex-col gap-1">
      <h1 class="font-display text-page-title font-medium text-on-surface">Target Allocation &amp; Bands</h1>
      <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
        Review and adjust target weights and min-to-max tolerance bands used for portfolio drift checks.
      </p>
    </header>

    <!-- Chart & Model Readout Sheet -->
    <section class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sheet flex flex-col gap-lg">
      <div class="flex justify-between items-end gap-md pb-md border-b border-outline-variant">
        <div>
          <span class="font-sans text-meta text-on-surface-variant block mb-0.5">Projected annual return</span>
          <span class="font-display text-display-figure font-medium text-on-surface tabular-nums" data-testid="projected-return">
            {{ projectedReturn }}
          </span>
        </div>
        <div class="text-right">
          <span class="font-sans text-meta text-on-surface-variant block mb-0.5">Risk profile tier</span>
          <span class="font-sans text-heading font-semibold text-on-surface capitalize" data-testid="risk-score">
            {{ computedRiskScore }}
          </span>
        </div>
      </div>

      <div class="relative w-44 h-44 mx-auto flex items-center justify-center">
        <svg aria-label="Asset Allocation Chart" class="w-full h-full transform -rotate-90" viewBox="0 0 100 100">
          <circle
            v-for="(arc, idx) in chartArcs"
            :key="idx"
            cx="50"
            cy="50"
            r="40"
            fill="transparent"
            :stroke="arc.color"
            stroke-width="11"
            :stroke-dasharray="`${arc.len} 251.2`"
            :stroke-dashoffset="arc.offset"
            class="transition-[stroke-dasharray,stroke-dashoffset] duration-300 ease-desk"
          ></circle>
        </svg>
        <div class="absolute inset-0 flex flex-col items-center justify-center pointer-events-none">
          <span class="font-sans text-heading font-semibold text-on-surface tabular-nums" data-testid="total-percent-display">{{ totalTargetPercent }}%</span>
          <span class="font-sans text-meta text-on-surface-variant">Total target</span>
        </div>
      </div>
    </section>

    <!-- Bands & Sliders -->
    <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet divide-y divide-outline-variant overflow-hidden">
      <div
        v-for="(band, idx) in bands"
        :key="band.asset_class"
        class="p-lg flex flex-col gap-3"
        data-testid="band-row"
      >
        <div class="flex justify-between items-center gap-md">
          <div class="flex items-center gap-2.5">
            <span
              class="w-3 h-3 rounded-sm shrink-0"
              :style="{ backgroundColor: arcColors[idx % arcColors.length] }"
              aria-hidden="true"
            ></span>
            <span class="font-sans text-body font-semibold text-on-surface">{{ band.asset_class }}</span>
          </div>
          <div class="flex items-center gap-1.5 tabular-nums">
            <label class="font-sans text-meta text-on-surface-variant">Target</label>
            <input
              v-model.number="band.target_percent"
              type="number"
              min="0"
              max="100"
              class="w-16 bg-surface text-center font-sans text-body py-1 px-2 rounded-md border border-outline-variant text-on-surface"
              :data-testid="`input-target-${idx}`"
            />
            <span class="font-sans text-meta text-on-surface-variant">%</span>
          </div>
        </div>

        <input
          v-model.number="band.target_percent"
          type="range"
          min="0"
          max="100"
          class="w-full h-2 bg-surface-container rounded-lg appearance-none cursor-pointer accent-primary"
          :data-testid="`slider-target-${idx}`"
        />

        <div class="flex items-center justify-between gap-md font-sans text-meta text-on-surface-variant tabular-nums">
          <span>Drift bounds</span>
          <div class="flex items-center gap-2">
            <div class="flex items-center gap-1">
              <span>Min</span>
              <input
                v-model.number="band.min_percent"
                type="number"
                min="0"
                max="100"
                class="w-14 bg-surface text-center font-sans text-meta py-0.5 px-1 rounded border border-outline-variant text-on-surface"
                :data-testid="`input-min-${idx}`"
              />
              <span>%</span>
            </div>
            <span>to</span>
            <div class="flex items-center gap-1">
              <span>Max</span>
              <input
                v-model.number="band.max_percent"
                type="number"
                min="0"
                max="100"
                class="w-14 bg-surface text-center font-sans text-meta py-0.5 px-1 rounded border border-outline-variant text-on-surface"
                :data-testid="`input-max-${idx}`"
              />
              <span>%</span>
            </div>
          </div>
        </div>

        <div
          v-if="band.min_percent > band.target_percent || band.target_percent > band.max_percent"
          class="font-sans text-meta text-error flex items-center gap-1.5"
        >
          <span class="material-symbols-outlined text-[16px]" aria-hidden="true">error</span>
          <span>Constraint violation: Min ({{ band.min_percent }}%) &le; Target ({{ band.target_percent }}%) &le; Max ({{ band.max_percent }}%) required.</span>
        </div>
      </div>
    </section>

    <!-- Warning if total != 100 -->
    <div
      v-if="totalTargetPercent !== 100"
      class="bg-error-container text-on-error-container border border-error/30 p-md rounded-lg flex items-center gap-2.5"
      data-testid="allocation-warning"
    >
      <span class="material-symbols-outlined text-error text-[20px]" aria-hidden="true">warning</span>
      <span class="font-sans text-body tabular-nums">
        Total target allocation must equal 100%. Currently: <span class="font-semibold">{{ totalTargetPercent }}%</span>
      </span>
    </div>

    <div>
      <button
        type="button"
        class="w-full bg-primary text-on-primary py-3.5 px-lg rounded-md font-sans text-body font-medium inline-flex items-center justify-center gap-2 transition-colors duration-200 ease-desk hover:bg-primary-container disabled:opacity-50 disabled:cursor-not-allowed"
        :disabled="!isValid"
        data-testid="confirm-allocation-btn"
        @click="confirmAllocation"
      >
        <span>Continue to Policy Constraints</span>
        <span class="material-symbols-outlined text-[18px]" aria-hidden="true">arrow_forward</span>
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
const arcColors = ['#0f2342', '#1e40af', '#047857'];

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
