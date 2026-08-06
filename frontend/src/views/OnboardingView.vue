<template>
  <div class="flex flex-col min-h-screen bg-surface text-on-surface" data-testid="onboarding-view">
    <!-- Header with Back Button and Dynamic Step Title -->
    <header class="fixed top-0 w-full z-50 pt-safe bg-surface/80 backdrop-blur-xl shadow-sm border-b border-outline-variant/30">
      <div class="flex items-center h-16 px-margin-mobile md:px-margin-desktop gap-md">
        <button
          class="w-10 h-10 flex items-center justify-center -ml-2 text-on-surface-variant hover:bg-surface-container rounded-full transition-colors"
          data-testid="onboarding-back-btn"
          @click="goBack"
        >
          <span class="material-symbols-outlined">arrow_back</span>
        </button>
        <div class="flex items-center gap-sm">
          <img alt="Logo" class="h-6 w-auto object-contain" src="/images/logo.png" />
          <span class="font-title-sm text-title-sm text-primary tracking-tight" data-testid="step-title">
            {{ stepTitle }}
          </span>
        </div>
      </div>
      <!-- Progress Bar -->
      <div class="h-1 bg-surface-container w-full">
        <div
          class="h-full bg-on-tertiary-container transition-all duration-500"
          :style="{ width: `${progressPercent}%` }"
          data-testid="progress-bar"
        ></div>
      </div>
    </header>

    <!-- Main Wizard Content -->
    <main class="pt-24 pb-16 px-margin-mobile md:px-margin-desktop min-h-screen flex flex-col justify-center">
      <!-- Step 1: Welcome -->
      <WelcomeStep
        v-if="currentStep === 1"
        @next="goToStep(2)"
      />

      <!-- Step 2: Risk Profile & Objectives -->
      <RiskGoalsStep
        v-else-if="currentStep === 2"
        :initial-risk-tolerance="state.risk_tolerance"
        @select="onObjectiveSelected"
      />

      <!-- Step 3: Target Allocation Review -->
      <TargetAllocationStep
        v-else-if="currentStep === 3"
        :initial-allocation="state.target_allocation"
        @confirm="onAllocationConfirmed"
      />

      <!-- Step 4: Statement Upload -->
      <StatementUploadStep
        v-else-if="currentStep === 4"
        @complete="onCompleteOnboarding"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue';
import { useRouter } from 'vue-router';
import type { OnboardingState, RiskToleranceTier, TargetAllocationInput } from '../types';
import WelcomeStep from '../components/onboarding/WelcomeStep.vue';
import RiskGoalsStep from '../components/onboarding/RiskGoalsStep.vue';
import TargetAllocationStep from '../components/onboarding/TargetAllocationStep.vue';
import StatementUploadStep from '../components/onboarding/StatementUploadStep.vue';

const router = useRouter();

const currentStep = ref(1);

const state = reactive<OnboardingState>({
  step: 1,
  objective: 'Balanced Growth & Income',
  time_horizon_years: 10,
  drawdown_reaction: 'hold',
  risk_tolerance: 'moderate',
  target_allocation: {
    equity: 60,
    fixed_income: 30,
    cash: 10
  }
});

const progressPercent = computed(() => {
  switch (currentStep.value) {
    case 1: return 0;
    case 2: return 33;
    case 3: return 66;
    case 4: return 100;
    default: return 0;
  }
});

const stepTitle = computed(() => {
  switch (currentStep.value) {
    case 1: return 'Welcome to Portfolio Copilot';
    case 2: return 'Step 1: Risk & Objectives';
    case 3: return 'Step 2: Target Allocation Review';
    case 4: return 'Step 3: Document Upload';
    default: return 'Onboarding';
  }
});

function goToStep(step: number) {
  currentStep.value = step;
  state.step = step;
}

function goBack() {
  if (currentStep.value > 1) {
    currentStep.value -= 1;
    state.step = currentStep.value;
  } else {
    router.push('/');
  }
}

function onObjectiveSelected(payload: {
  objective: string;
  riskTolerance: RiskToleranceTier;
  allocation: TargetAllocationInput;
}) {
  state.objective = payload.objective;
  state.risk_tolerance = payload.riskTolerance;
  state.target_allocation = payload.allocation;
  goToStep(3);
}

function onAllocationConfirmed(allocation: TargetAllocationInput) {
  state.target_allocation = allocation;
  goToStep(4);
}

function onCompleteOnboarding(file: any) {
  if (file) {
    state.uploaded_file = file;
  }
  router.push('/');
}
</script>
