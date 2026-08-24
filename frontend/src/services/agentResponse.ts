/**
 * Formats a raw agent/planner response into human-readable text for the chat UI.
 *
 * The orchestrator's planner returns its final output as a list of
 * `"<skill>_result: <payload>"` strings, where `<payload>` is a stringified
 * dict. Rendered verbatim that reads as a wall of JSON. This helper turns it
 * into readable prose: it prettifies each skill label and surfaces the
 * human-authored field (narrative_summary / rationale / summary) when present,
 * falling back to a concise "<Skill> complete." line rather than dumping the
 * raw structure.
 */

const SKILL_LABELS: Record<string, string> = {
  'spending-analysis': 'Spending Analysis',
  'portfolio-analysis': 'Portfolio Analysis',
  'goals-onboarding': 'Goals Onboarding',
  research: 'Research',
  'action-drafting': 'Proposed Action',
  reviewer: 'Compliance Review',
  hitl_decision: 'Approval',
  hitl_error: 'Approval Error',
  execution_result: 'Execution',
  execution_error: 'Execution Error',
  error: 'Error',
};

const NARRATIVE_KEYS = ['narrative_summary', 'rationale', 'summary', 'message', 'detail'];

function prettifyLabel(key: string): string {
  const norm = key
    .trim()
    .replace(/_result$/, '')
    .replace(/^private-/, '');
  if (SKILL_LABELS[norm]) return SKILL_LABELS[norm];
  return norm
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

function tryParseJson(value: string): unknown {
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

/**
 * A ProposedAction.rationale sometimes arrives as a JSON-encoded
 * ProposedActionRationale string — e.g. `{"rationale":"…","supporting_research_refs":[]}`
 * — rather than plain text. Unwrap it to the inner rationale for display; plain
 * strings (and non-strings) pass through unchanged.
 */
export function unwrapRationale(value: unknown): string {
  if (typeof value !== 'string') return value == null ? '' : String(value);
  const trimmed = value.trim();
  if (trimmed.startsWith('{')) {
    const parsed = tryParseJson(trimmed) as Record<string, unknown> | null;
    if (parsed && typeof parsed === 'object' && typeof parsed.rationale === 'string') {
      return parsed.rationale;
    }
  }
  return value;
}

/** Best-effort extraction of a human-readable sentence from a payload string. */
function extractNarrative(value: string): string {
  const trimmed = value.trim();
  const parsed = tryParseJson(trimmed);
  if (parsed && typeof parsed === 'object') {
    const obj = parsed as Record<string, unknown>;
    for (const key of NARRATIVE_KEYS) {
      if (typeof obj[key] === 'string' && (obj[key] as string).trim()) {
        return (obj[key] as string).trim();
      }
    }
    if (typeof obj.status === 'string') return `status: ${obj.status}`;
    return '';
  }
  // Fall back to a regex over loose/Python-repr text (e.g. {'narrative_summary': '...'}).
  for (const key of NARRATIVE_KEYS) {
    const re = new RegExp(`['"]?${key}['"]?\\s*:\\s*(['"])([\\s\\S]*?)\\1`);
    const m = trimmed.match(re);
    if (m && m[2].trim()) return m[2].trim();
  }
  return '';
}

function fmtPct(n: unknown): string {
  const v = typeof n === 'number' ? n : Number(n);
  return Number.isFinite(v) ? `${v}%` : String(n ?? '');
}

function prettifyRuleId(id: unknown): string {
  return String(id ?? '')
    .replace(/[-_]/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
    .trim();
}

function isDriftReport(o: any): boolean {
  return !!o && typeof o === 'object' && Array.isArray(o.entries) && 'rebalance_recommended' in o;
}

function formatDriftReport(o: any): string {
  const lines: string[] = [
    o.rebalance_recommended
      ? 'Portfolio drift — rebalancing recommended.'
      : 'Portfolio drift — all asset classes within their target bands.',
  ];
  for (const e of o.entries || []) {
    if (!e || typeof e !== 'object') continue;
    let status: string;
    if (e.in_band) {
      status = 'in band';
    } else if (typeof e.current_percent === 'number' && typeof e.max_percent === 'number' && e.current_percent > e.max_percent) {
      status = `above band (max ${fmtPct(e.max_percent)})`;
    } else {
      status = `below band (min ${fmtPct(e.min_percent)})`;
    }
    lines.push(`• ${e.asset_class}: ${fmtPct(e.current_percent)} vs ${fmtPct(e.target_percent)} target — ${status}`);
  }
  return lines.join('\n');
}

function isReviewerVerdict(o: any): boolean {
  return !!o && typeof o === 'object' && Array.isArray(o.rule_results) && 'overall_pass' in o;
}

function formatReviewerVerdict(o: any): string {
  const rules = Array.isArray(o.rule_results) ? o.rule_results : [];
  const failed = rules.filter((r: any) => r && r.passed === false);
  const lines: string[] = [];
  if (o.overall_pass) {
    lines.push(`Compliance review passed — all ${rules.length} checks OK.`);
  } else {
    lines.push(`Compliance review flagged ${failed.length} of ${rules.length} check(s):`);
    for (const r of failed) {
      lines.push(`• ${prettifyRuleId(r.rule_id)}${r.detail ? `: ${r.detail}` : ''}`);
    }
  }
  if (o.requires_human_approval) lines.push('Your approval is required before this can proceed.');
  return lines.join('\n');
}

function isHitlRequest(o: any): boolean {
  return !!o && typeof o === 'object' && o.kind === 'hitl_approval_request';
}

/** Render a recognized structured domain object as prose; null if unrecognized. */
function formatStructured(o: any): string | null {
  if (isDriftReport(o)) return formatDriftReport(o);
  if (isReviewerVerdict(o)) return formatReviewerVerdict(o);
  if (isHitlRequest(o)) {
    const a = o.action || {};
    const bits = [a.side, a.quantity, a.ticker].filter((x) => x !== undefined && x !== null && x !== '');
    return `Proposed ${bits.join(' ') || 'trade'} — awaiting your approval below.`;
  }
  for (const key of NARRATIVE_KEYS) {
    if (typeof o[key] === 'string' && (o[key] as string).trim()) return (o[key] as string).trim();
  }
  return null;
}

/** Last-resort readable summary of an unknown object — never raw JSON braces. */
function compactSummary(o: any): string {
  try {
    const parts: string[] = [];
    for (const [k, v] of Object.entries(o)) {
      if (v === null || v === undefined) continue;
      if (typeof v === 'object') continue;
      parts.push(`${prettifyRuleId(k)}: ${v}`);
      if (parts.length >= 6) break;
    }
    return parts.join(' · ');
  } catch {
    return '';
  }
}

function formatEntry(entry: string): string {
  const m = entry.match(/^([\w-]+)_result:\s*([\s\S]*)$/);
  if (m) {
    const label = prettifyLabel(m[1]);
    const parsed = tryParseJson(m[2].trim());
    if (parsed && typeof parsed === 'object') {
      const structured = formatStructured(parsed);
      if (structured) {
        // Multi-line structured summaries (drift, verdict) get their own line;
        // single-line narratives stay inline with the label.
        return structured.includes('\n') ? `${label}:\n${structured}` : `${label}: ${structured}`;
      }
    }
    const narrative = extractNarrative(m[2]);
    return narrative ? `${label}: ${narrative}` : `${label} complete.`;
  }
  // Non-skill entries like "error: ...", "hitl_decision: {...}".
  const colon = entry.indexOf(':');
  if (colon > 0) {
    const key = entry.slice(0, colon);
    const val = entry.slice(colon + 1).trim();
    const narrative = extractNarrative(val);
    return narrative ? `${prettifyLabel(key)}: ${narrative}` : entry.trim();
  }
  return entry.trim();
}

function isSkillRegistryObject(o: any): boolean {
  if (!o || typeof o !== 'object') return false;
  return (
    'target_state' in o ||
    'default_revision' in o ||
    'targetState' in o ||
    'defaultRevision' in o ||
    (typeof o.name === 'string' && o.name.includes('/skills/'))
  );
}

/**
 * Turn an arbitrary agent response (string, array of result strings, or object)
 * into readable multi-line text. Never returns a raw `[{...}]` blob.
 */
export function formatAgentResponse(output: unknown): string {
  if (output === null || output === undefined) return '';

  if (typeof output === 'string') {
    const trimmed = output.trim();
    if (trimmed.startsWith('[') || trimmed.startsWith('{')) {
      const parsed = tryParseJson(trimmed);
      if (parsed !== null) return formatAgentResponse(parsed);
    }
    return output;
  }

  if (Array.isArray(output)) {
    // Filter out internal discovery skill lists
    if (output.some(isSkillRegistryObject)) {
      return '';
    }
    return output
      .map((item) => {
        if (typeof item === 'string') return formatEntry(item);
        if (item && typeof item === 'object') {
          if (isSkillRegistryObject(item)) return '';
          return formatStructured(item) || compactSummary(item);
        }
        return String(item);
      })
      .filter((line) => line.trim())
      .join('\n\n');
  }

  if (typeof output === 'object') {
    if (isSkillRegistryObject(output)) return '';
    // Recognized domain objects (DriftReport, ReviewerVerdict, HITL request,
    // or anything carrying a narrative field) render as prose; otherwise fall
    // back to a compact key summary — never a raw JSON blob (issue #272).
    return formatStructured(output) || compactSummary(output) || '';
  }

  return String(output);
}

