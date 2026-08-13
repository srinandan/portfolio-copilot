<template>
  <div class="flex flex-col lg:flex-row gap-lg lg:gap-xl w-full">
    <!-- Left Panel (40%): Agent Activity & Conversational Stream -->
    <div class="flex flex-col gap-md lg:w-[40%] lg:flex-shrink-0">
      <!-- Action / Prompt Trigger -->
      <div class="bg-surface-container-lowest rounded-xl p-sm border border-surface-variant shadow-sm flex flex-col gap-sm">
        <textarea
          v-model="inputPrompt"
          rows="4"
          placeholder="Ask Copilot (e.g. Analyze portfolio drift)..."
          class="w-full px-3 py-2 text-sm rounded bg-surface border border-surface-variant font-body-base text-on-surface focus:outline-none focus:border-primary resize-y min-h-[96px]"
          :disabled="isStreaming"
          @keydown.enter.exact.prevent="triggerPlan(inputPrompt)"
        ></textarea>
        <div class="flex items-center justify-between gap-sm">
          <span class="text-xs text-on-surface-variant hidden sm:block">
            Enter to send · Shift+Enter for a new line
          </span>
          <Button
            variant="primary"
            :disabled="isStreaming"
            data-testid="btn-trigger-plan"
            @click="triggerPlan(inputPrompt)"
          >
            {{ isStreaming ? 'Running...' : 'Run' }}
          </Button>
        </div>

        <!-- Suggestion chips: always available, not just on the empty state -->
        <div class="flex flex-wrap items-center gap-xs pt-xs border-t border-surface-variant">
          <span class="text-xs text-on-surface-variant mr-1">Try:</span>
          <button
            v-for="prompt in examplePrompts"
            :key="prompt"
            type="button"
            class="text-xs font-body-mono px-sm py-1 rounded-full bg-surface-container hover:bg-surface-container-high border border-surface-variant text-on-surface disabled:opacity-50"
            data-testid="example-prompt"
            :disabled="isStreaming"
            @click="triggerPlan(prompt)"
          >
            {{ prompt }}
          </button>
        </div>
      </div>

      <!-- Messages Stream -->
      <div class="flex flex-col gap-sm">
        <!-- Empty state: shown before the user runs anything -->
        <div
          v-if="messages.length === 0"
          class="bg-surface-container-lowest rounded-xl p-lg border border-dashed border-surface-variant text-center flex flex-col items-center gap-sm"
          data-testid="dashboard-empty-state"
        >
          <span class="material-symbols-outlined text-outline text-[28px]">chat</span>
          <p class="font-body-base text-sm text-on-surface-variant">
            Ask Portfolio Copilot something to get started, or pick a suggestion above. Nothing has run yet.
          </p>
        </div>

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
          <!-- Live analysis progress: shown while the run is in flight, then
               cleared and replaced by the final output below. -->
          <AnalysisProgress
            v-if="msg.sender === 'agent' && msg.progressActive && msg.progress && msg.progress.length"
            :stages="msg.progress"
            :started-at="msg.startedAt"
          />
          <p
            v-else
            class="font-body-base text-sm text-on-surface whitespace-pre-wrap"
          >
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
      <NetWorthCard :total-value="holdings.total_value_usd" :as-of="holdings.as_of" />
      <AssetAllocationCard />
      <TopHoldingsTable :positions="holdings.positions" />
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

// Start empty so we don't show a fake demo message. Real events populate this
// on the first triggerPlan call, either from typed input or an example prompt.
const messages = ref<ChatMessage[]>([]);

const examplePrompts = [
  'Analyze my portfolio drift',
  'Check my spending anomalies',
  'Suggest a rebalance'
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
      // Plain text part carrying the JSON payload.
      raw = asHitlRequest(part.text);
      if (raw) break;
      // ADK RequestInput surfaces the approval request as an `adk_request_input`
      // function-call whose args.message holds the JSON payload; the interrupt
      // id is the function-call id. Without this the ApprovalCard never mounts
      // and the raw action+verdict JSON leaks into the chat.
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
    // The rationale occasionally arrives as a JSON-encoded ProposedActionRationale
    // string; show the inner text, not the raw JSON.
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

/**
 * Upsert a live progress stage into a message's stepper, keyed by stage id so
 * repeated events (running -> done, or re-emitted stages on HITL resume) update
 * the same row in place while preserving arrival order.
 */
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
  // Live pipeline progress: update the stepper and stop — never touch text.
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
    // The approval card is the point of interaction now — clear the stepper so
    // the card replaces it.
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

  if (event.output !== undefined && event.output !== null) {
    const formatted = formatAgentResponse(event.output);
    if (formatted) {
      currentMsg.text = formatted;
    }
  } else if (event.content?.parts) {
    const text = event.content.parts.map((p: any) => p.text || '').join('');
    if (text) {
      currentMsg.text = formatAgentResponse(text);
    }
  }
}

async function triggerPlan(promptText?: string) {
  const text = (promptText || 'Analyze my portfolio drift and suggest rebalancing').trim();
  if (!text) return;
  inputPrompt.value = '';

  // Clear previous agent messages/responses for the new interaction
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
  // Drive streaming mutations through the REACTIVE array element, not the raw
  // object. Mutating the raw object bypasses Vue's proxy set-trap, so per-event
  // updates (notably the live progress stepper) would never re-render until some
  // other reactive change forced it. The resume handlers already receive the
  // reactive proxy via the template, which is why they were never affected.
  const agentMsg = messages.value[messages.value.length - 1];

  isStreaming.value = true;
  try {
    // User-action span: the API client span for POST /api/plan nests under this,
    // and the whole trace continues into the Go server and orchestrator.
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
    // Run complete: clear the stepper so the final output replaces it.
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
  } catch (err: any) {
    // If orchestrator is not running or mock test environment, status remains updated
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
  } catch (err: any) {
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
  } catch (err: any) {
    msg.text += `\n[Edit Saved]`;
  } finally {
    isStreaming.value = false;
    msg.progressActive = false;
  }
}
</script>
