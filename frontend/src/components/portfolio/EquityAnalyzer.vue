<template>
  <div
    class="w-full bg-surface-container-lowest rounded-xl shadow-sm border border-surface-variant flex flex-col p-lg gap-md"
    data-testid="equity-analyzer"
  >
    <div class="flex flex-col gap-xs">
      <h2 class="font-headline-sm text-headline-sm text-on-background">Research a stock</h2>
      <p class="font-body-base text-body-base text-on-surface-variant max-w-md">
        Get an advisory read on a single stock — a DCF valuation plus how it fits your policy and holdings.
        Advisory only; it never places a trade.
      </p>
    </div>

    <form class="flex items-end gap-sm flex-wrap" data-testid="equity-analyzer-form" @submit.prevent="analyze">
      <label class="flex flex-col gap-1">
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase tracking-wider">Ticker</span>
        <input
          v-model="ticker"
          type="text"
          placeholder="e.g. AAPL"
          maxlength="6"
          class="px-3 py-2 rounded-lg border border-surface-variant bg-surface-container-lowest font-body-mono text-body-mono text-on-surface uppercase w-40 focus:outline-none focus:ring-2 focus:ring-primary"
          data-testid="input-equity-ticker"
        />
      </label>
      <Button type="submit" icon="query_stats" :disabled="loading || !ticker.trim()" data-testid="btn-analyze-equity">
        {{ loading ? 'Analyzing…' : 'Analyze' }}
      </Button>
    </form>

    <p v-if="error" class="font-body-base text-sm text-red-700" data-testid="equity-analyzer-error">{{ error }}</p>

    <EquityRecommendationCard v-if="result" :result="result" />
  </div>
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
