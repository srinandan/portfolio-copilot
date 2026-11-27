<template>
  <div
    :class="[
      'w-full flex flex-col p-lg gap-md',
      embedded
        ? 'bg-surface-container-low/30'
        : 'bg-surface-container-lowest rounded-xl shadow-sheet border border-outline-variant'
    ]"
    data-testid="equity-recommendation-card"
  >
    <!-- Header: Ticker & Recommendation -->
    <div class="flex items-start justify-between gap-md flex-wrap">
      <div class="flex flex-col gap-0.5">
        <h3 class="font-sans text-heading font-semibold text-on-surface" data-testid="equity-ticker">
          {{ rec.ticker }}<span v-if="assess.company_name" class="text-on-surface-variant font-normal">
            &middot; {{ assess.company_name }}
          </span>
        </h3>
        <span class="font-sans text-meta text-on-surface-variant capitalize">
          {{ verdictLabel }} &middot; {{ rec.conviction }} conviction
        </span>
      </div>
      <span
        :class="['px-3 py-1 rounded-md border font-sans text-meta font-semibold uppercase', directionClasses]"
        data-testid="equity-direction"
      >
        {{ rec.direction }}
      </span>
    </div>

    <!-- Valuation Strip -->
    <div
      class="grid grid-cols-1 sm:grid-cols-3 divide-y sm:divide-y-0 sm:divide-x divide-outline-variant rounded-md border border-outline-variant bg-surface-container-lowest tabular-nums"
      data-testid="equity-valuation"
    >
      <div class="p-3.5 flex flex-col gap-0.5">
        <span class="font-sans text-meta text-on-surface-variant">Price</span>
        <span class="font-sans text-heading font-semibold text-on-surface">{{ fmtUsd(assess.dcf?.current_price_usd) }}</span>
      </div>
      <div class="p-3.5 flex flex-col gap-0.5">
        <span class="font-sans text-meta text-on-surface-variant">Intrinsic (DCF)</span>
        <span class="font-sans text-heading font-semibold text-on-surface">{{ fmtUsd(assess.dcf?.intrinsic_value_per_share_usd) }}</span>
      </div>
      <div class="p-3.5 flex flex-col gap-0.5">
        <span class="font-sans text-meta text-on-surface-variant">Upside</span>
        <span :class="['font-sans text-heading font-semibold', upsideClass]" data-testid="equity-upside">
          {{ fmtPct(rec.upside_pct) }}
        </span>
      </div>
    </div>

    <!-- Rationale -->
    <p class="font-sans text-body text-on-surface max-w-[65ch]" data-testid="equity-rationale">
      {{ rec.rationale }}
    </p>

    <!-- Suitability & Risks -->
    <div class="grid grid-cols-1 md:grid-cols-2 gap-lg pt-3 border-t border-outline-variant/80">
      <div v-if="rec.suitability_factors.length" class="flex flex-col gap-2">
        <span class="font-sans text-meta font-semibold text-on-surface">Suitability</span>
        <ul class="flex flex-col gap-2">
          <li
            v-for="(f, i) in rec.suitability_factors"
            :key="i"
            class="flex items-start gap-2 font-sans text-body text-on-surface"
            data-testid="equity-factor"
          >
            <span class="material-symbols-outlined text-[18px] mt-0.5 shrink-0" :class="factorIconClass(f.favorable)" aria-hidden="true">
              {{ factorIcon(f.favorable) }}
            </span>
            <span>{{ f.detail }}</span>
          </li>
        </ul>
      </div>

      <div v-if="rec.key_risks.length" class="flex flex-col gap-2">
        <span class="font-sans text-meta font-semibold text-on-surface">Key risks</span>
        <ul class="list-disc pl-5 flex flex-col gap-1.5">
          <li
            v-for="(r, i) in rec.key_risks"
            :key="i"
            class="font-sans text-body text-on-surface-variant"
            data-testid="equity-risk"
          >
            {{ r }}
          </li>
        </ul>
      </div>
    </div>

    <!-- Disclaimers -->
    <div v-if="rec.disclaimers.length" class="pt-3 border-t border-outline-variant/60 flex flex-col gap-1">
      <p
        v-for="(d, i) in rec.disclaimers"
        :key="i"
        class="font-sans text-meta text-on-surface-variant"
        data-testid="equity-disclaimer"
      >
        {{ d }}
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { EquityAnalysisResult } from '../../types';

const props = withDefaults(
  defineProps<{
    result: EquityAnalysisResult;
    embedded?: boolean;
  }>(),
  { embedded: false }
);

const rec = computed(() => props.result.recommendation);
const assess = computed(() => props.result.assessment);

const verdictLabel = computed(() => rec.value.valuation_verdict.replace('_', ' '));

const directionClasses = computed(() => {
  switch (rec.value.direction) {
    case 'buy':
    case 'add':
      return 'bg-tertiary-fixed text-on-tertiary-fixed border-tertiary-fixed-dim';
    case 'trim':
    case 'avoid':
      return 'bg-error-container text-on-error-container border-error/25';
    default:
      return 'bg-secondary-fixed text-on-secondary-fixed border-secondary-fixed-dim';
  }
});

const upsideClass = computed(() => {
  const u = rec.value.upside_pct;
  if (u === null || u === undefined) return 'text-on-surface-variant';
  return u >= 0 ? 'text-on-tertiary-container' : 'text-error';
});

function fmtUsd(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--';
  return `$${v.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

function fmtPct(v: number | null | undefined): string {
  if (v === null || v === undefined) return '--';
  const sign = v >= 0 ? '+' : '';
  return `${sign}${v.toFixed(1)}%`;
}

function factorIcon(favorable?: boolean | null): string {
  if (favorable === true) return 'check_circle';
  if (favorable === false) return 'cancel';
  return 'radio_button_unchecked';
}

function factorIconClass(favorable?: boolean | null): string {
  if (favorable === true) return 'text-on-tertiary-container';
  if (favorable === false) return 'text-error';
  return 'text-outline';
}
</script>
