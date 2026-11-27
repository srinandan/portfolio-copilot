<template>
  <section
    class="w-full bg-surface-container-lowest rounded-xl shadow-sheet border border-outline-variant flex flex-col overflow-hidden"
    data-testid="equity-analyzer"
  >
    <div class="p-lg flex flex-col gap-md">
      <div class="flex flex-col gap-1">
        <h2 class="font-sans text-heading font-semibold text-on-surface">Research a stock</h2>
        <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
          Get an advisory read on a single stock combining a DCF valuation with your active policy and holdings.
          Advisory only; it never places a trade.
        </p>
      </div>

      <form class="flex items-end gap-3 flex-wrap" data-testid="equity-analyzer-form" @submit.prevent="analyze">
        <label class="flex flex-col gap-1.5">
          <span class="font-sans text-meta font-medium text-on-surface-variant">Ticker symbol</span>
          <input
            v-model="ticker"
            type="text"
            placeholder="e.g. AAPL"
            maxlength="6"
            class="px-3.5 py-2 rounded-md border border-outline-variant bg-surface font-sans text-body font-medium text-on-surface uppercase w-44 tabular-nums focus:bg-surface-container-lowest transition-colors duration-200 ease-desk"
            data-testid="input-equity-ticker"
          />
        </label>
        <Button type="submit" icon="query_stats" :disabled="loading || !ticker.trim()" data-testid="btn-analyze-equity">
          {{ loading ? 'Analyzing...' : 'Analyze' }}
        </Button>
      </form>

      <p v-if="error" class="font-sans text-meta font-medium text-error" data-testid="equity-analyzer-error">
        {{ error }}
      </p>
    </div>

    <div v-if="result" class="border-t border-outline-variant">
      <EquityRecommendationCard :result="result" embedded />
    </div>
  </section>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import Button from '../common/Button.vue';
import EquityRecommendationCard from './EquityRecommendationCard.vue';
import { apiService } from '../../services/api';
import type { EquityAnalysisResult } from '../../types';

const props = withDefaults(defineProps<{ userId?: string }>(), { userId: 'demo_user' });

const ticker = ref('');
const loading = ref(false);
const error = ref('');
const result = ref<EquityAnalysisResult | null>(null);

async function analyze() {
  const symbol = ticker.value.trim().toUpperCase();
  if (!symbol) return;
  loading.value = true;
  error.value = '';
  try {
    result.value = await apiService.analyzeEquity(symbol, props.userId);
  } catch (e) {
    error.value = e instanceof Error ? e.message : 'Analysis failed. Please try again.';
    result.value = null;
  } finally {
    loading.value = false;
  }
}
</script>
