<template>
  <div
    class="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant flex flex-col p-lg gap-md"
    data-testid="equity-recommendation-card"
  >
    <!-- Header: ticker + direction badge -->
    <div class="flex items-center justify-between gap-md flex-wrap">
      <div class="flex flex-col">
        <h3 class="font-headline-sm text-headline-sm text-on-background" data-testid="equity-ticker">
          {{ rec.ticker }}<span v-if="assess.company_name" class="text-on-surface-variant font-body-base">
            &nbsp;· {{ assess.company_name }}</span>
        </h3>
        <span class="font-body-mono text-xs text-on-surface-variant uppercase tracking-wider">
          {{ verdictLabel }} · {{ rec.conviction }} conviction
        </span>
      </div>
      <span
        :class="['px-3 py-1 rounded-full font-label-caps text-label-caps uppercase tracking-wider', directionClasses]"
        data-testid="equity-direction"
      >
        {{ rec.direction }}
      </span>
    </div>

    <!-- Valuation snapshot -->
    <div class="grid grid-cols-3 gap-sm" data-testid="equity-valuation">
      <div class="flex flex-col">
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">Price</span>
        <span class="font-body-mono text-body-mono text-on-surface tabular-nums">{{ fmtUsd(assess.dcf?.current_price_usd) }}</span>
      </div>
      <div class="flex flex-col">
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">Intrinsic (DCF)</span>
        <span class="font-body-mono text-body-mono text-on-surface tabular-nums">{{ fmtUsd(assess.dcf?.intrinsic_value_per_share_usd) }}</span>
      </div>
      <div class="flex flex-col">
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">Upside</span>
        <span :class="['font-body-mono text-body-mono tabular-nums', upsideClass]" data-testid="equity-upside">
          {{ fmtPct(rec.upside_pct) }}
        </span>
      </div>
    </div>

    <!-- Rationale -->
    <p class="font-body-base text-body-base text-on-surface" data-testid="equity-rationale">{{ rec.rationale }}</p>

    <!-- Suitability factors -->
    <div v-if="rec.suitability_factors.length" class="flex flex-col gap-xs">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Suitability</span>
      <ul class="flex flex-col gap-1">
        <li
          v-for="(f, i) in rec.suitability_factors"
          :key="i"
          class="flex items-start gap-2 font-body-base text-sm text-on-surface"
          data-testid="equity-factor"
        >
          <span class="material-symbols-outlined text-[16px] mt-0.5" :class="factorIconClass(f.favorable)">{{ factorIcon(f.favorable) }}</span>
          <span>{{ f.detail }}</span>
        </li>
      </ul>
    </div>

    <!-- Risks -->
    <div v-if="rec.key_risks.length" class="flex flex-col gap-xs">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Key risks</span>
      <ul class="list-disc pl-5 flex flex-col gap-1">
        <li v-for="(r, i) in rec.key_risks" :key="i" class="font-body-base text-sm text-on-surface-variant" data-testid="equity-risk">
          {{ r }}
        </li>
      </ul>
    </div>

    <!-- Disclaimers -->
    <p
      v-for="(d, i) in rec.disclaimers"
      :key="i"
      class="font-body-mono text-xs text-on-surface-variant italic"
      data-testid="equity-disclaimer"
    >
      {{ d }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { EquityAnalysisResult } from '../../types';

const props = defineProps<{ result: EquityAnalysisResult }>();

const rec = computed(() => props.result.recommendation);
const assess = computed(() => props.result.assessment);

const verdictLabel = computed(() => rec.value.valuation_verdict.replace('_', ' '));

const directionClasses = computed(() => {
  switch (rec.value.direction) {
    case 'buy':
    case 'add':
      return 'bg-emerald-100 text-emerald-800';
    case 'trim':
    case 'avoid':
      return 'bg-red-100 text-red-800';
    default:
      return 'bg-amber-100 text-amber-800';
  }
});

const upsideClass = computed(() => {
  const u = rec.value.upside_pct;
  if (u === null || u === undefined) return 'text-on-surface-variant';
  return u >= 0 ? 'text-emerald-700' : 'text-red-700';
});

function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '—';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function factorIcon(favorable?: boolean | null): string {
  if (favorable === true) return 'check_circle';
  if (favorable === false) return 'cancel';
  return 'radio_button_unchecked';
}

function factorIconClass(favorable?: boolean | null): string {
  if (favorable === true) return 'text-emerald-600';
  if (favorable === false) return 'text-red-600';
  return 'text-on-surface-variant';
}
</script>
