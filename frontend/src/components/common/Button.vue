<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="[
      'font-body-mono text-body-mono px-4 py-2.5 rounded-lg flex items-center justify-center gap-sm transition-transform active:scale-95 shadow-sm font-semibold',
      variantClasses,
      disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : 'cursor-pointer'
    ]"
    data-testid="ui-button"
    @click="!disabled && $emit('click', $event)"
  >
    <span v-if="icon" class="material-symbols-outlined text-[18px]">{{ icon }}</span>
    <slot></slot>
  </button>
</template>

<script setup lang="ts">
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    variant?: 'primary' | 'approval' | 'danger' | 'secondary';
    type?: 'button' | 'submit' | 'reset';
    disabled?: boolean;
    icon?: string;
  }>(),
  {
    variant: 'primary',
    type: 'button',
    disabled: false
  }
);

defineEmits<{
  (e: 'click', event: MouseEvent): void;
}>();

const variantClasses = computed(() => {
  switch (props.variant) {
    case 'primary':
      return 'bg-primary text-on-primary hover:opacity-90';
    case 'approval':
      return 'bg-tertiary-fixed text-on-tertiary-fixed hover:bg-tertiary-fixed-dim';
    case 'danger':
      return 'border border-error text-error hover:bg-error-container/20';
    case 'secondary':
      return 'bg-surface-container text-on-surface hover:bg-surface-container-high border border-outline/20';
    default:
      return 'bg-primary text-on-primary';
  }
});
</script>
