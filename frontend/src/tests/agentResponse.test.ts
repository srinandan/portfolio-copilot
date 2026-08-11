import { describe, it, expect } from 'vitest';
import { formatAgentResponse } from '../services/agentResponse';

describe('formatAgentResponse', () => {
  it('returns plain strings unchanged', () => {
    expect(formatAgentResponse('Hello there')).toBe('Hello there');
  });

  it('extracts narratives from Python-repr planner result strings', () => {
    const out = [
      "spending-analysis_result: {'user_id': 'u1', 'narrative_summary': 'You saved 40% of income this quarter.'}",
      "portfolio-analysis_result: {'rebalance_recommended': True, 'summary': 'Equities are 8% over target.'}",
    ];
    const text = formatAgentResponse(out);
    expect(text).toContain('Spending Analysis: You saved 40% of income this quarter.');
    expect(text).toContain('Portfolio Analysis: Equities are 8% over target.');
    // No raw structure leaks through.
    expect(text).not.toContain('{');
    expect(text).not.toContain('user_id');
  });

  it('handles valid JSON payloads', () => {
    const out = ['action-drafting_result: {"rationale": "Trim AAPL by 5 shares."}'];
    expect(formatAgentResponse(out)).toBe('Proposed Action: Trim AAPL by 5 shares.');
  });

  it('falls back to a concise line when no narrative is present', () => {
    const out = ["reviewer_result: {'overall_pass': True}"];
    expect(formatAgentResponse(out)).toBe('Compliance Review complete.');
  });

  it('preserves error entries', () => {
    const out = ['error: No authorized Portfolio Copilot skills found.'];
    expect(formatAgentResponse(out)).toContain('No authorized Portfolio Copilot skills found.');
  });

  it('handles narratives containing apostrophes (double-quoted repr value)', () => {
    const out = ['spending-analysis_result: {\'narrative_summary\': "You\'re saving more than last month."}'];
    expect(formatAgentResponse(out)).toBe("Spending Analysis: You're saving more than last month.");
  });

  it('formats an object with a narrative field', () => {
    expect(formatAgentResponse({ narrative_summary: 'All good.' })).toBe('All good.');
  });

  it('returns empty string for null/undefined', () => {
    expect(formatAgentResponse(null)).toBe('');
    expect(formatAgentResponse(undefined)).toBe('');
  });

  it('parses a JSON-string array output', () => {
    const s = JSON.stringify(['research_result: {"summary": "Rates steady."}']);
    expect(formatAgentResponse(s)).toBe('Research: Rates steady.');
  });

  it('renders a DriftReport (no narrative field) as prose, not JSON', () => {
    const drift = {
      entries: [
        { asset_class: 'Equity', current_percent: 67.5, target_percent: 60.0, min_percent: 50.0, max_percent: 65.0, in_band: false, drift_amount_percent: 2.5 },
        { asset_class: 'Bonds', current_percent: 17.5, target_percent: 30.0, min_percent: 25.0, max_percent: 35.0, in_band: false, drift_amount_percent: 7.5 },
        { asset_class: 'Cash', current_percent: 10.0, target_percent: 10.0, min_percent: 5.0, max_percent: 15.0, in_band: true, drift_amount_percent: 0.0 },
      ],
      unclassified_value_usd: 10000.0,
      rebalance_recommended: true,
    };
    const text = formatAgentResponse(drift);
    expect(text).toContain('rebalancing recommended');
    expect(text).toContain('Equity: 67.5% vs 60% target — above band (max 65%)');
    expect(text).toContain('Bonds: 17.5% vs 30% target — below band (min 25%)');
    expect(text).toContain('Cash: 10% vs 10% target — in band');
    expect(text).not.toContain('{');
    expect(text).not.toContain('unclassified_value_usd');
  });

  it('renders a failing ReviewerVerdict as a readable summary', () => {
    const verdict = {
      overall_pass: false,
      requires_human_approval: true,
      rule_results: [
        { rule_id: 'excluded_ticker', passed: true, detail: null },
        { rule_id: 'concentration_limit', passed: false, detail: 'Resulting VTI position is 47.5% (limit 15%).' },
        { rule_id: 'ips_version_current', passed: true, detail: null },
      ],
    };
    const text = formatAgentResponse(verdict);
    expect(text).toContain('flagged 1 of 3');
    expect(text).toContain('Concentration Limit: Resulting VTI position is 47.5% (limit 15%).');
    expect(text).toContain('approval is required');
    expect(text).not.toContain('{');
  });

  it('renders a passing ReviewerVerdict concisely', () => {
    const verdict = { overall_pass: true, requires_human_approval: false, rule_results: [{ rule_id: 'a', passed: true }, { rule_id: 'b', passed: true }] };
    expect(formatAgentResponse(verdict)).toContain('all 2 checks OK');
  });

  it('summarizes a HITL approval request object', () => {
    const req = { kind: 'hitl_approval_request', action: { side: 'sell', quantity: 25, ticker: 'VTI' } };
    expect(formatAgentResponse(req)).toContain('awaiting your approval');
  });

  it('never dumps raw JSON for an unknown object', () => {
    const text = formatAgentResponse({ foo: 'bar', count: 3, nested: { a: 1 } });
    expect(text).not.toContain('{');
    expect(text).toContain('Foo: bar');
    expect(text).toContain('Count: 3');
  });
});
