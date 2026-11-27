<template>
  <button
    :type="type"
    :disabled="disabled"
    :class="[
      'font-sans text-body font-medium px-4 py-2 rounded-md inline-flex items-center justify-center gap-2 transition-[background-color,border-color,color,transform] duration-200 ease-desk active:scale-[0.98]',
      variantClasses,
      disabled ? 'opacity-50 cursor-not-allowed pointer-events-none' : 'cursor-pointer'
    ]"
    data-testid="ui-button"
    @click="!disabled && $emit('click', $event)"
  >
    <span v-if="icon" class="material-symbols-outlined text-[18px]" aria-hidden="true">{{ icon }}</span>
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
      return 'bg-primary text-on-primary hover:bg-primary-container';
    case 'approval':
      return 'bg-tertiary text-on-tertiary hover:bg-on-tertiary-fixed';
    case 'danger':
      return 'bg-surface-container-lowest border border-error text-error hover:bg-error-container/60';
    case 'secondary':
      return 'bg-surface-container-lowest text-on-surface border border-outline-variant hover:bg-surface-container-low';
    default:
      return 'bg-primary text-on-primary';
  }
});
</script>
