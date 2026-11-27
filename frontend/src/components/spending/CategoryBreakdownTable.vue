<template>
  <section
    class="bg-surface-container-lowest rounded-xl shadow-sheet border border-outline-variant overflow-hidden flex flex-col"
    data-testid="category-breakdown-table"
  >
    <div class="px-lg py-4 border-b border-outline-variant flex items-baseline justify-between gap-md">
      <h3 class="font-sans text-heading font-semibold text-on-surface">Spend by Category</h3>
      <span class="font-sans text-meta text-on-surface-variant">30-day total</span>
    </div>

    <div v-if="sortedCategories.length > 0" class="p-lg flex flex-col gap-md">
      <div
        v-for="item in sortedCategories"
        :key="item.category"
        class="flex flex-col gap-1.5"
        data-testid="category-row"
      >
        <div class="flex items-baseline justify-between gap-md">
          <span class="font-sans text-body font-medium text-on-surface capitalize">{{ item.category }}</span>
          <div class="flex items-baseline gap-lg tabular-nums shrink-0">
            <span class="font-sans text-meta text-on-surface-variant">{{ item.percent_of_total }}%</span>
            <span class="font-sans text-body font-semibold text-on-surface w-24 text-right">
              ${{ item.amount_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
            </span>
          </div>
        </div>
        <div class="h-2 w-full bg-surface-container-low rounded-full overflow-hidden">
          <div
            class="h-full bg-primary transition-[width] duration-200 ease-desk rounded-full"
            :style="{ width: `${Math.min(100, item.percent_of_total)}%` }"
          ></div>
        </div>
      </div>
    </div>

    <div v-else class="p-lg text-center font-sans text-body text-on-surface-variant">
      No category spending data available yet.
    </div>
  </section>
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
