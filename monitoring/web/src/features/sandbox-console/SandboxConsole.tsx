import type { PatientTemplate, SandboxSessionResponse, SandboxTurnResponse, TraceSummary } from '../../types';
import { ModelSettings } from '../model-settings/ModelSettings';
import type { EffectiveModelConfig, GenerationConfig } from '../../types';

type Props = {
  templates: PatientTemplate[];
  selectedTemplateId?: number;
  sandbox: SandboxSessionResponse | null;
  sandboxMessage: string;
  sandboxTurns: SandboxTurnResponse[];
  busy: boolean;
  modelConfig: EffectiveModelConfig | null;
  selectedModelTask: string;
  draftModelConfig: GenerationConfig | null;
  onTemplateChange: (id: number) => void;
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
  sandbox,
  sandboxMessage,
  sandboxTurns,
  busy,
  modelConfig,
  selectedModelTask,
  draftModelConfig,
  onTemplateChange,
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
        <button onClick={onAutoRun} disabled={!sandbox || busy}>Auto patient x3</button>
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
