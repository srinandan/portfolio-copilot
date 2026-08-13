/**
 * Lightweight, dependency-free distributed tracing for the SPA.
 *
 * It generates W3C Trace Context (`traceparent`) so a browser-originated trace
 * continues through the Go server (otelgin extracts it) and into the Python
 * orchestrator under a single Trace ID, and it records client/user-action spans
 * which are batched to the Go telemetry sink (`/api/telemetry/v1/traces`) where
 * they are correlated with the server/agent spans in Cloud Trace.
 *
 * Why not `@opentelemetry/sdk-trace-web`? Two reasons specific to this app:
 *  1. `@opentelemetry/instrumentation-fetch` patches the global `fetch`, which
 *     wraps the streaming Response body and can interfere with the SSE reader
 *     the dashboard relies on (see readSSEStream). Manual, header-only injection
 *     leaves the stream untouched.
 *  2. The web SDK + instrumentations add substantial bundle weight and are
 *     awkward under jsdom in unit tests, for no gain over W3C + OTLP-JSON here.
 * See ADR-0019.
 */

const TRACES_ENDPOINT = '/api/telemetry/v1/traces';
const FLUSH_INTERVAL_MS = 5000;
const MAX_BUFFER = 100;

export type SpanKind = 'internal' | 'client' | 'server' | 'producer' | 'consumer';

export interface SpanData {
  traceId: string;
  spanId: string;
  parentSpanId: string;
  name: string;
  kind: SpanKind;
  startTimeUnixMs: number;
  endTimeUnixMs: number;
  attributes: Record<string, unknown>;
}

function randomHex(bytes: number): string {
  const buf = new Uint8Array(bytes);
  const c = (globalThis as { crypto?: Crypto }).crypto;
  if (c && typeof c.getRandomValues === 'function') {
    c.getRandomValues(buf);
  } else {
    for (let i = 0; i < bytes; i++) buf[i] = Math.floor(Math.random() * 256);
  }
  return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('');
}

/** 16-byte (32 hex) W3C trace id. */
export const newTraceId = (): string => randomHex(16);
/** 8-byte (16 hex) W3C span id. */
export const newSpanId = (): string => randomHex(8);

/** Formats a span into a W3C `traceparent` header value (sampled). */
export function traceparentFor(span: SpanData): string {
  return `00-${span.traceId}-${span.spanId}-01`;
}

const buffer: SpanData[] = [];
let activeSpan: SpanData | null = null;
let flushTimer: ReturnType<typeof setInterval> | undefined;
let started = false;

export class Span {
  readonly data: SpanData;
  private ended = false;

  constructor(data: SpanData) {
    this.data = data;
  }

  setAttribute(key: string, value: unknown): this {
    this.data.attributes[key] = value;
    return this;
  }

  traceparent(): string {
    return traceparentFor(this.data);
  }

  end(): void {
    if (this.ended) return;
    this.ended = true;
    this.data.endTimeUnixMs = now();
    enqueue(this.data);
  }
}

function now(): number {
  return typeof performance !== 'undefined' && performance.timeOrigin
    ? performance.timeOrigin + performance.now()
    : Date.now();
}

/**
 * Starts a span. When a span is active (see runWithSpan / setActiveSpan) the new
 * span joins the active trace as its child; otherwise it starts a new trace.
 */
export function startSpan(
  name: string,
  attributes: Record<string, unknown> = {},
  kind: SpanKind = 'internal',
  parent: SpanData | null = activeSpan
): Span {
  return new Span({
    traceId: parent ? parent.traceId : newTraceId(),
    spanId: newSpanId(),
    parentSpanId: parent ? parent.spanId : '',
    name,
    kind,
    startTimeUnixMs: now(),
    endTimeUnixMs: 0,
    attributes: { ...attributes }
  });
}

export function getActiveSpan(): SpanData | null {
  return activeSpan;
}

export function setActiveSpan(span: SpanData | null): void {
  activeSpan = span;
}

/**
 * Runs `fn` with `span` active so any spans/fetches started inside it join the
 * same trace, then ends the span (even on throw). Restores the prior active span.
 */
export async function runWithSpan<T>(span: Span, fn: (span: Span) => T | Promise<T>): Promise<T> {
  const prev = activeSpan;
  activeSpan = span.data;
  try {
    return await fn(span);
  } finally {
    activeSpan = prev;
    span.end();
  }
}

/** Records a user action as a self-contained span. Returns it so callers may add attributes; it is already ended. */
export function recordUserAction(name: string, attributes: Record<string, unknown> = {}): Span {
  const span = startSpan(name, attributes, 'internal');
  span.end();
  return span;
}

/**
 * Returns headers extended with a `traceparent` for a fresh client span that is a
 * child of the active span (or a new root). The returned span must be ended by
 * the caller when the request completes. Used by the API layer to propagate
 * trace context onto every `/api/*` and SSE request without patching fetch.
 */
export function traceRequest(
  name: string,
  headers: Record<string, string> = {},
  attributes: Record<string, unknown> = {}
): { headers: Record<string, string>; span: Span } {
  const span = startSpan(name, attributes, 'client');
  return { headers: { ...headers, traceparent: span.traceparent() }, span };
}

function enqueue(span: SpanData): void {
  buffer.push(span);
  if (buffer.length >= MAX_BUFFER) flush();
}

/** Exports buffered spans to the Go telemetry sink. Best-effort; never throws. */
export function flush(useBeacon = false): void {
  if (buffer.length === 0) return;
  const spans = buffer.splice(0, buffer.length);
  const body = JSON.stringify({ spans });
  try {
    if (useBeacon && typeof navigator !== 'undefined' && typeof navigator.sendBeacon === 'function') {
      navigator.sendBeacon(TRACES_ENDPOINT, new Blob([body], { type: 'application/json' }));
      return;
    }
    if (typeof fetch === 'function') {
      // keepalive lets the export survive a navigating tab.
      void fetch(TRACES_ENDPOINT, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body,
        keepalive: true
      }).catch(() => {});
    }
  } catch {
    // Telemetry must never break the app.
  }
}

/**
 * Initializes span export: a periodic flush plus a flush on page hide/unload.
 * Idempotent and safe to call outside a browser (it simply does less).
 */
export function initTracing(): void {
  if (started) return;
  started = true;
  if (typeof setInterval === 'function') {
    flushTimer = setInterval(() => flush(), FLUSH_INTERVAL_MS);
  }
  if (typeof document !== 'undefined' && typeof document.addEventListener === 'function') {
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flush(true);
    });
  }
  if (typeof window !== 'undefined' && typeof window.addEventListener === 'function') {
    window.addEventListener('pagehide', () => flush(true));
  }
}

/** Test/teardown hook: stops the flush timer and clears buffered spans. */
export function _resetTracingForTest(): void {
  if (flushTimer) clearInterval(flushTimer);
  flushTimer = undefined;
  started = false;
  activeSpan = null;
  buffer.length = 0;
}
