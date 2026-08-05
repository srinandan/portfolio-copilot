import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/vue';
import ApprovalCard from '../components/approval/ApprovalCard.vue';
import type { ProposedAction, ReviewerVerdict } from '../types';

const mockAction: ProposedAction = {
  action_id: 'act_test_001',
  session_id: 'sess_1',
  type: 'TRADE',
  ticker: 'AAPL',
  side: 'BUY',
  quantity: 10,
  rationale: 'Rebalancing US equities per IPS target',
  status: 'DRAFTED'
};

const mockVerdict: ReviewerVerdict = {
  verdict_id: 'verd_1',
  action_id: 'act_test_001',
  overall_pass: true,
  requires_human_approval: true,
  rule_results: [
    {
      rule_id: 'rule_1',
      description: 'Within IPS target range',
      passed: true
    }
  ]
};

describe('ApprovalCard.vue', () => {
  afterEach(() => {
    cleanup();
  });

  it('renders pending trade details and policy rules checklist', () => {
    render(ApprovalCard, {
      props: { action: mockAction, verdict: mockVerdict }
    });
    expect(screen.getByText('Action ID: act_test_001')).toBeDefined();
    expect(screen.getByText('AAPL')).toBeDefined();
    expect(screen.getByText('BUY')).toBeDefined();
    expect(screen.getByText('10')).toBeDefined();
    expect(screen.getByText('Within IPS target range')).toBeDefined();
    expect(screen.getByTestId('action-buttons')).toBeDefined();
  });

  it('emits approve event when Approve Trade button is clicked', async () => {
    const { emitted } = render(ApprovalCard, {
      props: { action: mockAction, verdict: mockVerdict }
    });
    const approveBtn = screen.getByTestId('btn-approve');
    await fireEvent.click(approveBtn);
    expect(emitted().approve).toHaveLength(1);
    expect(emitted().approve[0]).toEqual([
      { ...mockAction, status: 'APPROVED' }
    ]);
  });

  it('emits reject event when Reject button is clicked', async () => {
    const { emitted } = render(ApprovalCard, {
      props: { action: mockAction, verdict: mockVerdict }
    });
    const rejectBtn = screen.getByTestId('btn-reject');
    await fireEvent.click(rejectBtn);
    expect(emitted().reject).toHaveLength(1);
    expect(emitted().reject[0]).toEqual([
      { ...mockAction, status: 'REJECTED' }
    ]);
  });

  it('enters edit mode, allows updating quantity and rationale, and emits update', async () => {
    const { emitted } = render(ApprovalCard, {
      props: { action: mockAction, verdict: mockVerdict }
    });

    const editBtn = screen.getByTestId('btn-edit');
    await fireEvent.click(editBtn);

    expect(screen.getByTestId('edit-form')).toBeDefined();
    const qtyInput = screen.getByTestId('edit-quantity-input') as HTMLInputElement;
    const rationaleInput = screen.getByTestId('edit-rationale-input') as HTMLTextAreaElement;

    await fireEvent.update(qtyInput, '25');
    await fireEvent.update(rationaleInput, 'Updated rationale');

    const saveBtn = screen.getByText('Save Changes');
    await fireEvent.click(saveBtn);

    const updates = emitted().update as unknown[][];
    expect(updates).toHaveLength(1);
    expect(updates[0][0]).toEqual({
      ...mockAction,
      quantity: 25,
      rationale: 'Updated rationale'
    });
  });

  it('cancels edit mode without emitting update', async () => {
    const { emitted } = render(ApprovalCard, {
      props: { action: mockAction, verdict: mockVerdict }
    });

    await fireEvent.click(screen.getByTestId('btn-edit'));
    expect(screen.getByTestId('edit-form')).toBeDefined();

    const cancelBtn = screen.getByText('Cancel');
    await fireEvent.click(cancelBtn);

    expect(screen.queryByTestId('edit-form')).toBeNull();
    expect(emitted().update).toBeUndefined();
  });

  it('renders approved completed state banner and hides action buttons', () => {
    const approvedAction: ProposedAction = {
      ...mockAction,
      status: 'APPROVED'
    };
    render(ApprovalCard, {
      props: { action: approvedAction, verdict: mockVerdict }
    });

    const banner = screen.getByTestId('completed-banner');
    expect(banner.textContent).toContain('APPROVED — Execution Triggered');
    expect(screen.queryByTestId('action-buttons')).toBeNull();
  });

  it('renders rejected completed state banner and hides action buttons', () => {
    const rejectedAction: ProposedAction = {
      ...mockAction,
      status: 'REJECTED'
    };
    render(ApprovalCard, {
      props: { action: rejectedAction, verdict: mockVerdict }
    });

    const banner = screen.getByTestId('completed-banner');
    expect(banner.textContent).toContain('REJECTED — Trade Aborted');
    expect(screen.queryByTestId('action-buttons')).toBeNull();
  });
});
