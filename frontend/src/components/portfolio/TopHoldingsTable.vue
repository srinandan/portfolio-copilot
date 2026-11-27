<template>
  <section class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden">
    <div class="px-lg py-4 border-b border-outline-variant flex items-baseline justify-between gap-md">
      <h3 class="font-sans text-heading font-semibold text-on-surface">Top Holdings</h3>
      <span v-if="sortedPositions.length > 0" class="font-sans text-meta text-on-surface-variant tabular-nums">
        {{ sortedPositions.length }} positions
      </span>
    </div>

    <div v-if="sortedPositions.length > 0" class="overflow-x-auto">
      <table class="w-full text-left border-collapse">
        <thead>
          <tr class="border-b border-outline-variant bg-surface-container-low/50 font-sans text-meta font-medium text-on-surface-variant">
            <th class="py-2.5 pl-lg pr-4">Holding</th>
            <th class="py-2.5 px-4 hidden sm:table-cell">Asset class</th>
            <th class="py-2.5 px-4 text-right">Shares</th>
            <th class="py-2.5 pl-4 pr-lg text-right">Market value</th>
          </tr>
        </thead>
        <tbody class="divide-y divide-outline-variant/60 tabular-nums">
          <tr
            v-for="pos in sortedPositions"
            :key="pos.ticker"
            class="hover:bg-surface-container-low/50 transition-colors duration-150 ease-desk"
            data-testid="holding-row"
          >
            <td class="py-3 pl-lg pr-4">
              <div class="flex items-center gap-3">
                <div class="min-w-12 h-10 px-1.5 rounded-md bg-surface-container-low border border-outline-variant/70 flex items-center justify-center font-sans text-meta font-semibold text-primary shrink-0">
                  {{ pos.ticker }}
                </div>
                <div class="flex flex-col min-w-0">
                  <span class="font-sans text-body font-medium text-on-surface truncate">
                    {{ pos.name || pos.ticker }}
                  </span>
                  <span class="font-sans text-meta text-on-surface-variant sm:hidden">
                    {{ pos.asset_class }}
                  </span>
                </div>
              </div>
            </td>
            <td class="py-3 px-4 font-sans text-meta text-on-surface-variant hidden sm:table-cell">
              {{ pos.asset_class }}
            </td>
            <td class="py-3 px-4 text-right font-sans text-body text-on-surface-variant">
              {{ pos.quantity.toLocaleString('en-US') }}
            </td>
            <td class="py-3 pl-4 pr-lg text-right">
              <div class="flex flex-col items-end">
                <span class="font-sans text-body font-semibold text-on-surface">
                  ${{ getPositionValue(pos).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
                </span>
                <span
                  v-if="pos.change_percent !== undefined && pos.change_percent !== null"
                  :class="[
                    'font-sans text-meta font-medium',
                    (pos.change_percent || 0) >= 0 ? 'text-on-tertiary-container' : 'text-error'
                  ]"
                >
                  {{ (pos.change_percent || 0) >= 0 ? '+' : '' }}{{ pos.change_percent }}%
                </span>
              </div>
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <div v-else class="p-lg text-center font-sans text-body text-on-surface-variant">
      No holdings positions available.
    </div>
  </section>
</template>

<script setup lang="ts">
import { computed } from 'vue';
import type { Position } from '../../types';

const props = withDefaults(
  defineProps<{
    positions?: Position[];
    limit?: number;
  }>(),
  {
    positions: () => [],
    limit: 5
  }
);

function getPositionValue(pos: Position): number {
  return pos.current_value_usd ?? pos.market_value_usd ?? (pos.quantity * (pos.current_price_usd ?? 0));
}

const sortedPositions = computed(() => {
  if (!props.positions || props.positions.length === 0) return [];
  return props.positions
    .slice()
    .sort((a, b) => getPositionValue(b) - getPositionValue(a))
    .slice(0, props.limit);
});
</script>
