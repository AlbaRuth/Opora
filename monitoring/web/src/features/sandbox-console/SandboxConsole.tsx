import type { PatientTemplate, SandboxPrescreeningProfile, SandboxSessionResponse, SandboxTurnResponse, TraceSummary } from '../../types';
import { ModelSettings } from '../model-settings/ModelSettings';
import type { EffectiveModelConfig, GenerationConfig } from '../../types';

type Props = {
  templates: PatientTemplate[];
  selectedTemplateId?: number;
  startPhase: 'prescreening' | 'intake' | 'therapy';
  prescreeningMode: 'manual' | 'ai_generated';
  manualProfile: SandboxPrescreeningProfile;
  aiPrescreeningSeed: string;
  scenarioSeed: string;
  autoRunTurns: number;
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
  onMessageChange: (message: string) => void;
  onCreate: () => void;
  onSend: () => void;
  onAutoRun: () => void;
  onStop: () => void;
  onRefreshTurns: () => void;
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
  onMessageChange,
  onCreate,
  onSend,
  onAutoRun,
  onStop,
  onRefreshTurns,
  onOpenTrace,
  onModelTaskChange,
  onDraftModelChange,
  onResetModel,
}: Props) {
  const selectedTemplate = templates.find((template) => template.id === selectedTemplateId);

  return (
    <section className="panel sandbox">
      <div className="panelHeader">
        <h2>Sandbox</h2>
        {sandbox && <small>Run #{sandbox.run_id} · {sandbox.status}</small>}
      </div>
      <ModelSettings
        modelConfig={modelConfig}
        selectedModelTask={selectedModelTask}
        draftModelConfig={draftModelConfig}
        onTaskChange={onModelTaskChange}
        onDraftChange={onDraftModelChange}
        onReset={onResetModel}
      />
      <div className="settingsGrid">
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
      </div>
      {prescreeningMode === 'manual' ? (
        <div className="settingsGrid">
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
          <textarea value={aiPrescreeningSeed} onChange={(event) => onAiPrescreeningSeedChange(event.target.value)} />
        </label>
      )}
      <label>
        Scenario seed
        <textarea value={scenarioSeed} onChange={(event) => onScenarioSeedChange(event.target.value)} />
      </label>
      <label>
        Шаблон пациента
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
          <strong>{selectedTemplate.name}</strong>
          <p>{selectedTemplate.presenting_problem}</p>
          {selectedTemplate.persona && <small>{selectedTemplate.persona}</small>}
        </article>
      )}
      <div className="row">
        <button onClick={onCreate} disabled={busy}>Создать sandbox-сессию</button>
        <button onClick={onRefreshTurns} disabled={!sandbox || busy}>История</button>
        <button onClick={onStop} disabled={!sandbox || busy}>Stop</button>
      </div>
      <textarea
        value={sandboxMessage}
        placeholder="Сообщение пациента без Telegram"
        onChange={(event) => onMessageChange(event.target.value)}
      />
      <div className="row">
        <button onClick={onSend} disabled={!sandbox || busy || !sandboxMessage.trim()}>Отправить</button>
        <button onClick={onAutoRun} disabled={!sandbox || busy}>Auto patient</button>
      </div>
      {busy && <p className="muted">LLM выполняет ход...</p>}
      <div className="sandboxTurns">
        {sandboxTurns.map((turn, index) => (
          <article key={`${turn.trace_id}-${index}`} className="message sandboxTurn">
            <strong>Пациент</strong>
            <p>{turn.patient_message}</p>
            <strong>Ответ модели</strong>
            <p>{turn.assistant_message}</p>
            <small>{turn.latency_ms ?? 0} ms</small>
            {turn.trace_id && (
              <button
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
                Открыть trace
              </button>
            )}
          </article>
        ))}
      </div>
    </section>
  );
}
