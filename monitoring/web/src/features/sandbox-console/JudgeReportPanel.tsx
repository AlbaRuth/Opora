import type { ReactNode } from 'react';
import type { SandboxJudgeResult, SandboxSessionResponse } from '../../types';

type Props = {
  sandbox: SandboxSessionResponse | null;
  batchRuns: SandboxSessionResponse[];
  busy: boolean;
  onRunJudge: () => void;
  onSelectRun: (run: SandboxSessionResponse) => void;
};

export function JudgeReportPanel({
  sandbox,
  batchRuns,
  busy,
  onRunJudge,
  onSelectRun,
}: Props) {
  const judge = (sandbox?.judge_result ?? null) as SandboxJudgeResult | null;

  return (
    <section className="surface judgeSurface">
      <div className="sectionTitle">
        <span className="sectionIndex">05</span>
        <div>
          <h3>QA Judge</h3>
          <small>Оценка психолога, extraction и архитектурных bottleneck&apos;ов</small>
        </div>
      </div>

      {!judge && (
        <div className="emptyState">
          <strong>Оценка ещё не запущена</strong>
          <span>
            Для single session нажмите LLM Judge во вкладке Conversation. В batch оценка
            запускается автоматически после каждого run.
          </span>
          <button className="primaryAction" onClick={onRunJudge} disabled={!sandbox || busy}>
            Запустить оценку
          </button>
        </div>
      )}

      {judge && (
        <div className="judgeReport">
          <div className="judgeSummaryRow">
            <div className="judgeScoreBlock">
              <span>Overall</span>
              <strong>{formatScore(judge.overall_score)}</strong>
            </div>
            <VerdictBadge verdict={judge.overall_verdict} />
            <button onClick={onRunJudge} disabled={!sandbox || busy}>Перезапустить</button>
          </div>

          <div className="judgeGrid">
            <JudgeSection
              title="Therapist quality"
              score={judge.therapist_quality?.score}
              items={judge.therapist_quality?.findings}
            />
            <JudgeSection
              title="Extraction quality"
              score={judge.extraction_quality?.score}
              items={judge.extraction_quality?.findings}
              extra={
                <>
                  {(judge.extraction_quality?.missing_in_card ?? []).length > 0 && (
                    <JudgeList label="Missing in card" items={judge.extraction_quality!.missing_in_card!} />
                  )}
                  {(judge.extraction_quality?.hallucinated_in_card ?? []).length > 0 && (
                    <JudgeList
                      label="Hallucinated in card"
                      items={judge.extraction_quality!.hallucinated_in_card!}
                    />
                  )}
                </>
              }
            />
          </div>

          {(judge.architecture_bottlenecks ?? []).length > 0 && (
            <div className="judgeBottlenecks">
              <h4>Bottlenecks</h4>
              <ul>
                {judge.architecture_bottlenecks!.map((item, index) => (
                  <li key={`${item.turn_number}-${index}`}>
                    <SeverityBadge severity={item.severity} />
                    <span>
                      Turn {item.turn_number} · {item.component}: {item.issue}
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {(judge.recommended_fixes ?? []).length > 0 && (
            <div className="judgeFixes">
              <h4>Recommended fixes</h4>
              <ul>
                {judge.recommended_fixes!.map((fix) => (
                  <li key={fix}>{fix}</li>
                ))}
              </ul>
            </div>
          )}
        </div>
      )}

      {batchRuns.length > 1 && (
        <div className="batchRunsTable">
          <h4>Batch runs</h4>
          <table>
            <thead>
              <tr>
                <th>Run</th>
                <th>Status</th>
                <th>Score</th>
                <th>Verdict</th>
              </tr>
            </thead>
            <tbody>
              {batchRuns.map((run) => {
                const runJudge = run.judge_result as SandboxJudgeResult | null | undefined;
                return (
                  <tr
                    key={run.run_id}
                    className={sandbox?.run_id === run.run_id ? 'active' : ''}
                    onClick={() => onSelectRun(run)}
                  >
                    <td>#{run.run_id}</td>
                    <td>{run.status}</td>
                    <td>{runJudge ? formatScore(runJudge.overall_score) : '—'}</td>
                    <td>{runJudge?.overall_verdict ?? '—'}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function JudgeSection({
  title,
  score,
  items,
  extra,
}: {
  title: string;
  score?: number;
  items?: string[];
  extra?: ReactNode;
}) {
  return (
    <article className="judgeSection">
      <h4>{title} {typeof score === 'number' ? `(${formatScore(score)})` : ''}</h4>
      <ul>
        {(items ?? []).map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
      {extra}
    </article>
  );
}

function JudgeList({ label, items }: { label: string; items: string[] }) {
  return (
    <div className="judgeSubList">
      <strong>{label}</strong>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

function VerdictBadge({ verdict }: { verdict?: string }) {
  const tone = verdict === 'pass' ? 'ok' : verdict === 'fail' ? 'warn' : 'accent';
  return <span className={`badge ${tone}`}>{verdict ?? 'unknown'}</span>;
}

function SeverityBadge({ severity }: { severity?: string }) {
  const tone = severity === 'high' ? 'warn' : severity === 'medium' ? 'accent' : 'ok';
  return <span className={`badge ${tone}`}>{severity ?? 'low'}</span>;
}

function formatScore(score?: number) {
  if (typeof score !== 'number') return '—';
  return score.toFixed(1);
}
