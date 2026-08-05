<template>
  <span
    :class="[
      'inline-flex items-center gap-xs px-2.5 py-1 rounded-full font-label-caps text-label-caps uppercase tracking-wider font-bold',
      colorClasses
    ]"
    data-testid="status-pill"
  >
    <span v-if="icon" class="material-symbols-outlined text-[14px]" aria-hidden="true">{{ icon }}</span>
    <slot>{{ label || status }}</slot>
  </span>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    status: 'PASS' | 'APPROVED' | 'SUCCESS' | 'PENDING' | 'DRIFTED' | 'DRAFTED' | 'VIOLATION' | 'REJECTED' | 'FAILED' | 'PROCESSING';
    label?: string;
    showIcon?: boolean;
  }>(),
  {
    showIcon: true
  }
);

const icon = computed(() => {
  if (!props.showIcon) return null;
  switch (props.status) {
    case 'PASS':
    case 'APPROVED':
    case 'SUCCESS':
      return 'check_circle';
    case 'PENDING':
    case 'DRIFTED':
    case 'DRAFTED':
    case 'PROCESSING':
      return 'pending';
    case 'VIOLATION':
    case 'REJECTED':
    case 'FAILED':
      return 'error';
    default:
      return null;
  }
});

const colorClasses = computed(() => {
  switch (props.status) {
    case 'PASS':
    case 'APPROVED':
    case 'SUCCESS':
      return 'bg-tertiary-fixed text-on-tertiary-fixed';
    case 'PENDING':
    case 'DRIFTED':
    case 'DRAFTED':
    case 'PROCESSING':
      return 'bg-secondary-fixed text-on-secondary-fixed';
    case 'VIOLATION':
    case 'REJECTED':
    case 'FAILED':
      return 'bg-error-container text-on-error-container';
    default:
      return 'bg-surface-variant text-on-surface-variant';
  }
});
</script>
