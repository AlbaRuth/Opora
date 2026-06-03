import type {
  EffectiveModelConfig,
  GenerationConfig,
  SandboxBatchResponse,
  SandboxPrescreeningProfile,
  SandboxSessionResponse,
  SandboxTurnResponse,
  TraceSummary,
} from '../../types';
import { SelectField } from '../../components/SelectField';
import { ModelSettings } from '../model-settings/ModelSettings';
import { JudgeReportPanel } from './JudgeReportPanel';

type Props = {
  startPhase: 'prescreening' | 'intake' | 'therapy';
  prescreeningMode: 'manual' | 'ai_generated';
  manualProfile: SandboxPrescreeningProfile;
  aiPrescreeningSeed: string;
  scenarioSeed: string;
  autoRunTurns: number;
  batchCount: number;
  batchParallelism: number;
  sandboxBatch: SandboxBatchResponse | null;
  sandboxBatchRuns: SandboxSessionResponse[];
  sandbox: SandboxSessionResponse | null;
  sandboxMessage: string;
  sandboxTurns: SandboxTurnResponse[];
  busy: boolean;
  modelConfig: EffectiveModelConfig | null;
  selectedModelTask: string;
  draftModelConfig: GenerationConfig | null;
  onStartPhaseChange: (phase: 'prescreening' | 'intake' | 'therapy') => void;
  onPrescreeningModeChange: (mode: 'manual' | 'ai_generated') => void;
  onManualProfileChange: (profile: SandboxPrescreeningProfile) => void;
  onAiPrescreeningSeedChange: (seed: string) => void;
  onScenarioSeedChange: (seed: string) => void;
  onAutoRunTurnsChange: (turns: number) => void;
  onBatchCountChange: (count: number) => void;
  onBatchParallelismChange: (parallelism: number) => void;
  onMessageChange: (message: string) => void;
  onCreate: () => void;
  onCreateBatch: () => void;
  onSend: () => void;
  onAutoRun: () => void;
  onStop: () => void;
  onRefreshTurns: () => void;
  onExportRun: (format: 'json' | 'md') => void;
  onExportBatch: (format: 'json' | 'md') => void;
  onOpenTrace: (trace: TraceSummary) => void;
  onRunJudge: () => void;
  onSelectBatchRun: (run: SandboxSessionResponse) => void;
  onModelTaskChange: (task: string) => void;
  onDraftModelChange: (config: GenerationConfig) => void;
  onResetModel: () => void;
};

export function SandboxConsole({
  startPhase,
  prescreeningMode,
  manualProfile,
  aiPrescreeningSeed,
  scenarioSeed,
  autoRunTurns,
  batchCount,
  batchParallelism,
  sandboxBatch,
  sandboxBatchRuns,
  sandbox,
  sandboxMessage,
  sandboxTurns,
  busy,
  modelConfig,
  selectedModelTask,
  draftModelConfig,
  onStartPhaseChange,
  onPrescreeningModeChange,
  onManualProfileChange,
  onAiPrescreeningSeedChange,
  onScenarioSeedChange,
  onAutoRunTurnsChange,
  onBatchCountChange,
  onBatchParallelismChange,
  onMessageChange,
  onCreate,
  onCreateBatch,
  onSend,
  onAutoRun,
  onStop,
  onRefreshTurns,
  onExportRun,
  onExportBatch,
  onOpenTrace,
  onRunJudge,
  onSelectBatchRun,
  onModelTaskChange,
  onDraftModelChange,
  onResetModel,
}: Props) {
  const completedBatchRuns = sandboxBatch?.created_runs ?? 0;
  const requestedBatchRuns = sandboxBatch?.requested_count ?? batchCount;
  const batchProgress = requestedBatchRuns > 0 ? Math.min(100, Math.round((completedBatchRuns / requestedBatchRuns) * 100)) : 0;

  return (
    <section className="panel sandbox">
      <div className="sandboxHero">
        <div>
          <span className="eyebrow">Controlled LLM testbench</span>
          <h2>Sandbox Autotest</h2>
          <p>
            Run single sessions or batch prescreening simulations with full traces, judge output, and exportable logs.
          </p>
        </div>
        <div className="statusStack">
          <StatusPill label="Run" value={sandbox ? `#${sandbox.run_id} / ${sandbox.status}` : 'not created'} tone={sandbox ? 'ok' : 'idle'} />
          <StatusPill label="Batch" value={sandboxBatch ? `#${sandboxBatch.batch_id} / ${sandboxBatch.status}` : 'not created'} tone={sandboxBatch ? 'accent' : 'idle'} />
        </div>
      </div>

      <div className="sandboxMetrics">
        <MetricCard label="Turns" value={String(sandboxTurns.length)} hint="loaded transcript turns" />
        <MetricCard label="Auto turns" value={String(autoRunTurns)} hint="per active run" />
        <MetricCard label="Batch size" value={String(batchCount)} hint={`${batchParallelism} parallel`} />
        <MetricCard label="Batch progress" value={`${batchProgress}%`} hint={`${completedBatchRuns}/${requestedBatchRuns} runs`} />
      </div>

      {busy && (
        <div className="runBanner">
          <span className="pulseDot" />
          <strong>LLM pipeline is running</strong>
          <span>Waiting for patient, psychologist, evaluator, or judge calls to finish.</span>
        </div>
      )}

      <div className="sandboxGrid">
        <section className="surface controlSurface">
          <div className="sectionTitle">
            <span className="sectionIndex">01</span>
            <div>
              <h3>Run Setup</h3>
              <small>AI-generated patient profile, scenario, and optional seeds</small>
            </div>
          </div>

          <div className="settingsGrid compact">
            <label>
              Start phase
              <SelectField
                aria-label="Start phase"
                value={startPhase}
                onChange={(value) => onStartPhaseChange(value as 'prescreening' | 'intake' | 'therapy')}
                options={[
                  { value: 'prescreening', label: 'Prescreening' },
                  { value: 'intake', label: 'Intake' },
                  { value: 'therapy', label: 'Therapy' },
                ]}
              />
            </label>
            <label>
              Prescreening data
              <SelectField
                aria-label="Prescreening data"
                value={prescreeningMode}
                onChange={(value) => onPrescreeningModeChange(value as 'manual' | 'ai_generated')}
                options={[
                  { value: 'ai_generated', label: 'AI generated (random)' },
                  { value: 'manual', label: 'Manual override' },
                ]}
              />
            </label>
            <label>
              Auto turns
              <input type="number" min={1} max={20} value={autoRunTurns} onChange={(event) => onAutoRunTurnsChange(Number(event.target.value))} />
            </label>
            <label>
              Batch sessions
              <input type="number" min={1} max={100} value={batchCount} onChange={(event) => onBatchCountChange(Number(event.target.value))} />
            </label>
            <label>
              Parallelism
              <input type="number" min={1} max={20} value={batchParallelism} onChange={(event) => onBatchParallelismChange(Number(event.target.value))} />
            </label>
          </div>

          {prescreeningMode === 'manual' ? (
            <div className="settingsGrid compact">
              <label>
                Patient name
                <input value={manualProfile.patient_name} onChange={(event) => onManualProfileChange({ ...manualProfile, patient_name: event.target.value })} />
              </label>
              <label>
                Patient age
                <input type="number" value={manualProfile.patient_age ?? ''} onChange={(event) => onManualProfileChange({ ...manualProfile, patient_age: event.target.value === '' ? null : Number(event.target.value) })} />
              </label>
              <label>
                Patient sex
                <SelectField
                  aria-label="Patient sex"
                  value={manualProfile.patient_sex}
                  onChange={(value) => onManualProfileChange({
                    ...manualProfile,
                    patient_sex: value as SandboxPrescreeningProfile['patient_sex'],
                  })}
                  options={[
                    { value: 'prefer_not_to_say', label: 'Prefer not to say' },
                    { value: 'female', label: 'Female' },
                    { value: 'male', label: 'Male' },
                  ]}
                />
              </label>
              <label>
                Address
                <SelectField
                  aria-label="Address mode"
                  value={manualProfile.address_mode}
                  onChange={(value) => onManualProfileChange({
                    ...manualProfile,
                    address_mode: value as SandboxPrescreeningProfile['address_mode'],
                  })}
                  options={[
                    { value: 'formal', label: 'Formal' },
                    { value: 'informal', label: 'Informal' },
                  ]}
                />
              </label>
              <label>
                Therapist name
                <input value={manualProfile.therapist_name} onChange={(event) => onManualProfileChange({ ...manualProfile, therapist_name: event.target.value })} />
              </label>
              <label>
                Therapist gender
                <SelectField
                  aria-label="Therapist gender"
                  value={manualProfile.therapist_gender}
                  onChange={(value) => onManualProfileChange({
                    ...manualProfile,
                    therapist_gender: value as SandboxPrescreeningProfile['therapist_gender'],
                  })}
                  options={[
                    { value: 'female', label: 'Female' },
                    { value: 'male', label: 'Male' },
                  ]}
                />
              </label>
            </div>
          ) : (
            <label>
              AI prescreening seed
              <textarea
                value={aiPrescreeningSeed}
                onChange={(event) => onAiPrescreeningSeedChange(event.target.value)}
                placeholder="Optional. Leave empty for a fully random Russian-speaking patient each run."
              />
            </label>
          )}

          <label>
            Scenario seed
            <textarea
              value={scenarioSeed}
              onChange={(event) => onScenarioSeedChange(event.target.value)}
              placeholder="Optional direction for symptoms and backstory. Empty = model picks a fresh archetype."
            />
          </label>

          <p className="muted">
            Patient template is not used. Profile, archetype, and scenario are generated automatically for every run.
          </p>
        </section>

        <section className="surface modelSurface">
          <div className="sectionTitle">
            <span className="sectionIndex">02</span>
            <div>
              <h3>Models</h3>
              <small>Run-scoped overrides for any agent task</small>
            </div>
          </div>
          <ModelSettings
            modelConfig={modelConfig}
            selectedModelTask={selectedModelTask}
            draftModelConfig={draftModelConfig}
            onTaskChange={onModelTaskChange}
            onDraftChange={onDraftModelChange}
            onReset={onResetModel}
          />
        </section>

        <section className="surface actionSurface">
          <div className="sectionTitle">
            <span className="sectionIndex">03</span>
            <div>
              <h3>Execution</h3>
              <small>Create runs, drive patient turns, export evidence</small>
            </div>
          </div>

          <div className="buttonGrid">
            <button className="primaryAction" onClick={onCreate} disabled={busy}>Create session</button>
            <button className="primaryAction accent" onClick={onCreateBatch} disabled={busy}>Batch autotest</button>
            <button onClick={onRefreshTurns} disabled={!sandbox || busy}>Refresh turns</button>
            <button onClick={onStop} disabled={!sandbox || busy}>Stop run</button>
          </div>

          <label className="composer">
            Patient message
            <textarea
              value={sandboxMessage}
              placeholder="Type a patient message without Telegram..."
              onChange={(event) => onMessageChange(event.target.value)}
            />
          </label>

          <div className="buttonGrid">
            <button className="primaryAction" onClick={onSend} disabled={!sandbox || busy || !sandboxMessage.trim()}>Send message</button>
            <button onClick={onAutoRun} disabled={!sandbox || busy}>Auto patient</button>
            <button onClick={() => onExportRun('json')} disabled={!sandbox || busy}>Run JSON</button>
            <button onClick={() => onExportRun('md')} disabled={!sandbox || busy}>Run MD</button>
            <button onClick={() => onExportBatch('json')} disabled={!sandboxBatch || busy}>Batch JSON</button>
            <button onClick={() => onExportBatch('md')} disabled={!sandboxBatch || busy}>Batch MD</button>
          </div>
        </section>
      </div>

      <section className="surface transcriptSurface">
        <div className="sectionTitle">
          <span className="sectionIndex">04</span>
          <div>
            <h3>Transcript</h3>
            <small>Patient and psychologist turns with trace links</small>
          </div>
        </div>

        <div className="sandboxTurns">
          {sandboxTurns.length === 0 && (
            <div className="emptyState">
              <strong>No turns yet</strong>
              <span>Create a sandbox run, send a message, or start auto patient.</span>
            </div>
          )}
          {sandboxTurns.map((turn, index) => (
            <article key={`${turn.trace_id}-${index}`} className="sandboxTurnCard">
              <div className="turnMeta">
                <span>Turn {index + 1}</span>
                <span>{turn.latency_ms ?? 0} ms</span>
              </div>
              <div className="turnDialogue">
                <div className="bubble patientBubble">
                  <strong>Patient</strong>
                  <p>{turn.patient_message}</p>
                </div>
                <div className="bubble therapistBubble">
                  <strong>Psychologist</strong>
                  <p>{turn.assistant_message}</p>
                </div>
              </div>
              {turn.trace_id && (
                <button
                  className="traceButton"
                  onClick={() => onOpenTrace({
                    trace_id: turn.trace_id!,
                    turn_id: '',
                    status: 'sandbox',
                    channel: 'sandbox',
                    source: 'sandbox_ui',
                    duration_ms: turn.latency_ms ?? 0,
                    llm_latency_ms: 0,
                    total_tokens_input: 0,
                    total_tokens_output: 0,
                    started_at: new Date().toISOString(),
                  })}
                >
                  Open trace
                </button>
              )}
            </article>
          ))}
        </div>
      </section>

      <JudgeReportPanel
        sandbox={sandbox}
        batchRuns={sandboxBatchRuns}
        busy={busy}
        onRunJudge={onRunJudge}
        onSelectRun={onSelectBatchRun}
      />
    </section>
  );
}

function StatusPill({ label, value, tone }: { label: string; value: string; tone: 'ok' | 'accent' | 'idle' }) {
  return (
    <div className={`statusPill ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint: string }) {
  return (
    <article className="metricCard">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{hint}</small>
    </article>
  );
}
