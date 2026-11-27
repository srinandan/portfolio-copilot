<template>
  <div
    class="bg-surface-container-lowest rounded-lg border border-outline-variant border-l-4 border-l-primary p-md flex flex-col gap-md"
    data-testid="approval-card"
  >
    <!-- Header -->
    <div class="flex items-center justify-between gap-sm border-b border-outline-variant/80 pb-3 flex-wrap">
      <div class="flex items-center gap-2 min-w-0">
        <span class="material-symbols-outlined text-[18px] text-primary" aria-hidden="true">verified_user</span>
        <span class="font-sans text-meta font-medium text-on-surface-variant tabular-nums truncate">
          Action ID: {{ action.action_id }}
        </span>
      </div>
      <StatusPill :status="currentStatusBadge" />
    </div>

    <!-- Trade Ticket Grid -->
    <div
      v-if="!isEditing"
      class="grid grid-cols-3 divide-x divide-outline-variant rounded-md border border-outline-variant/80 bg-surface-container-low/50 tabular-nums"
    >
      <div class="p-3">
        <span class="font-sans text-meta text-on-surface-variant block">Ticker</span>
        <span class="font-sans text-body font-semibold text-on-surface">{{ action.ticker || 'N/A' }}</span>
      </div>
      <div class="p-3">
        <span class="font-sans text-meta text-on-surface-variant block">Side</span>
        <span
          :class="[
            'font-sans text-body font-semibold uppercase',
            (action.side || '').toLowerCase() === 'buy' ? 'text-on-tertiary-container' : 'text-error'
          ]"
        >
          {{ action.side || 'buy' }}
        </span>
      </div>
      <div class="p-3">
        <span class="font-sans text-meta text-on-surface-variant block">Quantity</span>
        <span class="font-sans text-body font-semibold text-on-surface">{{ action.quantity || 0 }}</span>
      </div>
    </div>

    <!-- Edit Form State -->
    <div v-else class="flex flex-col gap-3 bg-surface-container-low/60 p-md rounded-md border border-outline-variant/80" data-testid="edit-form">
      <div class="flex flex-col gap-1">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Quantity</label>
        <input
          v-model.number="editQuantity"
          type="number"
          class="w-full px-3 py-2 rounded-md bg-surface-container-lowest border border-outline-variant font-sans text-body text-on-surface tabular-nums"
          data-testid="edit-quantity-input"
        />
      </div>
      <div class="flex flex-col gap-1">
        <label class="font-sans text-meta font-medium text-on-surface-variant">Rationale</label>
        <textarea
          v-model="editRationale"
          rows="3"
          class="w-full px-3 py-2 rounded-md bg-surface-container-lowest border border-outline-variant font-sans text-body text-on-surface"
          data-testid="edit-rationale-input"
        ></textarea>
      </div>
      <div class="flex items-center gap-2 pt-1">
        <Button variant="primary" @click="saveEdit">Save Changes</Button>
        <Button variant="secondary" @click="cancelEdit">Cancel</Button>
      </div>
    </div>

    <!-- Rationale -->
    <p class="font-sans text-body text-on-surface-variant max-w-[65ch]">
      {{ action.rationale }}
    </p>

    <!-- Policy Safety Checklist -->
    <div
      v-if="verdict && verdict.rule_results && verdict.rule_results.length > 0"
      class="flex flex-col gap-2 border-t border-outline-variant/80 pt-3"
    >
      <span class="font-sans text-meta font-semibold text-on-surface">Policy safety checklist</span>
      <div class="divide-y divide-outline-variant/60">
        <div
          v-for="rule in verdict.rule_results"
          :key="rule.rule_id"
          class="flex items-center justify-between gap-md py-2 first:pt-1 last:pb-0"
          data-testid="rule-item"
        >
          <span class="font-sans text-meta text-on-surface">{{ rule.description }}</span>
          <StatusPill :status="rule.passed ? 'PASS' : 'VIOLATION'" :label="rule.passed ? 'PASS' : 'FAIL'" />
        </div>
      </div>
    </div>

    <!-- Footer Actions -->
    <div v-if="isPending" class="flex flex-wrap items-center justify-end gap-2 pt-3 border-t border-outline-variant/80" data-testid="action-buttons">
      <Button variant="secondary" icon="edit" data-testid="btn-edit" @click="startEdit">
        Edit
      </Button>
      <Button variant="danger" icon="close" data-testid="btn-reject" @click="onReject">
        Reject
      </Button>
      <Button variant="approval" icon="check" data-testid="btn-approve" @click="onApprove">
        Approve Trade
      </Button>
    </div>

    <!-- Completed State Banner -->
    <div
      v-else
      :class="[
        'px-3 py-2.5 rounded-md border flex items-center justify-between font-sans text-meta font-semibold',
        isApproved
          ? 'bg-tertiary-fixed/60 border-tertiary-fixed-dim text-on-tertiary-fixed'
          : 'bg-error-container/70 border-error/25 text-on-error-container'
      ]"
      data-testid="completed-banner"
    >
      <span>Status: {{ isApproved ? 'APPROVED: Execution Triggered' : 'REJECTED: Trade Aborted' }}</span>
      <span class="material-symbols-outlined text-[18px]" aria-hidden="true">
        {{ isApproved ? 'done_all' : 'block' }}
      </span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { ProposedAction, ReviewerVerdict } from '../../types';
import StatusPill from '../common/StatusPill.vue';
import Button from '../common/Button.vue';

const props = defineProps<{
  action: ProposedAction;
  verdict?: ReviewerVerdict;
}>();

const emit = defineEmits<{
  (e: 'approve', action: ProposedAction): void;
  (e: 'reject', action: ProposedAction): void;
  (e: 'update', action: ProposedAction): void;
}>();

const isEditing = ref(false);
const editQuantity = ref(props.action.quantity || 0);
const editRationale = ref(props.action.rationale || '');

const isPending = computed(() => {
  const s = (props.action.status || '').toLowerCase();
  return (
    s === 'drafted' ||
    s === 'pending' ||
    s === 'pending_approval' ||
    s === 'reviewed_pass'
  );
});

const isApproved = computed(() => {
  const s = (props.action.status || '').toLowerCase();
  return s === 'approved' || s === 'executed';
});

const currentStatusBadge = computed(() => {
  const s = (props.action.status || '').toLowerCase();
  if (s === 'approved' || s === 'executed') return 'APPROVED';
  if (s === 'rejected' || s === 'reviewed_fail' || s === 'failed') return 'REJECTED';
  return 'PENDING';
});

function startEdit() {
  editQuantity.value = props.action.quantity || 0;
  editRationale.value = props.action.rationale || '';
  isEditing.value = true;
}

function saveEdit() {
  isEditing.value = false;
  const updatedAction: ProposedAction = {
    ...props.action,
    quantity: editQuantity.value,
    rationale: editRationale.value
  };
  emit('update', updatedAction);
}

function cancelEdit() {
  isEditing.value = false;
}

function onApprove() {
  emit('approve', { ...props.action, status: 'approved' });
}

function onReject() {
  emit('reject', { ...props.action, status: 'rejected' });
}
</script>
