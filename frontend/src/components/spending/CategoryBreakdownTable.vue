<template>
  <div class="bg-surface-container-lowest rounded-xl p-lg shadow-sm border border-surface-variant flex flex-col gap-md" data-testid="category-breakdown-table">
    <div class="flex items-center justify-between border-b border-surface-variant pb-2">
      <h3 class="font-title-sm text-title-sm text-on-surface">Spend by Category</h3>
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">30-Day Total</span>
    </div>
    <div class="flex flex-col gap-sm">
      <div
        v-for="item in sortedCategories"
        :key="item.category"
        class="flex flex-col gap-xs py-1"
        data-testid="category-row"
      >
        <div class="flex items-center justify-between text-sm">
          <span class="font-body-base text-on-surface font-medium capitalize">{{ item.category }}</span>
          <div class="flex items-center gap-md tabular-nums">
            <span class="font-body-base text-on-surface-variant text-xs">{{ item.percent_of_total }}%</span>
            <span class="font-body-mono text-on-surface font-semibold w-24 text-right">
              ${{ item.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
            </span>
          </div>
        </div>
        <!-- Progress Bar -->
        <div class="h-2 w-full bg-surface-container rounded-full overflow-hidden">
          <div
            class="h-full bg-primary-fixed transition-all duration-300 rounded-full"
            :style="{ width: `${Math.min(100, item.percent_of_total)}%` }"
          ></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { CategorySpending } from '../../types';

const props = defineProps<{
  categories: CategorySpending[];
}>();

const sortedCategories = computed(() => {
  return [...props.categories].sort((a, b) => b.amount_usd - a.amount_usd);
});
</script>
