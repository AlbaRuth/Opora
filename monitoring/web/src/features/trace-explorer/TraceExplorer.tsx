import type { TraceDetail, TraceSummary } from '../../types';

type Props = {
  traces: TraceSummary[];
  traceDetail: TraceDetail | null;
  loading: boolean;
  onSelectTrace: (trace: TraceSummary) => void;
};

export function TraceExplorer({ traces, traceDetail, loading, onSelectTrace }: Props) {
  const maxLatency = Math.max(1, ...(traceDetail?.llm_calls.map((call) => call.latency_ms ?? 0) ?? [1]));

  return (
    <section className="panel tracePanel">
      <div className="panelHeader">
        <h2>LLM Timeline</h2>
        {loading && <small>Загружаю trace...</small>}
      </div>
      <div className="traceList">
        {traces.map((trace) => (
          <button key={trace.trace_id} className="trace" onClick={() => onSelectTrace(trace)}>
            <strong>{trace.status}</strong>
            <span>{trace.channel}/{trace.source}</span>
            <small>
              {trace.duration_ms ?? 0} ms · {trace.total_tokens_input + trace.total_tokens_output} tokens
            </small>
          </button>
        ))}
      </div>
      {traceDetail && (
        <div className="detail">
          <h3>Trace {traceDetail.trace.trace_id.slice(0, 8)}</h3>
          <div className="traceSummary">
            <span>{traceDetail.trace.status}</span>
            <span>{traceDetail.trace.duration_ms ?? 0} ms</span>
            <span>{traceDetail.trace.total_tokens_input + traceDetail.trace.total_tokens_output} tokens</span>
            {typeof traceDetail.trace.total_cost_usd === 'number' && (
              <span>${traceDetail.trace.total_cost_usd.toFixed(6)}</span>
            )}
          </div>
          {traceDetail.llm_calls.map((call) => {
            const width = Math.max(8, ((call.latency_ms ?? 0) / maxLatency) * 100);
            return (
              <article key={call.id} className="call">
                <div className="callHeader">
                  <h4>{call.agent_type}: {call.task_name}</h4>
                  <small>{call.model} · {call.latency_ms ?? 0} ms · in {call.tokens_input ?? 0} / out {call.tokens_output ?? 0}</small>
                </div>
                <div className="waterfallBar"><span style={{ width: `${width}%` }} /></div>
                <details open>
                  <summary>Generation Params</summary>
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
                  <pre>{call.prompt_messages ? JSON.stringify(call.prompt_messages, null, 2) : call.prompt}</pre>
                </details>
                <details open>
                  <summary>Response</summary>
                  <pre>{call.response}</pre>
                </details>
                {call.reasoning && (
                  <details>
                    <summary>Reasoning</summary>
                    <pre>{call.reasoning}</pre>
                  </details>
                )}
                <details>
                  <summary>Provider Metadata</summary>
                  <pre>{JSON.stringify(call.provider_metadata ?? {}, null, 2)}</pre>
                </details>
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}
