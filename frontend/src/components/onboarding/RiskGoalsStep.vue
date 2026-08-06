<template>
  <div class="flex flex-col lg:flex-row gap-gutter w-full max-w-7xl mx-auto" data-testid="risk-goals-step">
    <!-- Left Panel: Conversational Stream (40%) -->
    <div class="w-full lg:w-[40%] flex flex-col gap-md">
      <!-- Trust Header -->
      <div class="flex items-center gap-sm mb-sm mt-xs opacity-80">
        <span class="material-symbols-outlined text-[16px] text-tertiary-fixed-dim" style="font-variation-settings: 'FILL' 1;">
          shield_lock
        </span>
        <span class="font-body-mono text-label-caps text-on-surface-variant tracking-wider uppercase">
          End-to-End Encrypted Session
        </span>
      </div>

      <!-- Agent Message -->
      <div class="bg-surface-container rounded-xl rounded-tl-sm p-lg relative group shadow-sm border border-outline-variant">
        <div class="absolute -left-[1px] top-lg bottom-lg w-[3px] bg-secondary-fixed rounded-r-full"></div>
        <div class="flex items-center gap-3 mb-md">
          <div class="w-8 h-8 rounded-full bg-primary-container flex items-center justify-center border border-outline-variant">
            <span class="material-symbols-outlined text-[16px] text-on-primary" style="font-variation-settings: 'FILL' 1;">
              smart_toy
            </span>
          </div>
          <div>
            <div class="font-title-sm text-body-base text-on-surface">Portfolio Copilot</div>
            <div class="font-body-mono text-[10px] text-on-surface-variant uppercase tracking-widest">System Agent</div>
          </div>
        </div>
        <p class="font-body-base text-on-surface-variant leading-relaxed mb-md">
          To calibrate your portfolio architecture, I need to establish your baseline objectives. Let's define the primary vector for your capital allocation.
        </p>
        <p class="font-body-base text-on-surface font-semibold">
          What is the primary objective for this portfolio segment?
        </p>
      </div>

      <!-- Objective Choice Cards -->
      <div class="flex flex-col gap-sm mt-sm">
        <button
          v-for="opt in options"
          :key="opt.id"
          type="button"
          class="w-full text-left group bg-surface-container-lowest rounded-lg p-md border transition-all duration-200 shadow-sm"
          :class="[
            selectedId === opt.id
              ? 'border-primary ring-2 ring-primary/20 bg-surface-container-low'
              : 'border-outline-variant hover:border-primary/50'
          ]"
          :data-testid="`objective-opt-${opt.id}`"
          @click="selectOption(opt)"
        >
          <div class="flex items-start gap-md">
            <div
              class="mt-1 w-5 h-5 rounded-full border-2 flex items-center justify-center transition-colors"
              :class="selectedId === opt.id ? 'border-primary' : 'border-outline group-hover:border-primary/50'"
            >
              <div
                class="w-2.5 h-2.5 rounded-full bg-primary transition-transform"
                :class="selectedId === opt.id ? 'scale-100' : 'scale-0'"
              ></div>
            </div>
            <div>
              <div class="font-title-sm text-body-base text-on-surface group-hover:text-primary transition-colors">
                {{ opt.title }}
              </div>
              <div class="font-body-base text-[13px] text-on-surface-variant mt-1">
                {{ opt.description }}
              </div>
            </div>
          </div>
        </button>
      </div>

      <!-- Action Area -->
      <div class="mt-lg flex items-center justify-between">
        <div class="font-body-mono text-[11px] text-on-surface-variant uppercase tracking-widest flex items-center gap-2">
          <div class="w-2 h-2 rounded-full bg-tertiary-fixed-dim animate-pulse"></div>
          Awaiting Input
        </div>
        <button
          class="bg-primary-container text-on-primary font-title-sm text-body-base px-xl py-3 rounded-md shadow-sm hover:bg-primary-container/90 transition-colors flex items-center gap-2"
          data-testid="confirm-objective-btn"
          @click="confirmSelection"
        >
          <span>Confirm Selection</span>
          <span class="material-symbols-outlined text-[18px]">arrow_forward</span>
        </button>
      </div>
    </div>

    <!-- Right Panel: Financial Canvas (60%) -->
    <div class="hidden lg:flex w-[60%] flex-col gap-lg sticky top-24">
      <div class="w-full max-w-md mx-auto my-auto">
        <div class="mb-lg">
          <h3 class="font-title-sm text-headline-md text-on-surface mb-2">Profile Construction</h3>
          <p class="font-body-base text-on-surface-variant">Real-time parameters based on your input.</p>
        </div>

        <!-- Telemetry Preview Card -->
        <div class="bg-surface-container-lowest rounded-xl p-lg border border-outline-variant shadow-sm backdrop-blur-md">
          <div class="flex items-center justify-between border-b border-outline-variant pb-sm mb-md">
            <span class="font-body-mono text-[11px] text-on-surface-variant tracking-widest uppercase">Target Allocation</span>
            <span
              class="font-body-mono text-[11px] tracking-widest uppercase"
              :class="selectedOption ? 'text-on-tertiary-container font-semibold' : 'text-on-surface-variant'"
            >
              {{ selectedOption ? 'MODEL GENERATED' : 'CALCULATING...' }}
            </span>
          </div>

          <div class="space-y-4" :class="{ 'opacity-50 grayscale': !selectedOption }">
            <!-- Equities Bar -->
            <div>
              <div class="flex justify-between font-body-mono text-[12px] text-on-surface mb-1">
                <span>Equities (Growth)</span>
                <span class="font-bold">{{ currentAllocation.equity }}%</span>
              </div>
              <div class="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div
                  class="h-full bg-primary-container transition-all duration-500"
                  :style="{ width: `${currentAllocation.equity}%` }"
                ></div>
              </div>
            </div>

            <!-- Fixed Income Bar -->
            <div>
              <div class="flex justify-between font-body-mono text-[12px] text-on-surface mb-1">
                <span>Fixed Income (Yield)</span>
                <span class="font-bold">{{ currentAllocation.fixed_income }}%</span>
              </div>
              <div class="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div
                  class="h-full bg-secondary-fixed transition-all duration-500"
                  :style="{ width: `${currentAllocation.fixed_income}%` }"
                ></div>
              </div>
            </div>

            <!-- Cash Bar -->
            <div>
              <div class="flex justify-between font-body-mono text-[12px] text-on-surface mb-1">
                <span>Cash & Reserves</span>
                <span class="font-bold">{{ currentAllocation.cash }}%</span>
              </div>
              <div class="h-1.5 w-full bg-surface-container rounded-full overflow-hidden">
                <div
                  class="h-full bg-surface-tint transition-all duration-500"
                  :style="{ width: `${currentAllocation.cash}%` }"
                ></div>
              </div>
            </div>
          </div>

          <div class="mt-lg pt-md border-t border-outline-variant flex items-start gap-3">
            <span class="material-symbols-outlined text-[20px] text-on-surface-variant">info</span>
            <p class="font-body-base text-[12px] text-on-surface-variant leading-snug">
              Your selection dynamically structures the baseline allocation model. We utilize standard institutional risk parity frameworks to balance these vectors.
            </p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue';
import type { RiskToleranceTier, TargetAllocationInput } from '../../types';

interface ObjectiveOption {
  id: string;
  title: string;
  description: string;
  riskTolerance: RiskToleranceTier;
  allocation: TargetAllocationInput;
}

const props = defineProps<{
  initialRiskTolerance?: RiskToleranceTier;
}>();

const emit = defineEmits<{
  (e: 'select', payload: {
    objective: string;
    riskTolerance: RiskToleranceTier;
    allocation: TargetAllocationInput;
  }): void;
}>();

const options: ObjectiveOption[] = [
  {
    id: 'aggressive',
    title: 'Aggressive Capital Appreciation',
    description: 'Maximum growth orientation. Higher volatility tolerance.',
    riskTolerance: 'aggressive',
    allocation: { equity: 85, fixed_income: 10, cash: 5 }
  },
  {
    id: 'moderate',
    title: 'Balanced Growth & Income',
    description: 'Moderate risk profile targeting steady compounding.',
    riskTolerance: 'moderate',
    allocation: { equity: 60, fixed_income: 30, cash: 10 }
  },
  {
    id: 'conservative',
    title: 'Capital Preservation',
    description: 'Minimal downside risk. Focus on yield generation.',
    riskTolerance: 'conservative',
    allocation: { equity: 30, fixed_income: 60, cash: 10 }
  }
];

const selectedId = ref<string>(props.initialRiskTolerance || 'moderate');

const selectedOption = computed(() => options.find(o => o.id === selectedId.value) || options[1]);

const currentAllocation = computed<TargetAllocationInput>(() => {
  return selectedOption.value ? selectedOption.value.allocation : { equity: 0, fixed_income: 0, cash: 0 };
});

function selectOption(opt: ObjectiveOption) {
  selectedId.value = opt.id;
}

function confirmSelection() {
  const opt = selectedOption.value;
  emit('select', {
    objective: opt.title,
    riskTolerance: opt.riskTolerance,
    allocation: { ...opt.allocation }
  });
}
</script>
