import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, fireEvent, screen, cleanup } from '@testing-library/vue';
import WelcomeStep from '../components/onboarding/WelcomeStep.vue';
import RiskGoalsStep from '../components/onboarding/RiskGoalsStep.vue';
import TargetAllocationStep from '../components/onboarding/TargetAllocationStep.vue';
import StatementUploadStep from '../components/onboarding/StatementUploadStep.vue';
import OnboardingView from '../views/OnboardingView.vue';

const mockPush = vi.fn();
vi.mock('vue-router', () => ({
  useRouter: () => ({
    push: mockPush
  })
}));

describe('Onboarding Components', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  describe('WelcomeStep.vue', () => {
    it('renders welcome hero, value props, and emits next on CTA click', async () => {
      const { emitted } = render(WelcomeStep);

      expect(screen.getByText('Welcome to Portfolio Copilot')).toBeDefined();
      expect(screen.getByText('Security through Privacy')).toBeDefined();
      expect(screen.getByText('No Bank Logins')).toBeDefined();

      const startBtn = screen.getByTestId('start-setup-btn');
      await fireEvent.click(startBtn);

      expect(emitted().next).toBeTruthy();
    });
  });

  describe('RiskGoalsStep.vue', () => {
    it('renders objective options and telemetry preview', async () => {
      const { emitted } = render(RiskGoalsStep);

      expect(screen.getByText('Aggressive Capital Appreciation')).toBeDefined();
      expect(screen.getByText('Balanced Growth & Income')).toBeDefined();
      expect(screen.getByText('Capital Preservation')).toBeDefined();

      // Click Aggressive
      const aggressiveOpt = screen.getByTestId('objective-opt-aggressive');
      await fireEvent.click(aggressiveOpt);

      // Confirm
      const confirmBtn = screen.getByTestId('confirm-objective-btn');
      await fireEvent.click(confirmBtn);

      expect(emitted().select).toBeTruthy();
      const payload = (emitted().select as any)[0][0];
      expect(payload.riskTolerance).toBe('aggressive');
      expect(payload.allocation.equity).toBe(85);
      expect(payload.allocation.fixed_income).toBe(10);
      expect(payload.allocation.cash).toBe(5);
    });
  });

  describe('TargetAllocationStep.vue', () => {
    it('renders projected return, risk score, and allows slider overrides', async () => {
      const { emitted } = render(TargetAllocationStep, {
        props: {
          initialAllocation: { equity: 60, fixed_income: 30, cash: 10 }
        }
      });

      expect(screen.getByTestId('projected-return').textContent).toContain('6.1%');
      expect(screen.getByTestId('risk-score').textContent).toBe('Moderate');
      expect(screen.getByTestId('total-percent-display').textContent).toBe('100%');

      // Change equity to 70 (total becomes 110%)
      const inputEquity = screen.getByTestId('input-equity');
      await fireEvent.update(inputEquity, '70');

      // Check warning toast and disabled button
      expect(screen.getByTestId('allocation-warning').textContent).toContain('Total allocation must equal 100%. Currently: 110%');
      const confirmBtn = screen.getByTestId('confirm-allocation-btn') as HTMLButtonElement;
      expect(confirmBtn.disabled).toBe(true);

      // Balance it out: reduce fixed income to 20% (total becomes 100%)
      const inputFixed = screen.getByTestId('input-fixed');
      await fireEvent.update(inputFixed, '20');

      expect(screen.queryByTestId('allocation-warning')).toBeNull();
      expect(confirmBtn.disabled).toBe(false);

      await fireEvent.click(confirmBtn);
      expect(emitted().confirm).toBeTruthy();
      expect((emitted().confirm as any)[0][0]).toEqual({
        equity: 70,
        fixed_income: 20,
        cash: 10
      });
    });
  });

  describe('StatementUploadStep.vue', () => {
    it('handles file selection, displays parsed rows, and allows removal', async () => {
      const { emitted } = render(StatementUploadStep);

      const dropzone = screen.getByTestId('onboarding-dropzone');
      expect(dropzone).toBeDefined();

      const fileInput = screen.getByTestId('onboarding-file-input');
      const file = new File(['ticker,shares\nAAPL,10'], 'statement.csv', { type: 'text/csv' });

      await fireEvent.change(fileInput, {
        target: { files: [file] }
      });

      expect(screen.getByTestId('uploaded-file-card')).toBeDefined();
      expect(screen.getByTestId('file-name').textContent).toContain('statement.csv');

      const beginBtn = screen.getByTestId('begin-analysis-btn');
      await fireEvent.click(beginBtn);

      expect(emitted().complete).toBeTruthy();

      // Remove file
      const removeBtn = screen.getByTestId('remove-file-btn');
      await fireEvent.click(removeBtn);

      expect(screen.getByTestId('onboarding-dropzone')).toBeDefined();
    });

    it('handles drag and drop file upload', async () => {
      render(StatementUploadStep);

      const dropzone = screen.getByTestId('onboarding-dropzone');
      const file = new File(['content'], 'brokerage.pdf', { type: 'application/pdf' });

      await fireEvent.dragOver(dropzone);
      await fireEvent.drop(dropzone, {
        dataTransfer: { files: [file] }
      });

      expect(screen.getByTestId('uploaded-file-card')).toBeDefined();
      expect(screen.getByTestId('file-name').textContent).toContain('brokerage.pdf');
    });
  });

  describe('OnboardingView.vue (Full Wizard)', () => {
    it('navigates turn-by-turn through all 4 steps and completes setup', async () => {
      render(OnboardingView);

      // Step 1: Welcome
      expect(screen.getByTestId('step-title').textContent).toContain('Welcome to Portfolio Copilot');
      expect(screen.getByTestId('welcome-step')).toBeDefined();
      expect(screen.getByTestId('progress-bar').getAttribute('style')).toContain('width: 0%');

      await fireEvent.click(screen.getByTestId('start-setup-btn'));

      // Step 2: Risk & Objectives
      expect(screen.getByTestId('step-title').textContent).toContain('Step 1: Risk & Objectives');
      expect(screen.getByTestId('risk-goals-step')).toBeDefined();
      expect(screen.getByTestId('progress-bar').getAttribute('style')).toContain('width: 33%');

      await fireEvent.click(screen.getByTestId('objective-opt-aggressive'));
      await fireEvent.click(screen.getByTestId('confirm-objective-btn'));

      // Step 3: Target Allocation Review
      expect(screen.getByTestId('step-title').textContent).toContain('Step 2: Target Allocation Review');
      expect(screen.getByTestId('target-allocation-step')).toBeDefined();
      expect(screen.getByTestId('progress-bar').getAttribute('style')).toContain('width: 66%');

      await fireEvent.click(screen.getByTestId('confirm-allocation-btn'));

      // Step 4: Statement Upload
      expect(screen.getByTestId('step-title').textContent).toContain('Step 3: Document Upload');
      expect(screen.getByTestId('statement-upload-step')).toBeDefined();
      expect(screen.getByTestId('progress-bar').getAttribute('style')).toContain('width: 100%');

      // Upload file and complete
      const file = new File(['data'], 'schwab_jan2026.pdf', { type: 'application/pdf' });
      await fireEvent.change(screen.getByTestId('onboarding-file-input'), {
        target: { files: [file] }
      });

      await fireEvent.click(screen.getByTestId('begin-analysis-btn'));
      expect(mockPush).toHaveBeenCalledWith('/');
    });

    it('navigates backwards when clicking the back button', async () => {
      render(OnboardingView);

      // Advance to step 2
      await fireEvent.click(screen.getByTestId('start-setup-btn'));
      expect(screen.getByTestId('risk-goals-step')).toBeDefined();

      // Click back -> returns to step 1
      await fireEvent.click(screen.getByTestId('onboarding-back-btn'));
      expect(screen.getByTestId('welcome-step')).toBeDefined();

      // Click back on step 1 -> redirects to /
      await fireEvent.click(screen.getByTestId('onboarding-back-btn'));
      expect(mockPush).toHaveBeenCalledWith('/');
    });
  });
});
