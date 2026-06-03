import type { TraceDetail } from '../../types';
import {
  agentLabel,
  generationParams,
  groupCalls,
  promptMessages,
  promptVariables,
  responseText,
} from './traceUtils';

type Props = {
  traceDetail: TraceDetail;
  loading: boolean;
  onClose: () => void;
  onOpenJudgeReport?: () => void;
};

export function TraceInspector({ traceDetail, loading, onClose, onOpenJudgeReport }: Props) {
  const { trace } = traceDetail;
  const groups = groupCalls(traceDetail.llm_calls);
  const maxLatency = Math.max(1, ...traceDetail.llm_calls.map((call) => call.latency_ms ?? 0));
  const hasJudgeCall = traceDetail.llm_calls.some((call) => call.agent_type === 'sandbox_judge');

  return (
    <aside className="traceInspector">
      <div className="traceInspectorHeader">
        <div>
          <h3>Pipeline trace</h3>
          <small>{trace.trace_id.slice(0, 8)} · {trace.channel}/{trace.source}</small>
        </div>
        <button type="button" className="traceInspectorClose" onClick={onClose}>Close</button>
      </div>

      <div className="traceInspectorSummary">
        <Metric label="Status" value={trace.status} />
        <Metric label="Duration" value={`${trace.duration_ms ?? 0} ms`} />
        <Metric label="Tokens" value={`${trace.total_tokens_input + trace.total_tokens_output}`} />
        {typeof trace.total_cost_usd === 'number' && (
          <Metric label="Cost" value={`$${trace.total_cost_usd.toFixed(6)}`} />
        )}
      </div>

      {(hasJudgeCall || onOpenJudgeReport) && onOpenJudgeReport && (
        <button type="button" className="traceLink judgeReportLink" onClick={onOpenJudgeReport}>
          Open judge report
        </button>
      )}

      {loading && <p className="muted">Loading trace...</p>}

      {!loading && groups.length === 0 && (
        <p className="muted traceInspectorEmpty">
          No LLM calls were recorded for this trace. Check API logs or rerun the turn after fixing provider errors.
        </p>
      )}

      {groups.map((group) => (
        <section key={group.title} className="traceGroup">
          <h4>{group.title}</h4>
          {group.calls.map((call) => {
            const width = Math.max(8, ((call.latency_ms ?? 0) / maxLatency) * 100);
            const messages = promptMessages(call);
            const params = generationParams(call);
            const variables = promptVariables(call);
            return (
              <article key={call.id} className="traceCallCard">
                <div className="traceCallHeader">
                  <strong>{agentLabel(call)}</strong>
                  <span>{call.latency_ms ?? 0} ms</span>
                </div>
                <div className="badgeRow">
                  <span className="badge">{call.model}</span>
                  <span className="badge">in {call.tokens_input ?? 0}</span>
                  <span className="badge">out {call.tokens_output ?? 0}</span>
                  <span className={call.success ? 'badge ok' : 'badge warn'}>
                    {call.success ? 'ok' : 'failed'}
                  </span>
                </div>
                <div className="waterfallBar"><span style={{ width: `${width}%` }} /></div>

                <details open>
                  <summary>Generation params</summary>
                  <dl className="kvGrid">
                    {Object.entries(params).map(([key, value]) => (
                      <div key={key} className="kvRow">
                        <dt>{key}</dt>
                        <dd>{formatValue(value)}</dd>
                      </div>
                    ))}
                  </dl>
                </details>

                {Object.keys(variables).length > 0 && (
                  <details>
                    <summary>Prompt variables</summary>
                    <dl className="kvGrid">
                      {Object.entries(variables).map(([key, value]) => (
                        <div key={key} className="kvRow">
                          <dt>{key}</dt>
                          <dd>{formatValue(value)}</dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                )}

                <details open>
                  <summary>Prompt</summary>
                  {messages ? (
                    <div className="promptBlocks">
                      {messages.map((message, index) => (
                        <div key={`${message.role}-${index}`} className={`promptBlock ${message.role}`}>
                          <span className="promptRole">{message.role}</span>
                          <div className="promptBody">{message.content}</div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <div className="textBlock">{call.prompt ?? '—'}</div>
                  )}
                </details>

                <details open>
                  <summary>Response</summary>
                  <div className="textBlock">{responseText(call) || '—'}</div>
                </details>

                {call.reasoning && (
                  <details>
                    <summary>Reasoning</summary>
                    <div className="textBlock">{call.reasoning}</div>
                  </details>
                )}

                {call.error_message && (
                  <p className="error traceCallError">{call.error_message}</p>
                )}
              </article>
            );
          })}
        </section>
      ))}
    </aside>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="traceMetric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function formatValue(value: unknown): string {
  if (value === null || value === undefined) return '—';
  if (typeof value === 'string') return value;
  if (typeof value === 'number' || typeof value === 'boolean') return String(value);
  if (Array.isArray(value)) return value.map((item) => formatValue(item)).join(', ');
  return JSON.stringify(value);
}
