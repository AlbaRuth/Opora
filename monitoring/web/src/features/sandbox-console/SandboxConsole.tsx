import type {
  EffectiveModelConfig,
  GenerationConfig,
  PatientTemplate,
  SandboxBatchResponse,
  SandboxPrescreeningProfile,
  SandboxSessionResponse,
  SandboxTurnResponse,
  TraceSummary,
} from '../../types';
import { ModelSettings } from '../model-settings/ModelSettings';

type Props = {
  templates: PatientTemplate[];
  selectedTemplateId?: number;
  startPhase: 'prescreening' | 'intake' | 'therapy';
  prescreeningMode: 'manual' | 'ai_generated';
  manualProfile: SandboxPrescreeningProfile;
  aiPrescreeningSeed: string;
  scenarioSeed: string;
  autoRunTurns: number;
  batchCount: number;
  batchParallelism: number;
  sandboxBatch: SandboxBatchResponse | null;
  sandbox: SandboxSessionResponse | null;
  sandboxMessage: string;
  sandboxTurns: SandboxTurnResponse[];
  busy: boolean;
  modelConfig: EffectiveModelConfig | null;
  selectedModelTask: string;
  draftModelConfig: GenerationConfig | null;
  onTemplateChange: (id: number) => void;
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
  onModelTaskChange: (task: string) => void;
  onDraftModelChange: (config: GenerationConfig) => void;
  onResetModel: () => void;
};

export function SandboxConsole({
  templates,
  selectedTemplateId,
  startPhase,
  prescreeningMode,
  manualProfile,
  aiPrescreeningSeed,
  scenarioSeed,
  autoRunTurns,
  batchCount,
  batchParallelism,
  sandboxBatch,
  sandbox,
  sandboxMessage,
  sandboxTurns,
  busy,
  modelConfig,
  selectedModelTask,
  draftModelConfig,
  onTemplateChange,
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
  onModelTaskChange,
  onDraftModelChange,
  onResetModel,
}: Props) {
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);
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
              <small>Profile, phase, and generation seeds</small>
            </div>
          </div>

          <div className="settingsGrid compact">
            <label>
              Start phase
              <select value={startPhase} onChange={(event) => onStartPhaseChange(event.target.value as 'prescreening' | 'intake' | 'therapy')}>
                <option value="prescreening">Prescreening</option>
                <option value="intake">Intake</option>
                <option value="therapy">Therapy</option>
              </select>
            </label>
            <label>
              Prescreening data
              <select value={prescreeningMode} onChange={(event) => onPrescreeningModeChange(event.target.value as 'manual' | 'ai_generated')}>
                <option value="manual">Manual</option>
                <option value="ai_generated">AI generated</option>
              </select>
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
                <select value={manualProfile.patient_sex} onChange={(event) => onManualProfileChange({ ...manualProfile, patient_sex: event.target.value as SandboxPrescreeningProfile['patient_sex'] })}>
                  <option value="prefer_not_to_say">Prefer not to say</option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </label>
              <label>
                Address
                <select value={manualProfile.address_mode} onChange={(event) => onManualProfileChange({ ...manualProfile, address_mode: event.target.value as SandboxPrescreeningProfile['address_mode'] })}>
                  <option value="formal">Formal</option>
                  <option value="informal">Informal</option>
                </select>
              </label>
              <label>
                Therapist name
                <input value={manualProfile.therapist_name} onChange={(event) => onManualProfileChange({ ...manualProfile, therapist_name: event.target.value })} />
              </label>
              <label>
                Therapist gender
                <select value={manualProfile.therapist_gender} onChange={(event) => onManualProfileChange({ ...manualProfile, therapist_gender: event.target.value as SandboxPrescreeningProfile['therapist_gender'] })}>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                </select>
              </label>
            </div>
          ) : (
            <label>
              AI prescreening seed
              <textarea value={aiPrescreeningSeed} onChange={(event) => onAiPrescreeningSeedChange(event.target.value)} placeholder="Optional seed to make the generated patient reproducible" />
            </label>
          )}

          <label>
            Scenario seed
            <textarea value={scenarioSeed} onChange={(event) => onScenarioSeedChange(event.target.value)} placeholder="Optional scenario seed for symptoms, tone, and background" />
          </label>

          <label>
            Patient template
            <select value={selectedTemplateId ?? ''} onChange={(event) => onTemplateChange(Number(event.target.value))}>
              {templates.map((template) => (
                <option key={template.id} value={template.id}>
                  {template.name} v{template.version}
                </option>
              ))}
            </select>
          </label>
          {selectedTemplate && (
            <article className="templatePreview">
              <div>
                <strong>{selectedTemplate.name}</strong>
                <span className="badge">v{selectedTemplate.version}</span>
              </div>
              <p>{selectedTemplate.presenting_problem}</p>
              {selectedTemplate.persona && <small>{selectedTemplate.persona}</small>}
            </article>
          )}
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
