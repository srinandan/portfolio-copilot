<template>
  <div class="flex flex-col min-h-screen bg-surface text-on-surface" data-testid="onboarding-view">
    <!-- Header with Back Button, Step Title, and Progress Bar -->
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
        :has-active-profile="hasActiveProfile"
        :active-version="activeVersion"
        @next="goToStep(2)"
      />

      <!-- Step 2: Goals & Timeline -->
      <GoalsStep
        v-else-if="currentStep === 2"
        :initial-goals="state.goals"
        :initial-horizon-years="state.time_horizon_years"
        :initial-upcoming-expenses="state.known_upcoming_expenses_usd"
        @next="onGoalsConfirmed"
      />

      <!-- Step 3: Liabilities & Debt -->
      <LiabilitiesStep
        v-else-if="currentStep === 3"
        :initial-liabilities="state.liabilities"
        @next="onLiabilitiesConfirmed"
      />

      <!-- Step 4: Risk Calibration -->
      <RiskCalibrationStep
        v-else-if="currentStep === 4"
        :initial-horizon-years="state.time_horizon_years"
        :initial-reaction="state.drawdown_reaction"
        @next="onRiskCalibrationConfirmed"
      />

      <!-- Step 5: Target Allocation & Bands -->
      <TargetAllocationStep
        v-else-if="currentStep === 5"
        :initial-bands="state.target_bands"
        @confirm="onAllocationConfirmed"
      />

      <!-- Step 6: Policy Constraints & Guardrails -->
      <ConstraintsStep
        v-else-if="currentStep === 6"
        :initial-reserve-months="state.reserve_months"
        :initial-constraints="state.constraints"
        :initial-thresholds="state.approval_thresholds"
        @next="onConstraintsConfirmed"
      />

      <!-- Step 7: Final Review & Submission -->
      <SubmissionStep
        v-else-if="currentStep === 7"
        :state="state"
        :is-update="hasActiveProfile"
        @complete="onComplete"
      />
    </main>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue';
import { useRouter } from 'vue-router';
import type {
  OnboardingState,
  Goal,
  LiabilityItem,
  RiskToleranceTier,
  DrawdownReaction,
  AllocationBand,
  IPSConstraints,
  ApprovalThresholds
} from '../types';
import { getDefaultAllocationBands } from '../services/onboarding';
import { apiService } from '../services/api';

import WelcomeStep from '../components/onboarding/WelcomeStep.vue';
import GoalsStep from '../components/onboarding/GoalsStep.vue';
import LiabilitiesStep from '../components/onboarding/LiabilitiesStep.vue';
import RiskCalibrationStep from '../components/onboarding/RiskCalibrationStep.vue';
import TargetAllocationStep from '../components/onboarding/TargetAllocationStep.vue';
import ConstraintsStep from '../components/onboarding/ConstraintsStep.vue';
import SubmissionStep from '../components/onboarding/SubmissionStep.vue';

const router = useRouter();

const currentStep = ref(1);
const hasActiveProfile = ref(false);
const activeVersion = ref(1);

const state = reactive<OnboardingState>({
  step: 1,
  user_id: 'demo_user',
  goals: [
    {
      name: 'Retirement Compounding & Growth',
      target_amount_usd: 1500000,
      target_date: '2039-12-31'
    }
  ],
  time_horizon_years: 15,
  known_upcoming_expenses_usd: 0,
  liabilities: [
    {
      liability_id: 'liab_001',
      type: 'credit_card',
      description: 'Chase Sapphire Reserve',
      balance_usd: 4850,
      interest_rate_percent: 24.99,
      minimum_payment_usd: 150
    }
  ],
  drawdown_reaction: 'hold',
  risk_tolerance: 'aggressive',
  target_bands: getDefaultAllocationBands('aggressive'),
  reserve_months: 6,
  constraints: {
    concentration_limit_percent: 15,
    excluded_tickers: [],
    excluded_sectors: [],
    account_type: 'taxable',
    tax_loss_harvesting_enabled: true
  },
  approval_thresholds: {
    approval_required_above_usd: 1000,
    approval_required_above_percent: 5
  }
});

const progressPercent = computed(() => {
  return Math.round(((currentStep.value - 1) / 6) * 100);
});

const stepTitle = computed(() => {
  switch (currentStep.value) {
    case 1: return 'Welcome to Portfolio Copilot';
    case 2: return 'Turn 1: Goals & Timeline';
    case 3: return 'Turn 2: Liabilities & Debt';
    case 4: return 'Turn 3: Risk Calibration';
    case 5: return 'Turn 4: Target Allocation Bands';
    case 6: return 'Turn 5: Policy Guardrails';
    case 7: return 'Turn 6: Review & Submission';
    default: return 'Goals & Onboarding';
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

function onGoalsConfirmed(payload: {
  goals: Goal[];
  timeHorizonYears: number;
  knownUpcomingExpensesUsd: number;
}) {
  state.goals = payload.goals;
  state.time_horizon_years = payload.timeHorizonYears;
  state.known_upcoming_expenses_usd = payload.knownUpcomingExpensesUsd;
  goToStep(3);
}

function onLiabilitiesConfirmed(liabilities: LiabilityItem[]) {
  state.liabilities = liabilities;
  goToStep(4);
}

function onRiskCalibrationConfirmed(payload: {
  drawdownReaction: DrawdownReaction;
  riskTolerance: RiskToleranceTier;
  defaultBands: AllocationBand[];
}) {
  state.drawdown_reaction = payload.drawdownReaction;
  state.risk_tolerance = payload.riskTolerance;
  state.target_bands = payload.defaultBands;
  goToStep(5);
}

function onAllocationConfirmed(bands: AllocationBand[]) {
  state.target_bands = bands;
  goToStep(6);
}

function onConstraintsConfirmed(payload: {
  reserveMonths: number;
  constraints: IPSConstraints;
  thresholds: ApprovalThresholds;
}) {
  state.reserve_months = payload.reserveMonths;
  state.constraints = payload.constraints;
  state.approval_thresholds = payload.thresholds;
  goToStep(7);
}

function onComplete() {
  router.push('/');
}

onMounted(async () => {
  try {
    const profile = await apiService.getOnboarding(state.user_id);
    if (profile && profile.has_active_ips) {
      hasActiveProfile.value = true;
      if (profile.version) {
        activeVersion.value = profile.version;
      }
      if (profile.goals && profile.goals.length > 0) {
        state.goals = profile.goals;
      }
      if (profile.time_horizon_years) {
        state.time_horizon_years = profile.time_horizon_years;
      }
      if (profile.known_upcoming_expenses_usd !== undefined) {
        state.known_upcoming_expenses_usd = profile.known_upcoming_expenses_usd;
      }
      if (profile.reserve_months !== undefined) {
        state.reserve_months = profile.reserve_months;
      }
      if (profile.risk_tolerance) {
        state.risk_tolerance = profile.risk_tolerance;
      }
      if (profile.target_bands && profile.target_bands.length > 0) {
        state.target_bands = profile.target_bands;
      }
      if (profile.constraints) {
        state.constraints = { ...state.constraints, ...profile.constraints };
      }
      if (profile.approval_required_above_usd !== undefined || profile.approval_required_above_percent !== undefined) {
        state.approval_thresholds = {
          approval_required_above_usd: profile.approval_required_above_usd ?? state.approval_thresholds.approval_required_above_usd,
          approval_required_above_percent: profile.approval_required_above_percent ?? state.approval_thresholds.approval_required_above_percent
        };
      }
      if (profile.liabilities && profile.liabilities.length > 0) {
        state.liabilities = profile.liabilities;
      }
    }
  } catch {
    // Non-blocking: falls back to default onboarding state
  }
});
</script>
