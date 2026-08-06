<template>
  <div class="flex flex-col lg:flex-row gap-lg lg:gap-xl w-full">
    <!-- Left Panel (40%): Agent Activity & Conversational Stream -->
    <div class="flex flex-col gap-md lg:w-[40%] lg:flex-shrink-0">
      <div class="bg-surface-container-lowest rounded-xl p-md border border-surface-variant shadow-sm flex items-center justify-between">
        <div class="flex items-center gap-sm">
          <span class="material-symbols-outlined text-primary-container">smart_toy</span>
          <h2 class="font-title-sm text-title-sm text-on-surface">Agent Activity Stream</h2>
        </div>
        <span class="font-label-caps text-label-caps bg-secondary-container/50 text-on-secondary-container px-2 py-0.5 rounded uppercase">
          Live Governance
        </span>
      </div>

      <!-- Messages Stream -->
      <div class="flex flex-col gap-sm">
        <div
          v-for="msg in messages"
          :key="msg.id"
          class="bg-surface-container-lowest rounded-xl p-md border border-surface-variant shadow-sm flex flex-col gap-sm"
          data-testid="chat-message"
        >
          <div class="flex items-center justify-between text-xs text-on-surface-variant">
            <span class="font-bold text-on-surface">{{ msg.sender === 'agent' ? 'Portfolio Copilot Agent' : 'User' }}</span>
            <span class="font-body-mono">{{ msg.timestamp }}</span>
          </div>
          <p class="font-body-base text-sm text-on-surface">
            {{ msg.text }}
          </p>

          <!-- Render Approval Card if action is attached -->
          <ApprovalCard
            v-if="msg.action"
            :action="msg.action"
            :verdict="msg.verdict"
            @approve="onApproveAction(msg)"
            @reject="onRejectAction(msg)"
            @update="onUpdateAction(msg, $event)"
          />
        </div>
      </div>
    </div>

    <!-- Right Panel (60%): Financial Canvas -->
    <div class="flex flex-col gap-lg flex-1">
      <NetWorthCard :total-value="holdings.total_value_usd" />
      <AssetAllocationCard />
      <TopHoldingsTable :positions="holdings.positions" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { HoldingsSnapshot, ChatMessage, ProposedAction } from '../types';
import { apiService } from '../services/api';
import NetWorthCard from '../components/dashboard/NetWorthCard.vue';
import AssetAllocationCard from '../components/dashboard/AssetAllocationCard.vue';
import TopHoldingsTable from '../components/portfolio/TopHoldingsTable.vue';
import ApprovalCard from '../components/approval/ApprovalCard.vue';

const holdings = ref<HoldingsSnapshot>({
  total_value_usd: 1248500,
  cash_usd: 62400,
  as_of: '2023-10-24',
  positions: []
});

const messages = ref<ChatMessage[]>([
  {
    id: 'msg-1',
    sender: 'agent',
    text: 'Analyzed 3 positions against IPS target allocation. Detected equity drift (+3.2% US equities). Drafted rebalancing proposal for human approval.',
    timestamp: '09:41 AM',
    action: {
      action_id: 'act_rebal_001',
      session_id: 'sess_default',
      type: 'TRADE',
      ticker: 'AAPL',
      side: 'SELL',
      quantity: 15,
      estimated_price_usd: 170.41,
      estimated_value_usd: 2556.15,
      rationale: 'Trim AAPL position to rebalance US Equities within 55% IPS target allocation.',
      status: 'DRAFTED'
    },
    verdict: {
      verdict_id: 'verd_001',
      action_id: 'act_rebal_001',
      overall_pass: true,
      requires_human_approval: true,
      rule_results: [
        {
          rule_id: 'rule_ips_target',
          description: 'Trade moves asset allocation closer to IPS target',
          passed: true
        },
        {
          rule_id: 'rule_max_single_trade',
          description: 'Single trade value under 5% portfolio threshold',
          passed: true
        }
      ]
    }
  }
]);

onMounted(async () => {
  try {
    const data = await apiService.getHoldings();
    holdings.value = data;
  } catch {
    // Fallback initialized above
  }
});

function onApproveAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'APPROVED';
  }
}

function onRejectAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'REJECTED';
  }
}

function onUpdateAction(msg: ChatMessage, updated: ProposedAction) {
  msg.action = updated;
}
</script>
