<template>
  <span
    :class="[
      'inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-md font-sans text-meta font-semibold border whitespace-nowrap',
      colorClasses
    ]"
    data-testid="status-pill"
  >
    <span v-if="icon" class="material-symbols-outlined text-[15px]" aria-hidden="true">{{ icon }}</span>
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
      return 'schedule';
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
      return 'bg-tertiary-fixed text-on-tertiary-fixed border-tertiary-fixed-dim';
    case 'PENDING':
    case 'DRIFTED':
    case 'DRAFTED':
    case 'PROCESSING':
      return 'bg-secondary-fixed text-on-secondary-fixed border-secondary-fixed-dim';
    case 'VIOLATION':
    case 'REJECTED':
    case 'FAILED':
      return 'bg-error-container text-on-error-container border-error/25';
    default:
      return 'bg-surface-container-low text-on-surface-variant border-outline-variant';
  }
});
</script>
