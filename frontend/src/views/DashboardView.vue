<template>
  <div class="flex flex-col gap-lg w-full">
    <h1 class="sr-only">Portfolio Copilot Workspace</h1>

    <div class="grid grid-cols-1 lg:grid-cols-12 gap-lg items-start w-full">
      <!-- Left Desk (5 cols / ~42%): Copilot Command & Governance Stream -->
      <section class="lg:col-span-5 flex flex-col gap-md">
        <div class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet overflow-hidden">
          <!-- Prompt Composer -->
          <div class="p-md flex flex-col gap-3">
            <div class="flex items-baseline justify-between gap-sm">
              <h2 class="font-sans text-heading font-semibold text-on-surface">Copilot desk</h2>
              <span class="font-sans text-meta text-on-surface-variant hidden sm:inline">
                Enter to run
              </span>
            </div>

            <textarea
              v-model="inputPrompt"
              rows="3"
              placeholder="Ask Copilot (e.g. Analyze portfolio drift)..."
              class="w-full px-3.5 py-2.5 text-body rounded-md bg-surface border border-outline-variant font-sans text-on-surface placeholder:text-on-surface-variant/70 resize-y min-h-[88px] transition-colors duration-200 ease-desk focus:border-primary-fixed focus:bg-surface-container-lowest"
              :disabled="isStreaming"
              @keydown.enter.exact.prevent="triggerPlan(inputPrompt)"
            ></textarea>

            <div class="flex items-center justify-between gap-sm">
              <span class="font-sans text-meta text-on-surface-variant hidden sm:inline">
                Shift+Enter for a new line
              </span>
              <Button
                variant="primary"
                class="w-full sm:w-auto sm:ml-auto"
                :disabled="isStreaming"
                data-testid="btn-trigger-plan"
                @click="triggerPlan(inputPrompt)"
              >
                {{ isStreaming ? 'Running...' : 'Run' }}
              </Button>
            </div>
          </div>

          <!-- Suggested Prompts Directory (hairline-divided list, zero pill clutter) -->
          <div class="border-t border-outline-variant bg-surface-container-low/40 px-md py-3">
            <span class="font-sans text-meta font-medium text-on-surface-variant block mb-2">
              Suggested inquiries
            </span>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-1 divide-y divide-outline-variant/60 border-t border-outline-variant/60">
              <button
                v-for="prompt in examplePrompts"
                :key="prompt"
                type="button"
                class="group py-2 px-1 text-left font-sans text-meta text-on-surface hover:text-primary flex items-center justify-between gap-2 transition-colors duration-150 ease-desk disabled:opacity-50"
                data-testid="example-prompt"
                :disabled="isStreaming"
                @click="triggerPlan(prompt)"
              >
                <span class="truncate">{{ prompt }}</span>
                <span
                  class="material-symbols-outlined text-[16px] text-outline group-hover:text-primary group-hover:translate-x-0.5 transition-[color,transform] duration-150 ease-desk shrink-0"
                  aria-hidden="true"
                >
                  arrow_forward
                </span>
              </button>
            </div>
          </div>
        </div>

        <!-- Messages Stream -->
        <div class="flex flex-col gap-3">
          <div
            v-if="messages.length === 0"
            class="bg-surface-container-lowest rounded-xl p-lg border border-dashed border-outline-variant text-center flex flex-col items-center gap-2"
            data-testid="dashboard-empty-state"
          >
            <span class="material-symbols-outlined text-outline text-[24px]" aria-hidden="true">forum</span>
            <p class="font-sans text-body text-on-surface-variant max-w-[44ch]">
              Ask Portfolio Copilot something to get started, or pick a suggestion above. Nothing has run yet.
            </p>
          </div>

          <article
            v-for="msg in messages"
            :key="msg.id"
            :class="[
              'rounded-xl p-md border flex flex-col gap-3',
              msg.sender === 'agent'
                ? 'bg-surface-container-lowest border-outline-variant shadow-sheet'
                : 'bg-surface-container-low/80 border-outline-variant/80'
            ]"
            data-testid="chat-message"
          >
            <div class="flex items-baseline justify-between gap-sm text-meta">
              <span class="font-semibold text-on-surface">
                {{ msg.sender === 'agent' ? 'Portfolio Copilot Agent' : 'User' }}
              </span>
              <span class="text-on-surface-variant tabular-nums">{{ msg.timestamp }}</span>
            </div>

            <AnalysisProgress
              v-if="msg.sender === 'agent' && msg.progressActive && msg.progress && msg.progress.length"
              :stages="msg.progress"
              :started-at="msg.startedAt"
            />
            <p
              v-else
              class="font-sans text-body text-on-surface whitespace-pre-wrap max-w-[65ch]"
            >
              {{ msg.text }}
            </p>

            <ApprovalCard
              v-if="msg.action"
              :action="msg.action"
              :verdict="msg.verdict"
              @approve="onApproveAction(msg)"
              @reject="onRejectAction(msg)"
              @update="onUpdateAction(msg, $event)"
            />
          </article>
        </div>
      </section>

      <!-- Right Canvas (7 cols / ~58%): Financial Ledger -->
      <section class="lg:col-span-7 flex flex-col gap-lg">
        <!-- Unified Balance & Allocation Sheet -->
        <div class="bg-surface-container-lowest rounded-xl border border-outline-variant shadow-sheet divide-y divide-outline-variant">
          <NetWorthCard
            :total-value="holdings.total_value_usd"
            :cash-usd="holdings.cash_usd"
            :as-of="holdings.as_of"
            embedded
          />
          <AssetAllocationCard :holdings="holdings" embedded />
        </div>

        <TopHoldingsTable :positions="holdings.positions" />
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue';
import type { HoldingsSnapshot, ChatMessage, ProposedAction, ReviewerVerdict, ProgressStage } from '../types';
import { apiService } from '../services/api';
import NetWorthCard from '../components/dashboard/NetWorthCard.vue';
import AssetAllocationCard from '../components/dashboard/AssetAllocationCard.vue';
import AnalysisProgress from '../components/dashboard/AnalysisProgress.vue';
import TopHoldingsTable from '../components/portfolio/TopHoldingsTable.vue';
import ApprovalCard from '../components/approval/ApprovalCard.vue';
import Button from '../components/common/Button.vue';
import { formatAgentResponse, unwrapRationale } from '../services/agentResponse';
import { startSpan, runWithSpan } from '../services/tracing';

const holdings = ref<HoldingsSnapshot>({
  total_value_usd: 0,
  cash_usd: 0,
  as_of: '',
  positions: []
});

const inputPrompt = ref('');
const isStreaming = ref(false);
const currentSessionId = ref<string | undefined>(undefined);
const currentUserId = ref('demo_user');

const messages = ref<ChatMessage[]>([]);

const examplePrompts = [
  'Analyze my portfolio drift',
  'Check my spending anomalies',
  'Suggest a rebalance',
  'Should I buy more AAPL?',
  'Is NVDA overvalued?',
  'Should I sell some TSLA?'
];

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

function asHitlRequest(v: any): any {
  if (!v) return null;
  if (typeof v === 'string') {
    try {
      const parsed = JSON.parse(v);
      return parsed?.kind === 'hitl_approval_request' ? parsed : null;
    } catch {
      return null;
    }
  }
  if (typeof v === 'object' && v.kind === 'hitl_approval_request') return v;
  return null;
}

function extractHITLPayload(event: Record<string, any>): {
  action: ProposedAction;
  verdict?: ReviewerVerdict;
  interruptId?: string;
} | null {
  let raw: any = null;
  let interruptId: string | undefined;

  if (event.kind === 'hitl_approval_request') {
    raw = event;
  } else {
    raw = asHitlRequest(event.output);
  }

  if (!raw && event.content?.parts) {
    for (const part of event.content.parts) {
      raw = asHitlRequest(part.text);
      if (raw) break;
      const fc = part.function_call;
      if (fc?.args) {
        raw = asHitlRequest(fc.args.message) || asHitlRequest(fc.args);
        if (raw) {
          interruptId = fc.id || fc.args.interruptId || fc.args.interrupt_id;
          break;
        }
      }
    }
  }

  if (!raw && event.actions?.requested_tool_confirmations) {
    for (const val of Object.values(event.actions.requested_tool_confirmations) as any[]) {
      if (val?.kind === 'hitl_approval_request') {
        raw = val;
        break;
      }
    }
  }

  if (raw && raw.action) {
    const action = { ...raw.action };
    if (action.rationale !== undefined && action.rationale !== null) {
      action.rationale = unwrapRationale(action.rationale);
    }
    return {
      action,
      verdict: raw.reviewer_verdict,
      interruptId
    };
  }
  return null;
}

function upsertProgress(msg: ChatMessage, event: Record<string, any>) {
  const incoming: ProgressStage = {
    stage: String(event.stage ?? ''),
    label: String(event.label ?? event.stage ?? ''),
    status: event.status,
    detail: event.detail
  };
  const existing = msg.progress ? [...msg.progress] : [];
  const idx = existing.findIndex((s) => s.stage === incoming.stage);
  if (idx >= 0) existing[idx] = incoming;
  else existing.push(incoming);
  msg.progress = existing;
  msg.progressActive = true;
  if (!msg.startedAt) msg.startedAt = Date.now();
}

function handleStreamEvent(event: Record<string, any>, currentMsg: ChatMessage) {
  if (event.kind === 'progress' && event.stage) {
    upsertProgress(currentMsg, event);
    return;
  }

  if (event.error || event.error_message) {
    currentMsg.text += `\n[Error]: ${event.error_message || event.error}`;
    return;
  }

  const hitl = extractHITLPayload(event);
  if (hitl) {
    currentMsg.progressActive = false;
    currentMsg.action = hitl.action;
    currentMsg.verdict = hitl.verdict;
    currentMsg.invocation_id = event.invocation_id;
    currentMsg.interrupt_id = hitl.interruptId || event.id;
    if (event.session_id) {
      currentMsg.session_id = event.session_id;
      currentSessionId.value = event.session_id;
    }
    currentMsg.text = `Drafted proposed action ${hitl.action.action_id} for ${hitl.action.side || 'TRADE'} ${hitl.action.ticker || ''}. Review and approve below.`;
    return;
  }

  const isInternalNode =
    event.author === 'get_skills' ||
    event.node_info?.path?.includes('get_skills') ||
    event.author?.includes('get_skills');

  if (!isInternalNode) {
    if (event.output !== undefined && event.output !== null) {
      const formatted = formatAgentResponse(event.output);
      if (formatted) {
        currentMsg.text = formatted;
      }
    } else if (event.content?.parts) {
      const text = event.content.parts.map((p: any) => p.text || '').join('');
      if (text) {
        const formatted = formatAgentResponse(text);
        if (formatted) {
          currentMsg.text = formatted;
        }
      }
    }
  }
}

async function triggerPlan(promptText?: string) {
  const text = (promptText || 'Analyze my portfolio drift and suggest rebalancing').trim();
  if (!text) return;
  inputPrompt.value = '';

  messages.value = [];

  const userMsg: ChatMessage = {
    id: `msg-${Date.now()}-user`,
    sender: 'user',
    text,
    timestamp: formatTime()
  };
  messages.value.push(userMsg);

  const newAgentMsg: ChatMessage = {
    id: `msg-${Date.now()}-agent`,
    sender: 'agent',
    text: 'Analyzing portfolio and discovering authorized skills...',
    timestamp: formatTime(),
    session_id: currentSessionId.value
  };
  messages.value.push(newAgentMsg);
  const agentMsg = messages.value[messages.value.length - 1];

  isStreaming.value = true;
  try {
    await runWithSpan(
      startSpan('planning_turn_triggered', {
        'user.id': currentUserId.value,
        'prompt.length': text.length,
        'session.id': currentSessionId.value || ''
      }),
      () =>
        apiService.streamPlan(
          {
            user_id: currentUserId.value,
            message: text,
            session_id: currentSessionId.value
          },
          (event) => handleStreamEvent(event, agentMsg),
          (err) => {
            agentMsg.text += `\n[Stream Error]: ${err.message || err}`;
          }
        )
    );
  } catch (err: any) {
    agentMsg.text += `\n[Request Failed]: ${err.message || err}`;
  } finally {
    isStreaming.value = false;
    agentMsg.progressActive = false;
  }
}

async function onApproveAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'APPROVED';
  }
  isStreaming.value = true;
  try {
    await runWithSpan(
      startSpan('hitl_decision_submitted', { decision: 'approve', 'action.id': msg.action?.action_id || '' }),
      () =>
        apiService.streamPlanResume(
          {
            user_id: currentUserId.value,
            session_id: msg.session_id || currentSessionId.value || '',
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
        )
    );
  } catch {
    msg.text += `\n[Approval Recorded]`;
  } finally {
    isStreaming.value = false;
    msg.progressActive = false;
  }
}

async function onRejectAction(msg: ChatMessage) {
  if (msg.action) {
    msg.action.status = 'REJECTED';
  }
  isStreaming.value = true;
  try {
    await runWithSpan(
      startSpan('hitl_decision_submitted', { decision: 'reject', 'action.id': msg.action?.action_id || '' }),
      () =>
        apiService.streamPlanResume(
          {
            user_id: currentUserId.value,
            session_id: msg.session_id || currentSessionId.value || '',
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
        )
    );
  } catch {
    msg.text += `\n[Rejection Recorded]`;
  } finally {
    isStreaming.value = false;
    msg.progressActive = false;
  }
}

async function onUpdateAction(msg: ChatMessage, updated: ProposedAction) {
  msg.action = updated;
  isStreaming.value = true;
  try {
    await runWithSpan(
      startSpan('hitl_decision_submitted', { decision: 'edit', 'action.id': msg.action?.action_id || '' }),
      () =>
        apiService.streamPlanResume(
          {
            user_id: currentUserId.value,
            session_id: msg.session_id || currentSessionId.value || '',
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
        )
    );
  } catch {
    msg.text += `\n[Edit Saved]`;
  } finally {
    isStreaming.value = false;
    msg.progressActive = false;
  }
}
</script>
