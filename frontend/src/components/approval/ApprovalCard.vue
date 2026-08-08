<template>
  <div class="bg-surface-container-lowest rounded-xl p-lg shadow-sm border border-surface-variant flex flex-col gap-md" data-testid="approval-card">
    <!-- Header -->
    <div class="flex items-center justify-between border-b border-surface-variant pb-2">
      <div class="flex items-center gap-sm">
        <span class="material-symbols-outlined text-outline">verified</span>
        <span class="font-body-mono text-xs text-on-surface-variant uppercase tracking-wider">Action ID: {{ action.action_id }}</span>
      </div>
      <StatusPill :status="currentStatusBadge" />
    </div>

    <!-- Body: Structured Grid -->
    <div v-if="!isEditing" class="grid grid-cols-3 gap-md bg-surface-container-low p-md rounded-lg tabular-nums">
      <div>
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase block mb-1">Ticker</span>
        <span class="font-body-mono text-body-mono text-on-surface font-bold">{{ action.ticker || 'N/A' }}</span>
      </div>
      <div>
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase block mb-1">Side</span>
        <span
          :class="[
            'font-body-mono text-body-mono font-bold uppercase',
            (action.side || '').toLowerCase() === 'buy' ? 'text-tertiary-container' : 'text-error'
          ]"
        >
          {{ action.side || 'buy' }}
        </span>
      </div>
      <div>
        <span class="font-label-caps text-label-caps text-on-surface-variant uppercase block mb-1">Quantity</span>
        <span class="font-body-mono text-body-mono text-on-surface">{{ action.quantity || 0 }}</span>
      </div>
    </div>

    <!-- Edit Form State -->
    <div v-else class="flex flex-col gap-sm bg-surface-container-low p-md rounded-lg" data-testid="edit-form">
      <div>
        <label class="font-label-caps text-label-caps text-on-surface-variant uppercase block mb-1">Quantity</label>
        <input
          v-model.number="editQuantity"
          type="number"
          class="w-full p-2 rounded bg-surface border border-surface-variant font-body-mono text-sm"
          data-testid="edit-quantity-input"
        />
      </div>
      <div>
        <label class="font-label-caps text-label-caps text-on-surface-variant uppercase block mb-1">Rationale</label>
        <textarea
          v-model="editRationale"
          class="w-full p-2 rounded bg-surface border border-surface-variant font-body-base text-sm"
          data-testid="edit-rationale-input"
        ></textarea>
      </div>
      <div class="flex items-center gap-sm mt-2">
        <Button variant="primary" @click="saveEdit">Save Changes</Button>
        <Button variant="secondary" @click="cancelEdit">Cancel</Button>
      </div>
    </div>

    <!-- Rationale -->
    <p class="font-body-base text-body-base text-on-surface-variant text-sm italic">
      "{{ action.rationale }}"
    </p>

    <!-- Verdict Section: Policy Rules Checklist -->
    <div v-if="verdict && verdict.rule_results && verdict.rule_results.length > 0" class="flex flex-col gap-xs border-t border-surface-variant pt-2">
      <span class="font-label-caps text-label-caps text-on-surface-variant uppercase">Policy Safety Checklist</span>
      <div
        v-for="rule in verdict.rule_results"
        :key="rule.rule_id"
        class="flex items-center justify-between py-1 border-b border-outline/10 last:border-0"
        data-testid="rule-item"
      >
        <span class="font-body-base text-xs text-on-surface">{{ rule.description }}</span>
        <StatusPill :status="rule.passed ? 'PASS' : 'VIOLATION'" :label="rule.passed ? 'PASS' : 'FAIL'" />
      </div>
    </div>

    <!-- Footer Buttons: Approve / Edit / Reject (conditional on status) -->
    <div v-if="isPending" class="flex items-center justify-end gap-sm pt-2" data-testid="action-buttons">
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
        'p-sm rounded-lg flex items-center justify-between font-body-mono text-xs font-semibold',
        isApproved
          ? 'bg-tertiary-fixed/20 text-on-tertiary-fixed'
          : 'bg-error-container/20 text-on-error-container'
      ]"
      data-testid="completed-banner"
    >
      <span>Status: {{ isApproved ? 'APPROVED — Execution Triggered' : 'REJECTED — Trade Aborted' }}</span>
      <span class="material-symbols-outlined text-[16px]">{{ isApproved ? 'done_all' : 'block' }}</span>
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
