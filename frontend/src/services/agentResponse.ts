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

function formatEntry(entry: string): string {
  const m = entry.match(/^([\w-]+)_result:\s*([\s\S]*)$/);
  if (m) {
    const label = prettifyLabel(m[1]);
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
    return output
      .map((item) => {
        if (typeof item === 'string') return formatEntry(item);
        if (item && typeof item === 'object') {
          const narrative = extractNarrative(JSON.stringify(item));
          return narrative || JSON.stringify(item);
        }
        return String(item);
      })
      .filter((line) => line.trim())
      .join('\n\n');
  }

  if (typeof output === 'object') {
    const obj = output as Record<string, unknown>;
    for (const key of NARRATIVE_KEYS) {
      if (typeof obj[key] === 'string' && (obj[key] as string).trim()) {
        return (obj[key] as string).trim();
      }
    }
    return JSON.stringify(output, null, 2);
  }

  return String(output);
}
