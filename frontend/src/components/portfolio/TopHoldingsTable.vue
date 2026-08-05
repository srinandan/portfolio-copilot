<template>
  <div class="flex flex-col gap-md">
    <h3 class="font-title-sm text-title-sm text-on-background">Top Holdings</h3>
    <div class="flex flex-col gap-xs">
      <div
        v-for="pos in positions"
        :key="pos.ticker"
        class="bg-surface-container-lowest border border-surface-variant rounded-lg p-md flex items-center justify-between shadow-sm hover:bg-surface-container-low transition-colors cursor-pointer group"
        data-testid="holding-row"
      >
        <div class="flex items-center gap-md">
          <div class="w-10 h-10 rounded-full bg-primary-fixed/20 flex items-center justify-center text-primary font-body-mono text-body-mono font-bold group-hover:scale-105 transition-transform">
            {{ pos.ticker }}
          </div>
          <div class="flex flex-col">
            <span class="font-body-base text-body-base text-on-surface font-medium">{{ pos.name }}</span>
            <span class="font-body-base text-body-base text-on-surface-variant text-sm">{{ pos.asset_class }} • {{ pos.quantity }} Shares</span>
          </div>
        </div>
        <div class="flex flex-col items-end tabular-nums">
          <span class="font-body-mono text-body-mono text-on-surface">${{ pos.current_value_usd.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) }}</span>
          <span
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
  </div>
</template>

<script setup lang="ts">
import type { Position } from '../../types';

withDefaults(
  defineProps<{
    positions?: Position[];
  }>(),
  {
    positions: () => [
      {
        ticker: 'AAPL',
        name: 'Apple Inc.',
        asset_class: 'Equities (US)',
        quantity: 120,
        current_price_usd: 170.41,
        current_value_usd: 20450.0,
        change_percent: 1.2
      },
      {
        ticker: 'VOO',
        name: 'Vanguard S&P 500 ETF',
        asset_class: 'Equities (US)',
        quantity: 45,
        current_price_usd: 404.45,
        current_value_usd: 18200.5,
        change_percent: 0.8
      },
      {
        ticker: 'MSFT',
        name: 'Microsoft Corp.',
        asset_class: 'Equities (US)',
        quantity: 50,
        current_price_usd: 410.0,
        current_value_usd: 20500.0,
        change_percent: -0.4
      }
    ]
  }
);
</script>
