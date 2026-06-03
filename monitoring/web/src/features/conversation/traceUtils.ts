import type { LlmCallItem, TraceDetail } from '../../types';

export function groupCalls(calls: TraceDetail['llm_calls']) {
  const order = ['Auto patient', 'Signal/evaluator', 'Intake/Psychologist', 'Judge', 'Other'];
  const groups = new Map<string, LlmCallItem[]>();
  for (const call of calls) {
    const title = call.agent_type === 'sandbox_patient'
      ? 'Auto patient'
      : call.agent_type === 'sandbox_judge'
        ? 'Judge'
        : call.agent_type === 'intake' || call.agent_type === 'therapist'
          ? 'Intake/Psychologist'
          : call.agent_type === 'evaluator'
            ? 'Signal/evaluator'
            : 'Other';
    groups.set(title, [...(groups.get(title) ?? []), call]);
  }
  return order
    .filter((title) => groups.has(title))
    .map((title) => ({ title, calls: groups.get(title)! }));
}

export function agentLabel(call: LlmCallItem) {
  return `${call.agent_type}.${call.task_name}`;
}

export function promptMessages(call: LlmCallItem) {
  return call.prompt_messages_full ?? call.prompt_messages ?? null;
}

export function responseText(call: LlmCallItem) {
  return call.response_full ?? call.response ?? '';
}

export function generationParams(call: LlmCallItem): Record<string, unknown> {
  const fromMeta = call.metadata?.generation_params;
  if (fromMeta && typeof fromMeta === 'object') {
    return fromMeta as Record<string, unknown>;
  }
  return {
    model: call.model,
    temperature: call.temperature,
    max_tokens: call.max_tokens,
  };
}

export function promptVariables(call: LlmCallItem): Record<string, unknown> {
  const raw = call.metadata?.prompt_variables;
  return raw && typeof raw === 'object' ? (raw as Record<string, unknown>) : {};
}
