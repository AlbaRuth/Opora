export type ChatSummary = {
  session_id: number;
  account_id: number;
  telegram_id: number;
  username?: string | null;
  display_name?: string | null;
  source: 'telegram' | 'sandbox';
  session_number: number;
  therapy_type: string;
  is_active: boolean;
  dialog_count: number;
  created_at: string;
  updated_at: string;
};

export type MessageItem = {
  id: number;
  role: 'patient' | 'doctor';
  content: string;
  message_number: number;
  primary_emotion?: string | null;
  emotional_intensity?: number | null;
  created_at: string;
};

export type TraceSummary = {
  trace_id: string;
  turn_id: string;
  session_id?: number | null;
  account_id?: number | null;
  status: string;
  channel: string;
  source: string;
  duration_ms?: number | null;
  llm_latency_ms: number;
  total_tokens_input: number;
  total_tokens_output: number;
  total_cost_usd?: number | null;
  started_at: string;
  finished_at?: string | null;
  error_message?: string | null;
};

export type LlmCallItem = {
  id: number;
  agent_type: string;
  task_name: string;
  model: string;
  temperature: number;
  max_tokens: number;
  prompt?: string | null;
  prompt_messages?: Array<Record<string, string>> | null;
  response?: string | null;
  reasoning?: string | null;
  reasoning_summary?: string | null;
  latency_ms?: number | null;
  tokens_input?: number | null;
  tokens_output?: number | null;
  cost_usd?: number | null;
  success: boolean;
  error_message?: string | null;
  metadata?: Record<string, unknown> | null;
  provider_metadata?: Record<string, unknown> | null;
  created_at: string;
};

export type TraceDetail = {
  trace: TraceSummary;
  llm_calls: LlmCallItem[];
};

export type GenerationConfig = {
  model: string;
  temperature: number;
  max_tokens: number;
  top_p?: number | null;
  frequency_penalty?: number | null;
  presence_penalty?: number | null;
  config_source?: string;
};

export type ModelOverrides = Record<string, Record<string, Partial<GenerationConfig>>>;

export type EffectiveModelConfig = {
  provider: Record<string, unknown>;
  agents: Record<string, Record<string, GenerationConfig>>;
  logging: Record<string, unknown>;
  sandbox: Record<string, unknown>;
};

export type SandboxSessionResponse = {
  run_id: number;
  account_id: number;
  session_id: number;
  status: string;
  start_phase?: 'prescreening' | 'intake' | 'therapy' | null;
  prescreening_mode?: 'manual' | 'ai_generated' | null;
  generated_prescreening_profile?: Record<string, unknown> | null;
  generated_scenario?: Record<string, unknown> | null;
  effective_model_config?: EffectiveModelConfig | null;
};

export type SandboxPrescreeningProfile = {
  patient_name: string;
  patient_age?: number | null;
  patient_sex: 'male' | 'female' | 'prefer_not_to_say';
  address_mode: 'formal' | 'informal';
  therapist_name: string;
  therapist_gender: 'female' | 'male';
  therapist_styles: string[];
};

export type SandboxCreatePayload = {
  name: string;
  patient_template_id?: number;
  start_phase: 'prescreening' | 'intake' | 'therapy';
  prescreening_mode: 'manual' | 'ai_generated';
  manual_prescreening_profile?: SandboxPrescreeningProfile;
  ai_prescreening_seed?: string;
  scenario_seed?: string;
  patient_persona_source: 'generated' | 'manual' | 'legacy_template';
  model_overrides?: ModelOverrides;
};

export type SandboxTurnResponse = {
  run_id: number;
  trace_id?: string | null;
  patient_message: string;
  assistant_message: string;
  latency_ms?: number | null;
  metadata?: Record<string, unknown> | null;
};

export type PatientTemplate = {
  id: number;
  name: string;
  version: number;
  persona: string;
  presenting_problem: string;
  hidden_facts?: string[];
  emotional_trajectory?: string | null;
  cooperation_level?: string;
  safety_boundaries?: string[];
  max_turns: number;
  stop_conditions?: string[];
};
