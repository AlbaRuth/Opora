import type {
  ChatSummary,
  ClinicalCardResponse,
  EffectiveModelConfig,
  MessageItem,
  ModelOverrides,
  PatientTemplate,
  SandboxBatchCreatePayload,
  SandboxBatchResponse,
  SandboxCreatePayload,
  SandboxSessionResponse,
  SandboxTurnResponse,
  TraceDetail,
  TraceSummary,
} from './types';

const API_BASE = import.meta.env.VITE_MONITOR_API_BASE ?? 'http://localhost:8000';
const API_TOKEN = import.meta.env.VITE_MONITOR_API_TOKEN ?? 'dev-monitor-token';

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': API_TOKEN,
      ...(init?.headers ?? {}),
    },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.json() as Promise<T>;
}

async function requestText(path: string): Promise<string> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'X-API-Key': API_TOKEN,
    },
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${await response.text()}`);
  }
  return response.text();
}

export const api = {
  chats: (source?: string) =>
    request<ChatSummary[]>(`/api/chats${source ? `?source=${source}` : ''}`),
  chat: (sessionId: number) => request<ChatSummary>(`/api/chats/${sessionId}`),
  messages: (sessionId: number) => request<MessageItem[]>(`/api/chats/${sessionId}/messages`),
  clinicalCard: (sessionId: number) =>
    request<ClinicalCardResponse>(`/api/chats/${sessionId}/clinical-card`),
  traces: (sessionId: number) => request<TraceSummary[]>(`/api/chats/${sessionId}/traces`),
  traceDetail: (traceId: string) => request<TraceDetail>(`/api/traces/${traceId}`),
  exportChat: (sessionId: number, format: 'json' | 'md') =>
    format === 'md'
      ? requestText(`/api/chats/${sessionId}/export?format=md`)
      : request<Record<string, unknown>>(`/api/chats/${sessionId}/export?format=json`),
  templates: () => request<PatientTemplate[]>('/api/sandbox/templates/patients'),
  modelConfig: () => request<EffectiveModelConfig>('/api/sandbox/model-config'),
  sandboxTurns: (runId: number) =>
    request<SandboxTurnResponse[]>(`/api/sandbox/sessions/${runId}/turns`),
  createSandbox: (payload: SandboxCreatePayload) =>
    request<SandboxSessionResponse>('/api/sandbox/sessions', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  sendSandboxMessage: (runId: number, message: string, modelOverrides?: ModelOverrides) =>
    request<SandboxTurnResponse>(`/api/sandbox/sessions/${runId}/messages`, {
      method: 'POST',
      body: JSON.stringify({ message, model_overrides: modelOverrides }),
    }),
  autoRun: (runId: number, maxTurns: number, modelOverrides?: ModelOverrides) =>
    request<SandboxTurnResponse[]>(`/api/sandbox/sessions/${runId}/auto-run`, {
      method: 'POST',
      body: JSON.stringify({ max_turns: maxTurns, model_overrides: modelOverrides }),
    }),
  stopSandbox: (runId: number) =>
    request<SandboxSessionResponse>(`/api/sandbox/sessions/${runId}/stop`, {
      method: 'POST',
    }),
  judgeSandbox: (runId: number) =>
    request<SandboxSessionResponse>(`/api/sandbox/sessions/${runId}/judge`, {
      method: 'POST',
    }),
  getSandboxSession: (runId: number) =>
    request<SandboxSessionResponse>(`/api/sandbox/sessions/${runId}`),
  createSandboxBatch: (payload: SandboxBatchCreatePayload) =>
    request<SandboxBatchResponse>('/api/sandbox/batches', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),
  sandboxBatchRuns: (batchId: number) =>
    request<SandboxSessionResponse[]>(`/api/sandbox/batches/${batchId}/runs`),
  exportSandboxRun: (runId: number, format: 'json' | 'md') =>
    format === 'md'
      ? requestText(`/api/sandbox/sessions/${runId}/export?format=md`)
      : request<Record<string, unknown>>(`/api/sandbox/sessions/${runId}/export?format=json`),
  exportSandboxBatch: (batchId: number, format: 'json' | 'md') =>
    format === 'md'
      ? requestText(`/api/sandbox/batches/${batchId}/export?format=md`)
      : request<Record<string, unknown>>(`/api/sandbox/batches/${batchId}/export?format=json`),
};
