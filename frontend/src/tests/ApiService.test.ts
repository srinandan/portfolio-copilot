import { describe, it, expect, vi, beforeEach } from 'vitest';
import { ApiService } from '../services/api';

// Every request now carries an injected W3C traceparent header (distributed
// tracing). Assertions allow it via objectContaining + this matcher.
const TRACEPARENT_RE = /^00-[0-9a-f]{32}-[0-9a-f]{16}-01$/;
const withTraceparent = (extra: Record<string, unknown> = {}) =>
  expect.objectContaining({
    headers: expect.objectContaining({ traceparent: expect.stringMatching(TRACEPARENT_RE) }),
    ...extra
  });

describe('ApiService', () => {
  let service: ApiService;

  beforeEach(() => {
    service = new ApiService('http://localhost:8080');
    vi.restoreAllMocks();
  });

  it('checkHealth calls /health and returns JSON when response is ok', async () => {
    const mockHealth = { status: 'ok' };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHealth)
    });

    const result = await service.checkHealth();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/health', withTraceparent());
    expect(result).toEqual(mockHealth);
  });

  it('checkHealth throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.checkHealth()).rejects.toThrow('Health check failed with status 500');
  });

  it('getHoldings fetches holdings data', async () => {
    const mockHoldings = {
      user_id: 'usr_test',
      as_of: '2026-08-01T00:00:00Z',
      positions: [],
      cash_usd: 1000,
      total_value_usd: 1000
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockHoldings)
    });

    const result = await service.getHoldings();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/holdings', withTraceparent());
    expect(result).toEqual(mockHoldings);
  });

  it('getDocuments fetches document items', async () => {
    const mockDocs = [{ document_id: 'doc_1', title: 'Test Doc', doc_type: 'tax_return' }];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDocs)
    });

    const result = await service.getDocuments();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/documents', withTraceparent());
    expect(result).toEqual(mockDocs);
  });

  it('getSpendingReport fetches report with window query param', async () => {
    const mockReport = {
      report_id: 'rep_1',
      user_id: 'usr_test',
      analysis_window_months: 6,
      categories: [],
      recurring_subscriptions: [],
      total_recurring_monthly_usd: 0,
      generated_at: '2026-08-01T00:00:00Z'
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockReport)
    });

    const result = await service.getSpendingReport(6);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/spending_report?window_months=6',
      withTraceparent()
    );
    expect(result).toEqual(mockReport);
  });

  it('getDriftReport fetches drift report', async () => {
    const mockDrift = {
      drift_id: 'drift_1',
      user_id: 'usr_test',
      status: 'DRIFT_DETECTED',
      asset_classes: [],
      generated_at: '2026-08-01T00:00:00Z'
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDrift)
    });

    const result = await service.getDriftReport();
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/drift_report', withTraceparent());
    expect(result).toEqual(mockDrift);
  });

  it('triggerPlan posts plan payload to /api/plan', async () => {
    const mockResponse = { ok: true, status: 200 } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const payload = { user_id: 'usr_1', message: 'Hello planner' };
    const res = await service.triggerPlan(payload);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/plan',
      withTraceparent({ method: 'POST', body: JSON.stringify(payload) })
    );
    expect(res).toBe(mockResponse);
  });

  it('resumePlan posts resume payload to /api/plan/resume', async () => {
    const mockResponse = { ok: true, status: 200 } as unknown as Response;
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const payload = {
      user_id: 'usr_1',
      session_id: 'sess_1',
      invocation_id: 'inv_1',
      interrupt_id: 'int_1',
      payload: { decision: 'approved' }
    };
    const res = await service.resumePlan(payload);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/plan/resume',
      withTraceparent({ method: 'POST', body: JSON.stringify(payload) })
    );
    expect(res).toBe(mockResponse);
  });

  it('readSSEStream parses SSE data lines and calls onEvent', async () => {
    const sseText = 'data: {"event_id": "1", "message": "hello"}\n\ndata: {"event_id": "2", "kind": "hitl_approval_request"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream);
    const events: any[] = [];
    const { readSSEStream } = await import('../services/api');

    await readSSEStream(mockResponse, (e) => events.push(e));
    expect(events).toHaveLength(2);
    expect(events[0]).toEqual({ event_id: '1', message: 'hello' });
    expect(events[1]).toEqual({ event_id: '2', kind: 'hitl_approval_request' });
  });

  it('readSSEStream handles non-JSON raw strings and unreadable response', async () => {
    const sseText = 'data: raw plain message\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream);
    const events: any[] = [];
    const { readSSEStream } = await import('../services/api');

    await readSSEStream(mockResponse, (e) => events.push(e));
    expect(events).toHaveLength(1);
    expect(events[0]).toEqual({ raw: 'raw plain message' });

    // Test with response having no body
    const emptyResponse = { body: null } as unknown as Response;
    await readSSEStream(emptyResponse, () => {});
  });

  it('streamPlan calls triggerPlan and streams events', async () => {
    const sseText = 'data: {"status": "in_progress"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream, { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: any[] = [];
    await service.streamPlan(
      { user_id: 'usr_test', message: 'test plan' },
      (e) => events.push(e)
    );

    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan', expect.any(Object));
    expect(events).toEqual([{ status: 'in_progress' }]);
  });

  it('streamPlanResume calls resumePlan and streams events', async () => {
    const sseText = 'data: {"status": "executed"}\n\n';
    const stream = new ReadableStream({
      start(controller) {
        controller.enqueue(new TextEncoder().encode(sseText));
        controller.close();
      }
    });
    const mockResponse = new Response(stream, { status: 200 });
    globalThis.fetch = vi.fn().mockResolvedValue(mockResponse);

    const events: any[] = [];
    await service.streamPlanResume(
      {
        user_id: 'usr_test',
        session_id: 'sess_1',
        invocation_id: 'inv_1',
        interrupt_id: 'int_1',
        payload: { decision: 'approve' }
      },
      (e) => events.push(e)
    );

    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/plan/resume', expect.any(Object));
    expect(events).toEqual([{ status: 'executed' }]);
  });

  it('getUserProfile fetches user profile', async () => {
    const mockProfile = {
      user_id: 'demo_user',
      full_name: 'Alex Mercer',
      age: 46
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProfile)
    });

    const result = await service.getUserProfile('demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith('http://localhost:8080/api/profile?user_id=demo_user', withTraceparent());
    expect(result).toEqual(mockProfile);
  });

  it('getUserProfile throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500
    });

    await expect(service.getUserProfile('demo_user')).rejects.toThrow('Get user profile failed with status 500');
  });

  it('updateUserProfile posts user profile payload', async () => {
    const mockProfile = {
      user_id: 'demo_user',
      full_name: 'Alex Mercer',
      age: 46
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'ok', profile: mockProfile })
    });

    const result = await service.updateUserProfile(mockProfile);
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/profile',
      withTraceparent({
        method: 'POST',
        headers: expect.objectContaining({ 'Content-Type': 'application/json' }),
        body: JSON.stringify(mockProfile)
      })
    );
    expect(result.status).toBe('ok');
    expect(result.profile).toEqual(mockProfile);
  });

  it('updateUserProfile throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400
    });

    await expect(
      service.updateUserProfile({ user_id: 'demo_user' })
    ).rejects.toThrow('Update user profile failed with status 400');
  });

  it('getOnboarding fetches onboarding profile', async () => {
    const mockProfile = {
      has_active_ips: true,
      user_id: 'demo_user',
      goals: []
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockProfile)
    });

    const result = await service.getOnboarding('demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/onboarding?user_id=demo_user',
      withTraceparent()
    );
    expect(result).toEqual(mockProfile);
  });

  it('getOnboarding throws error on failure', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 502
    });

    await expect(service.getOnboarding('demo_user')).rejects.toThrow(
      'Get onboarding profile failed with status 502'
    );
  });

  it('uploadDocument sends multipart FormData and returns DocumentItem', async () => {
    const mockDoc = {
      id: 'doc-123',
      filename: 'test.csv',
      status: 'SUCCESS',
      records_parsed: 5
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockDoc)
    });

    const file = new File(['a,b\n1,2'], 'test.csv', { type: 'text/csv' });
    const result = await service.uploadDocument(file, 'transactions', 'checking_transactions');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/documents',
      withTraceparent({
        method: 'POST',
        body: expect.any(FormData)
      })
    );
    expect(result).toEqual(mockDoc);
  });

  it('uploadDocument throws error when response is not ok', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ error: 'invalid file extension' })
    });

    const file = new File(['bad'], 'test.pdf');
    await expect(service.uploadDocument(file, 'transactions')).rejects.toThrow(
      'invalid file extension'
    );
  });

  it('uploadW2 sends multipart FormData and returns W2Document', async () => {
    const mockW2 = {
      id: 'w2-123',
      user_id: 'demo_user',
      tax_year: 2024,
      status: 'SUCCESS',
      wages_and_compensation: {
        box1_wages_tips_other_comp_usd: 220000
      }
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockW2)
    });

    const file = new File(['dummy pdf bytes'], 'w2_2024.pdf', { type: 'application/pdf' });
    const result = await service.uploadW2(file, 'demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/profile/w2/upload',
      withTraceparent({
        method: 'POST',
        body: expect.any(FormData)
      })
    );
    expect(result).toEqual(mockW2);
  });

  it('getW2Documents retrieves list of W2Documents', async () => {
    const mockW2List = [
      {
        id: 'w2-123',
        user_id: 'demo_user',
        tax_year: 2024,
        status: 'SUCCESS',
        wages_and_compensation: { box1_wages_tips_other_comp_usd: 220000 }
      }
    ];
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockW2List)
    });

    const result = await service.getW2Documents('demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/profile/w2?user_id=demo_user',
      withTraceparent()
    );
    expect(result).toEqual(mockW2List);
  });

  it('deleteW2Document sends DELETE request', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ status: 'deleted' })
    });

    await service.deleteW2Document('w2-123', 'demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/profile/w2/w2-123?user_id=demo_user',
      withTraceparent({ method: 'DELETE' })
    );
  });

  it('applyW2ToProfile sends POST request and updates profile income', async () => {
    const mockAppliedRes = {
      status: 'applied',
      profile: {
        user_id: 'demo_user',
        annual_income_usd: 220000
      }
    };
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: () => Promise.resolve(mockAppliedRes)
    });

    const result = await service.applyW2ToProfile('w2-123', 'demo_user');
    expect(globalThis.fetch).toHaveBeenCalledWith(
      'http://localhost:8080/api/profile/w2/w2-123/apply?user_id=demo_user',
      withTraceparent({ method: 'POST' })
    );
    expect(result).toEqual(mockAppliedRes);
  });
});

