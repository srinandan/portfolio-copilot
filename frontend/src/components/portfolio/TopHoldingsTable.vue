<template>
  <div class="flex flex-col gap-md">
    <h3 class="font-title-sm text-title-sm text-on-background">Top Holdings</h3>
    <div v-if="sortedPositions.length > 0" class="flex flex-col gap-xs">
      <div
        v-for="pos in sortedPositions"
        :key="pos.ticker"
        class="bg-surface-container-lowest border border-surface-variant rounded-lg p-md flex items-center justify-between shadow-sm hover:bg-surface-container-low transition-colors cursor-pointer group"
        data-testid="holding-row"
      >
        <div class="flex items-center gap-md">
          <div class="w-10 h-10 rounded-full bg-primary-fixed/20 flex items-center justify-center text-primary font-body-mono text-body-mono font-bold group-hover:scale-105 transition-transform">
            {{ pos.ticker }}
          </div>
          <div class="flex flex-col">
            <span class="font-body-base text-body-base text-on-surface font-medium">{{ pos.name || pos.ticker }}</span>
            <span class="font-body-base text-body-base text-on-surface-variant text-sm">{{ pos.asset_class }} • {{ pos.quantity }} Shares</span>
          </div>
        </div>
        <div class="flex flex-col items-end tabular-nums">
          <span class="font-body-mono text-body-mono text-on-surface">
            ${{ getPositionValue(pos).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}
          </span>
          <span
            v-if="pos.change_percent !== undefined && pos.change_percent !== null"
            :class="[
              'font-body-mono text-body-mono text-xs',
              (pos.change_percent || 0) >= 0 ? 'text-tertiary-container' : 'text-error'
            ]"
          >
            {{ (pos.change_percent || 0) >= 0 ? '+' : '' }}{{ pos.change_percent }}%
          </span>
        </div>
      </div>
    </div>
    <div v-else class="bg-surface-container-lowest border border-dashed border-surface-variant rounded-lg p-md text-center text-sm text-on-surface-variant font-body-base">
      No holdings positions available.
    </div>
  </div>
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
