<template>
  <div
    class="flex flex-col gap-3 rounded-lg border border-outline-variant bg-surface-container-low/60 p-md"
    data-testid="analysis-progress"
    role="status"
    aria-live="polite"
  >
    <div class="flex items-center justify-between border-b border-outline-variant/70 pb-2">
      <span class="flex items-center gap-2 font-sans text-meta font-semibold text-primary">
        <span class="material-symbols-outlined animate-spin text-[16px] text-primary-fixed" aria-hidden="true">
          progress_activity
        </span>
        Working
      </span>
      <span class="font-sans text-meta text-on-surface-variant tabular-nums" data-testid="analysis-elapsed">
        {{ elapsed }}
      </span>
    </div>

    <ul class="flex flex-col gap-2">
      <li
        v-for="s in stages"
        :key="s.stage"
        class="flex items-start gap-2.5 text-body"
        data-testid="progress-stage"
        :data-stage="s.stage"
        :data-status="s.status"
      >
        <span
          class="material-symbols-outlined text-[18px] leading-6 shrink-0"
          :class="[iconClass(s.status), { 'animate-spin': s.status === 'running' }]"
          aria-hidden="true"
        >{{ icon(s.status) }}</span>
        <span class="flex flex-col">
          <span
            :class="[
              'font-sans text-body',
              s.status === 'running' ? 'text-on-surface font-medium' : 'text-on-surface-variant',
              s.status === 'skipped' ? 'line-through opacity-75' : ''
            ]"
          >{{ s.label }}</span>
          <span v-if="s.detail" class="font-sans text-meta text-on-surface-variant tabular-nums">{{ s.detail }}</span>
        </span>
      </li>
    </ul>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue';
import type { ProgressStage, ProgressStatus } from '../../types';

const props = defineProps<{
  stages: ProgressStage[];
  startedAt?: number;
}>();

const now = ref(Date.now());
let timer: ReturnType<typeof setInterval> | undefined;
onMounted(() => {
  timer = setInterval(() => {
    now.value = Date.now();
  }, 1000);
});
onUnmounted(() => {
  if (timer) clearInterval(timer);
});

const elapsed = computed(() => {
  const start = props.startedAt ?? now.value;
  const secs = Math.max(0, Math.floor((now.value - start) / 1000));
  const m = Math.floor(secs / 60);
  const s = secs % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
});

function icon(status: ProgressStatus): string {
  switch (status) {
    case 'done':
      return 'check_circle';
    case 'skipped':
      return 'do_not_disturb_on';
    case 'failed':
      return 'error';
    case 'pending':
      return 'radio_button_unchecked';
    case 'running':
    default:
      return 'progress_activity';
  }
}

function iconClass(status: ProgressStatus): string {
  switch (status) {
    case 'done':
      return 'text-on-tertiary-container';
    case 'failed':
      return 'text-error';
    case 'pending':
    case 'skipped':
      return 'text-outline';
    case 'running':
    default:
      return 'text-primary-fixed';
  }
}
</script>
