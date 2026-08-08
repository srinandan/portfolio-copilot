<template>
  <div class="flex flex-col lg:flex-row gap-lg lg:gap-xl w-full">
    <!-- Left Panel (40%): Agent Activity & Conversational Stream -->
    <div class="flex flex-col gap-md lg:w-[40%] lg:flex-shrink-0">
      <div class="bg-surface-container-lowest rounded-xl p-md border border-surface-variant shadow-sm flex items-center justify-between">
        <div class="flex items-center gap-sm">
          <span class="material-symbols-outlined text-primary-container">smart_toy</span>
          <h2 class="font-title-sm text-title-sm text-on-surface">Agent Activity Stream</h2>
        </div>
        <div class="flex items-center gap-sm">
          <span class="font-label-caps text-label-caps bg-secondary-container/50 text-on-secondary-container px-2 py-0.5 rounded uppercase">
            Live Governance
          </span>
        </div>
      </div>

      <!-- Action / Prompt Trigger -->
      <div class="bg-surface-container-lowest rounded-xl p-sm border border-surface-variant shadow-sm flex gap-sm">
        <input
          v-model="inputPrompt"
          type="text"
          placeholder="Ask Copilot (e.g. Analyze portfolio drift)..."
          class="flex-1 px-3 py-2 text-sm rounded bg-surface border border-surface-variant font-body-base text-on-surface focus:outline-none focus:border-primary"
          :disabled="isStreaming"
          @keydown.enter="triggerPlan(inputPrompt)"
        />
        <Button
          variant="primary"
          :disabled="isStreaming"
          data-testid="btn-trigger-plan"
          @click="triggerPlan(inputPrompt)"
        >
          {{ isStreaming ? 'Running...' : 'Run' }}
        </Button>
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
          <p class="font-body-base text-sm text-on-surface whitespace-pre-line">
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
import type { HoldingsSnapshot, ChatMessage, ProposedAction, ReviewerVerdict } from '../types';
import { apiService } from '../services/api';
import NetWorthCard from '../components/dashboard/NetWorthCard.vue';
import AssetAllocationCard from '../components/dashboard/AssetAllocationCard.vue';
import TopHoldingsTable from '../components/portfolio/TopHoldingsTable.vue';
import ApprovalCard from '../components/approval/ApprovalCard.vue';
import Button from '../components/common/Button.vue';

const holdings = ref<HoldingsSnapshot>({
  total_value_usd: 1248500,
  cash_usd: 62400,
  as_of: '2023-10-24',
  positions: []
});

const inputPrompt = ref('');
const isStreaming = ref(false);
const currentSessionId = ref('sess_default');
const currentUserId = ref('usr_default');

const messages = ref<ChatMessage[]>([
  {
    id: 'msg-init-1',
    sender: 'agent',
    text: 'Analyzed 3 positions against IPS target allocation. Detected equity drift (+3.2% US equities). Drafted rebalancing proposal for human approval.',
    timestamp: '09:41 AM',
    session_id: 'sess_default',
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

function formatTime(): string {
  const now = new Date();
  return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function extractHITLPayload(event: Record<string, any>): {
  action: ProposedAction;
  verdict?: ReviewerVerdict;
} | null {
  let raw: any = null;

  if (event.kind === 'hitl_approval_request') {
    raw = event;
  } else if (typeof event.output === 'string') {
    try {
      const parsed = JSON.parse(event.output);
      if (parsed?.kind === 'hitl_approval_request') raw = parsed;
    } catch {}
  } else if (event.output && typeof event.output === 'object' && event.output.kind === 'hitl_approval_request') {
    raw = event.output;
  } else if (event.content?.parts) {
    for (const part of event.content.parts) {
      const text = part.text || '';
      try {
        const parsed = JSON.parse(text);
        if (parsed?.kind === 'hitl_approval_request') {
          raw = parsed;
          break;
        }
      } catch {}
    }
  } else if (event.actions?.requested_tool_confirmations) {
    for (const val of Object.values(event.actions.requested_tool_confirmations) as any[]) {
      if (val?.kind === 'hitl_approval_request') {
        raw = val;
        break;
      }
    }
  }

  if (raw && raw.action) {
    return {
      action: raw.action,
      verdict: raw.reviewer_verdict
    };
  }
  return null;
}

function handleStreamEvent(event: Record<string, any>, currentMsg: ChatMessage) {
  if (event.error || event.error_message) {
    currentMsg.text += `\n[Error]: ${event.error_message || event.error}`;
    return;
  }

  const hitl = extractHITLPayload(event);
  if (hitl) {
    currentMsg.action = hitl.action;
    currentMsg.verdict = hitl.verdict;
    currentMsg.invocation_id = event.invocation_id;
    currentMsg.interrupt_id = event.id;
    if (event.session_id) {
      currentMsg.session_id = event.session_id;
      currentSessionId.value = event.session_id;
    }
    currentMsg.text = `Drafted proposed action ${hitl.action.action_id} for ${hitl.action.side || 'TRADE'} ${hitl.action.ticker || ''}. Review and approve below.`;
    return;
  }

  if (event.author && event.output && typeof event.output === 'string') {
    currentMsg.text = event.output;
  } else if (event.content?.parts) {
    const text = event.content.parts.map((p: any) => p.text || '').join('');
    if (text) {
      currentMsg.text = text;
    }
  }
}

async function triggerPlan(promptText?: string) {
  const text = (promptText || 'Analyze my portfolio drift and suggest rebalancing').trim();
  if (!text) return;
  inputPrompt.value = '';

  const userMsg: ChatMessage = {
    id: `msg-${Date.now()}-user`,
    sender: 'user',
    text,
    timestamp: formatTime()
  };
  messages.value.push(userMsg);

  const agentMsg: ChatMessage = {
    id: `msg-${Date.now()}-agent`,
    sender: 'agent',
    text: 'Analyzing portfolio and discovering authorized skills...',
    timestamp: formatTime(),
    session_id: currentSessionId.value
  };
  messages.value.push(agentMsg);

  isStreaming.value = true;
  try {
    await apiService.streamPlan(
      {
        user_id: currentUserId.value,
        message: text,
        session_id: currentSessionId.value
      },
      (event) => handleStreamEvent(event, agentMsg),
      (err) => {
        agentMsg.text += `\n[Stream Error]: ${err.message || err}`;
      }
    );
  } catch (err: any) {
    agentMsg.text += `\n[Request Failed]: ${err.message || err}`;
  } finally {
    isStreaming.value = false;
  }
}

async function onApproveAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'APPROVED';
  }
  isStreaming.value = true;
  try {
    await apiService.streamPlanResume(
      {
        user_id: currentUserId.value,
        session_id: msg.session_id || currentSessionId.value,
        invocation_id: msg.invocation_id || '',
        interrupt_id: msg.interrupt_id || '',
        payload: {
          decision: 'approve',
          user_id: currentUserId.value
        }
      },
      (event) => handleStreamEvent(event, msg),
      (err) => {
        msg.text += `\n[Resume Error]: ${err.message || err}`;
      }
    );
  } catch (err: any) {
    // If orchestrator is not running or mock test environment, status remains updated
    msg.text += `\n[Approval Recorded]`;
  } finally {
    isStreaming.value = false;
  }
}

async function onRejectAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'REJECTED';
  }
  isStreaming.value = true;
  try {
    await apiService.streamPlanResume(
      {
        user_id: currentUserId.value,
        session_id: msg.session_id || currentSessionId.value,
        invocation_id: msg.invocation_id || '',
        interrupt_id: msg.interrupt_id || '',
        payload: {
          decision: 'reject',
          reason: 'User rejected proposed trade',
          user_id: currentUserId.value
        }
      },
      (event) => handleStreamEvent(event, msg),
      (err) => {
        msg.text += `\n[Resume Error]: ${err.message || err}`;
      }
    );
  } catch (err: any) {
    msg.text += `\n[Rejection Recorded]`;
  } finally {
    isStreaming.value = false;
  }
}

async function onUpdateAction(msg: ChatMessage, updated: ProposedAction) {
  msg.action = updated;
  isStreaming.value = true;
  try {
    await apiService.streamPlanResume(
      {
        user_id: currentUserId.value,
        session_id: msg.session_id || currentSessionId.value,
        invocation_id: msg.invocation_id || '',
        interrupt_id: msg.interrupt_id || '',
        payload: {
          decision: 'edit',
          changes: {
            quantity: updated.quantity,
            rationale: updated.rationale
          },
          user_id: currentUserId.value
        }
      },
      (event) => handleStreamEvent(event, msg),
      (err) => {
        msg.text += `\n[Resume Error]: ${err.message || err}`;
      }
    );
  } catch (err: any) {
    msg.text += `\n[Edit Saved]`;
  } finally {
    isStreaming.value = false;
  }
}
</script>
