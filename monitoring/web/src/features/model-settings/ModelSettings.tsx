import type { EffectiveModelConfig, GenerationConfig } from '../../types';

type Props = {
  modelConfig: EffectiveModelConfig | null;
  selectedModelTask: string;
  draftModelConfig: GenerationConfig | null;
  onTaskChange: (task: string) => void;
  onDraftChange: (config: GenerationConfig) => void;
  onReset: () => void;
};

export function ModelSettings({
  modelConfig,
  selectedModelTask,
  draftModelConfig,
  onTaskChange,
  onDraftChange,
  onReset,
}: Props) {
  return (
    <section className="modelSettings">
      <h3>Model Settings</h3>
      <label>
        Agent task
        <select value={selectedModelTask} onChange={(event) => onTaskChange(event.target.value)}>
          {modelConfig && Object.entries(modelConfig.agents).flatMap(([agent, tasks]) =>
            Object.keys(tasks).map((task) => (
              <option key={`${agent}.${task}`} value={`${agent}.${task}`}>
                {agent}.{task}
              </option>
            )),
          )}
        </select>
      </label>
      {draftModelConfig && (
        <div className="settingsGrid">
          <label>
            Model
            <input
              value={draftModelConfig.model}
              onChange={(event) => onDraftChange({ ...draftModelConfig, model: event.target.value })}
            />
          </label>
          <NumberField label="Temperature" value={draftModelConfig.temperature} step="0.01" onChange={(temperature) => onDraftChange({ ...draftModelConfig, temperature: temperature ?? draftModelConfig.temperature })} />
          <NumberField label="Max tokens" value={draftModelConfig.max_tokens} onChange={(max_tokens) => onDraftChange({ ...draftModelConfig, max_tokens: max_tokens ?? draftModelConfig.max_tokens })} />
          <NumberField label="Top-p" value={draftModelConfig.top_p ?? ''} step="0.01" onChange={(top_p) => onDraftChange({ ...draftModelConfig, top_p })} />
          <NumberField label="Frequency penalty" value={draftModelConfig.frequency_penalty ?? ''} step="0.01" onChange={(frequency_penalty) => onDraftChange({ ...draftModelConfig, frequency_penalty })} />
          <NumberField label="Presence penalty" value={draftModelConfig.presence_penalty ?? ''} step="0.01" onChange={(presence_penalty) => onDraftChange({ ...draftModelConfig, presence_penalty })} />
          <button onClick={onReset}>Reset to config defaults</button>
        </div>
      )}
    </section>
  );
}

type NumberFieldProps = {
  label: string;
  value: number | '';
  step?: string;
  onChange: (value: number | null) => void;
};

function NumberField({ label, value, step, onChange }: NumberFieldProps) {
  return (
    <label>
      {label}
      <input
        type="number"
        step={step}
        value={value}
        onChange={(event) => onChange(event.target.value === '' ? null : Number(event.target.value))}
      />
    </label>
  );
}
