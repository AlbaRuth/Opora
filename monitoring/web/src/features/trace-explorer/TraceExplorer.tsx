import type { TraceDetail, TraceSummary } from '../../types';

type Props = {
  traces: TraceSummary[];
  traceDetail: TraceDetail | null;
  loading: boolean;
  onSelectTrace: (trace: TraceSummary) => void;
};

export function TraceExplorer({ traces, traceDetail, loading, onSelectTrace }: Props) {
  const maxLatency = Math.max(1, ...(traceDetail?.llm_calls.map((call) => call.latency_ms ?? 0) ?? [1]));
  const groups = traceDetail ? groupCalls(traceDetail.llm_calls) : [];

  return (
    <section className="panel tracePanel">
      <div className="panelHeader">
        <h2>LLM Timeline</h2>
        {loading && <small>Loading trace...</small>}
      </div>
      <div className="traceList">
        {traces.map((trace) => (
          <button key={trace.trace_id} className="trace" onClick={() => onSelectTrace(trace)}>
            <strong>{trace.status}</strong>
            <span>{trace.channel}/{trace.source}</span>
            <small>
              {trace.duration_ms ?? 0} ms / {trace.total_tokens_input + trace.total_tokens_output} tokens
              {trace.sandbox_run_id ? ` / run #${trace.sandbox_run_id}` : ''}
            </small>
          </button>
        ))}
      </div>
      {traceDetail && (
        <div className="detail">
          <h3>Trace {traceDetail.trace.trace_id.slice(0, 8)}</h3>
          <div className="traceSummary">
            <span>{traceDetail.trace.status}</span>
            <span>{traceDetail.trace.channel}/{traceDetail.trace.source}</span>
            <span>{traceDetail.trace.duration_ms ?? 0} ms</span>
            <span>{traceDetail.trace.total_tokens_input + traceDetail.trace.total_tokens_output} tokens</span>
            {typeof traceDetail.trace.total_cost_usd === 'number' && (
              <span>${traceDetail.trace.total_cost_usd.toFixed(6)}</span>
            )}
          </div>
          {groups.map((group) => (
            <section key={group.title} className="callGroup">
              <h3>{group.title}</h3>
              {group.calls.map((call) => {
                const width = Math.max(8, ((call.latency_ms ?? 0) / maxLatency) * 100);
                const promptMessages = call.prompt_messages_full ?? call.prompt_messages;
                const response = call.response_full ?? call.response;
                return (
                  <article key={call.id} className="call">
                    <div className="callHeader">
                      <h4>{call.agent_type}: {call.task_name}</h4>
                      <small>{call.model} / {call.latency_ms ?? 0} ms / in {call.tokens_input ?? 0} / out {call.tokens_output ?? 0}</small>
                    </div>
                    <div className="badgeRow">
                      <span className="badge">{call.channel ?? traceDetail.trace.channel}</span>
                      <span className="badge">{call.source ?? traceDetail.trace.source}</span>
                      {call.sandbox_run_id && <span className="badge">run #{call.sandbox_run_id}</span>}
                      {call.sandbox_batch_id && <span className="badge">batch #{call.sandbox_batch_id}</span>}
                      <span className={call.prompt_truncated || call.response_truncated ? 'badge warn' : 'badge ok'}>
                        {call.prompt_truncated || call.response_truncated ? 'truncated preview' : 'full payload'}
                      </span>
                    </div>
                    <div className="waterfallBar"><span style={{ width: `${width}%` }} /></div>
                    <details open>
                      <summary>Generation params</summary>
                      <pre>{JSON.stringify(call.metadata?.generation_params ?? {
                        model: call.model,
                        temperature: call.temperature,
                        max_tokens: call.max_tokens,
                      }, null, 2)}</pre>
                    </details>
                    <details>
                      <summary>Variables</summary>
                      <pre>{JSON.stringify(call.metadata?.prompt_variables ?? {}, null, 2)}</pre>
                    </details>
                    <details>
                      <summary>Prompt</summary>
                      <pre>{promptMessages ? JSON.stringify(promptMessages, null, 2) : call.prompt}</pre>
                    </details>
                    <details open>
                      <summary>Response</summary>
                      <pre>{response}</pre>
                    </details>
                    {call.reasoning && (
                      <details>
                        <summary>Reasoning</summary>
                        <pre>{call.reasoning}</pre>
                      </details>
                    )}
                    <details>
                      <summary>Provider metadata</summary>
                      <pre>{JSON.stringify(call.provider_metadata ?? {}, null, 2)}</pre>
                    </details>
                  </article>
                );
              })}
            </section>
          ))}
        </div>
      )}
    </section>
  );
}

function groupCalls(calls: TraceDetail['llm_calls']) {
  const order = ['Auto patient', 'Signal/evaluator', 'Intake/Psychologist', 'Judge', 'Other'];
  const groups = new Map<string, TraceDetail['llm_calls']>();
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
