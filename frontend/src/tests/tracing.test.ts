import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import {
  newTraceId,
  newSpanId,
  traceparentFor,
  startSpan,
  runWithSpan,
  traceRequest,
  recordUserAction,
  getActiveSpan,
  flush,
  initTracing,
  _resetTracingForTest
} from '../services/tracing';

describe('tracing', () => {
  beforeEach(() => {
    _resetTracingForTest();
  });
  afterEach(() => {
    _resetTracingForTest();
    vi.restoreAllMocks();
  });

  it('generates W3C-shaped ids and traceparent', () => {
    expect(newTraceId()).toMatch(/^[0-9a-f]{32}$/);
    expect(newSpanId()).toMatch(/^[0-9a-f]{16}$/);
    const span = startSpan('x');
    expect(traceparentFor(span.data)).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
  });

  it('starts a new trace when no span is active', () => {
    const a = startSpan('a');
    const b = startSpan('b');
    expect(a.data.parentSpanId).toBe('');
    expect(b.data.parentSpanId).toBe('');
    expect(a.data.traceId).not.toBe(b.data.traceId);
  });

  it('nests child spans under the active span within runWithSpan', async () => {
    let childTraceId = '';
    let childParent = '';
    const parent = startSpan('planning_turn_triggered');
    await runWithSpan(parent, async () => {
      expect(getActiveSpan()?.spanId).toBe(parent.data.spanId);
      const child = startSpan('child');
      childTraceId = child.data.traceId;
      childParent = child.data.parentSpanId;
      child.end();
    });
    // Same trace, parented to the user-action span.
    expect(childTraceId).toBe(parent.data.traceId);
    expect(childParent).toBe(parent.data.spanId);
    // Active span restored (ended) after the block.
    expect(getActiveSpan()).toBeNull();
  });

  it('traceRequest injects a traceparent header for a child client span', () => {
    const parent = startSpan('planning_turn_triggered');
    let headers: Record<string, string> = {};
    let spanTraceId = '';
    // Run inside the active span so the request span is a child.
    void runWithSpan(parent, () => {
      const r = traceRequest('POST /api/plan', { 'Content-Type': 'application/json' });
      headers = r.headers;
      spanTraceId = r.span.data.traceId;
      expect(r.span.data.kind).toBe('client');
      r.span.end();
    });
    expect(headers['Content-Type']).toBe('application/json');
    expect(headers.traceparent).toMatch(/^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/);
    expect(headers.traceparent).toContain(spanTraceId);
    expect(spanTraceId).toBe(parent.data.traceId);
  });

  it('exports ended spans to the telemetry sink on flush', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, status: 202 });
    vi.stubGlobal('fetch', fetchMock);

    recordUserAction('planning_turn_triggered', { 'user.id': 'demo_user' });
    flush();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe('/api/telemetry/v1/traces');
    expect(init.method).toBe('POST');
    const body = JSON.parse(init.body);
    expect(Array.isArray(body.spans)).toBe(true);
    expect(body.spans[0].name).toBe('planning_turn_triggered');
    expect(body.spans[0].endTimeUnixMs).toBeGreaterThan(0);
    // Buffer drained after flush.
    flush();
    expect(fetchMock).toHaveBeenCalledTimes(1);
  });

  it('flush is a no-op with no spans and never throws', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    expect(() => flush()).not.toThrow();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it('initTracing is idempotent', () => {
    expect(() => {
      initTracing();
      initTracing();
    }).not.toThrow();
  });
});
