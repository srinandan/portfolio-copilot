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
});
