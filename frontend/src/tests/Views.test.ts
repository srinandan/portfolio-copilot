import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/vue';
import DashboardView from '../views/DashboardView.vue';
import PortfolioView from '../views/PortfolioView.vue';
import DocumentsView from '../views/DocumentsView.vue';
import SecurityView from '../views/SecurityView.vue';
import { apiService } from '../services/api';

describe('Frontend Views', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiService, 'getDocuments').mockResolvedValue([
      {
        id: 'doc-1',
        filename: 'Fidelity_Stmt_Oct2023.pdf',
        size_bytes: 1258291,
        uploaded_at: '2023-10-24T09:41:00Z',
        status: 'SUCCESS',
        records_parsed: 42
      }
    ]);
    vi.spyOn(apiService, 'getHoldings').mockResolvedValue({
      total_value_usd: 1248500.0,
      cash_usd: 62400.0,
      as_of: '2023-10-24',
      positions: [
        {
          ticker: 'AAPL',
          name: 'Apple Inc.',
          asset_class: 'Equities (US)',
          quantity: 120,
          current_price_usd: 170.41,
          current_value_usd: 20449.2,
          change_percent: 1.2
        }
      ]
    });
    vi.spyOn(apiService, 'getDriftReport').mockResolvedValue({
      as_of: '2023-10-24',
      has_active_ips: true,
      rebalance_recommended: true,
      unclassified_value_usd: 0.0,
      bands: []
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('DashboardView renders agent activity stream, empty state, and financial canvas', async () => {
    render(DashboardView);
    expect(screen.getByText('Agent Activity Stream')).toBeDefined();
    expect(screen.getByText('Total Net Worth')).toBeDefined();
    expect(screen.getByText('Asset Allocation')).toBeDefined();

    // Before any turn runs, the dashboard shows a real empty state — no fake
    // demo message. The approval card only appears when a real HITL event
    // arrives.
    expect(screen.getByTestId('dashboard-empty-state')).toBeDefined();
    expect(screen.queryByTestId('approval-card')).toBeNull();
    expect(screen.getAllByTestId('example-prompt').length).toBeGreaterThan(0);
  });

  it('DashboardView triggers live plan, streams SSE events, and renders new HITL approval card', async () => {
    const streamPlanSpy = vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'int_live_123',
        invocation_id: 'inv_live_456',
        session_id: 'sess_live_789',
        kind: 'hitl_approval_request',
        action: {
          action_id: 'act_rebal_999',
          session_id: 'sess_live_789',
          type: 'TRADE',
          ticker: 'MSFT',
          side: 'BUY',
          quantity: 20,
          rationale: 'Add MSFT per tech allocation band',
          status: 'DRAFTED'
        },
        reviewer_verdict: {
          verdict_id: 'verd_999',
          action_id: 'act_rebal_999',
          overall_pass: true,
          requires_human_approval: true,
          rule_results: [
            { rule_id: 'rule_target', description: 'Moves closer to IPS target', passed: true }
          ]
        }
      });
    });

    render(DashboardView);
    const input = screen.getByPlaceholderText(/Ask Copilot/i);
    await fireEvent.update(input, 'Rebalance my portfolio now');

    const triggerBtn = screen.getByTestId('btn-trigger-plan');
    await fireEvent.click(triggerBtn);

    expect(streamPlanSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        message: 'Rebalance my portfolio now'
      }),
      expect.any(Function),
      expect.any(Function)
    );

    await waitFor(() => {
      expect(screen.getByText('Action ID: act_rebal_999')).toBeDefined();
      expect(screen.getByText('MSFT')).toBeDefined();
    });
  });

  it('DashboardView keeps suggestion prompts after a turn and renders responses as prose (not raw JSON)', async () => {
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        author: 'portfolio_copilot_planner',
        output: ["spending-analysis_result: {'narrative_summary': 'You saved 40% of income this quarter.'}"]
      });
    });

    render(DashboardView);
    const prompts = screen.getAllByTestId('example-prompt');
    await fireEvent.click(prompts[0]);

    await waitFor(() => {
      // Empty state is gone once a conversation starts...
      expect(screen.queryByTestId('dashboard-empty-state')).toBeNull();
      // ...but the suggestion chips persist so users can keep asking.
      expect(screen.getAllByTestId('example-prompt').length).toBeGreaterThan(0);
      // The agent reply is rendered as prose, not a raw JSON blob.
      expect(screen.getByText(/You saved 40% of income this quarter\./)).toBeDefined();
      expect(screen.queryByText(/narrative_summary/)).toBeNull();
    });
  });

  it('DashboardView renders the ApprovalCard from an ADK adk_request_input function-call event', async () => {
    // The real HITL request arrives as a function-call whose args.message holds
    // the payload — not as event.output/kind. The card must still render.
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'evt_1',
        invocation_id: 'inv_1',
        content: {
          parts: [
            {
              function_call: {
                id: 'int_fc_1',
                name: 'adk_request_input',
                args: {
                  interruptId: 'int_fc_1',
                  message: JSON.stringify({
                    kind: 'hitl_approval_request',
                    action: {
                      action_id: 'act_fc_1',
                      ticker: 'VTI',
                      side: 'sell',
                      quantity: 25,
                      status: 'drafted'
                    },
                    reviewer_verdict: {
                      verdict_id: 'v_fc_1',
                      overall_pass: true,
                      requires_human_approval: true,
                      rule_results: []
                    }
                  })
                }
              }
            }
          ]
        }
      });
    });

    render(DashboardView);
    await fireEvent.click(screen.getAllByTestId('example-prompt')[0]);

    await waitFor(() => {
      expect(screen.getByTestId('approval-card')).toBeDefined();
      expect(screen.getByText('Action ID: act_fc_1')).toBeDefined();
      expect(screen.getByText('VTI')).toBeDefined();
    });
  });

  // Helper: mock streamPlan to synchronously deliver a HITL approval request
  // and then trigger a plan run so the ApprovalCard is on screen.
  const seedApprovalCard = async (rationale = 'Rebalance rationale') => {
    vi.spyOn(apiService, 'streamPlan').mockImplementation(async (_req, onEvent) => {
      onEvent({
        id: 'int_seed_1',
        invocation_id: 'inv_seed_1',
        session_id: 'sess_seed_1',
        kind: 'hitl_approval_request',
        action: {
          action_id: 'act_seed_1',
          session_id: 'sess_seed_1',
          type: 'trade',
          ticker: 'MSFT',
          side: 'buy',
          quantity: 20,
          rationale,
          status: 'drafted'
        },
        reviewer_verdict: {
          verdict_id: 'verd_seed_1',
          action_id: 'act_seed_1',
          overall_pass: true,
          requires_human_approval: true,
          rule_results: []
        }
      });
    });
    render(DashboardView);
    const prompts = screen.getAllByTestId('example-prompt');
    await fireEvent.click(prompts[0]);
    await waitFor(() => {
      expect(screen.getByTestId('approval-card')).toBeDefined();
    });
  };

  it('DashboardView allows approving actions and resumes plan via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard();

    const approveBtn = screen.getByTestId('btn-approve');
    await fireEvent.click(approveBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: { decision: 'approve', user_id: 'demo_user' }
      }),
      expect.any(Function),
      expect.any(Function)
    );

    expect(screen.getByText(/APPROVED — Execution Triggered/i)).toBeDefined();
  });

  it('DashboardView allows rejecting actions and resumes plan via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard();

    const rejectBtn = screen.getByTestId('btn-reject');
    await fireEvent.click(rejectBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: {
          decision: 'reject',
          reason: 'User rejected proposed trade',
          user_id: 'demo_user'
        }
      }),
      expect.any(Function),
      expect.any(Function)
    );

    expect(screen.getByText(/REJECTED — Trade Aborted/i)).toBeDefined();
  });

  it('DashboardView allows editing actions and saves changes via apiService.streamPlanResume', async () => {
    const resumeSpy = vi.spyOn(apiService, 'streamPlanResume').mockResolvedValue();
    await seedApprovalCard('Original rationale');

    const editBtn = screen.getByTestId('btn-edit');
    await fireEvent.click(editBtn);

    const qtyInput = screen.getByTestId('edit-quantity-input');
    await fireEvent.update(qtyInput, '30');

    const saveBtn = screen.getByText('Save Changes');
    await fireEvent.click(saveBtn);

    expect(resumeSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        user_id: 'demo_user',
        payload: {
          decision: 'edit',
          changes: {
            quantity: 30,
            rationale: 'Original rationale'
          },
          user_id: 'demo_user'
        }
      }),
      expect.any(Function),
      expect.any(Function)
    );
  });

  it('PortfolioView renders total value chart and top holdings list', async () => {
    render(PortfolioView);
    expect(screen.getByText('Total Value')).toBeDefined();
    expect(screen.getByText('Portfolio Drift Report')).toBeDefined();
    expect(screen.getByText('Top Holdings')).toBeDefined();

    await waitFor(() => {
      expect(screen.getByText('$1,248,500.00')).toBeDefined();
    });
  });

  it('DocumentsView renders a coming-soon placeholder and links back to the dashboard', () => {
    render(DocumentsView);
    expect(screen.getByTestId('documents-view')).toBeDefined();
    expect(screen.getByText('Statement upload — coming soon')).toBeDefined();
    const backLink = screen.getByTestId('documents-back-to-dashboard') as HTMLAnchorElement;
    expect(backLink.getAttribute('href')).toBe('/');
  });

  it('SecurityView renders privacy intro, 2FA toggle, and export button', async () => {
    const alertSpy = vi.spyOn(window, 'alert').mockImplementation(() => {});
    render(SecurityView);

    expect(screen.getByText('Security Through Privacy')).toBeDefined();
    expect(screen.getByText('Two-Factor Authentication')).toBeDefined();

    const exportBtn = screen.getByText('Export Encrypted Backup');
    await fireEvent.click(exportBtn);
    expect(alertSpy).toHaveBeenCalledWith('Backup export initiated. Check your downloads.');
  });

  it('OnboardingView renders initial step and step title', async () => {
    const OnboardingView = (await import('../views/OnboardingView.vue')).default;
    const { router } = await import('../router');
    render(OnboardingView, {
      global: {
        plugins: [router]
      }
    });

    expect(screen.getAllByText('Welcome to Portfolio Copilot').length).toBeGreaterThan(0);
    expect(screen.getByTestId('step-title').textContent).toContain('Welcome to Portfolio Copilot');
  });
});

