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
  session_id: number;
  role: 'patient' | 'doctor';
  content: string;
  message_number: number;
  channel: 'telegram' | 'sandbox';
  trace_id?: string | null;
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
  sandbox_run_id?: number | null;
  sandbox_batch_id?: number | null;
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
  prompt_messages_full?: Array<Record<string, string>> | null;
  response?: string | null;
  response_full?: string | null;
  prompt_truncated: boolean;
  response_truncated: boolean;
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
  channel?: string | null;
  source?: string | null;
  sandbox_run_id?: number | null;
  sandbox_batch_id?: number | null;
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
  batch_id?: number | null;
  judge_result?: Record<string, unknown> | null;
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
  stop_reason?: string | null;
  patient_trace_id?: string | null;
  intake_completed?: boolean;
  closure_segments?: {
    therapist_closure?: string;
    extracted_summary?: string;
    completion_notice?: string;
  } | null;
};

export type SandboxBatchCreatePayload = {
  name: string;
  count: number;
  parallelism: number;
  max_turns_per_run: number;
  start_phase: 'prescreening' | 'intake' | 'therapy';
  prescreening_mode: 'manual' | 'ai_generated';
  patient_persona_source: 'generated' | 'manual' | 'legacy_template';
  seed?: string;
  model_overrides?: ModelOverrides;
};

export type SandboxBatchResponse = {
  batch_id: number;
  name: string;
  status: string;
  requested_count: number;
  parallelism: number;
  max_turns_per_run: number;
  created_runs: number;
  model_config?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  started_at?: string | null;
  finished_at?: string | null;
  stop_reason?: string | null;
};

export type ClinicalCardResponse = {
  session_id: number;
  account_id: number;
  display_name?: string | null;
  age?: string | null;
  sex_display?: string | null;
  has_data: boolean;
  initial_info_insufficient: boolean;
  fields: Record<string, string>;
  summary_text?: string | null;
};

export type SandboxJudgeQualitySection = {
  score?: number;
  findings?: string[];
  good_examples?: string[];
  bad_examples?: string[];
};

export type SandboxJudgeExtractionQuality = {
  score?: number;
  findings?: string[];
  missing_in_card?: string[];
  hallucinated_in_card?: string[];
};

export type SandboxJudgeBottleneck = {
  turn_number?: number;
  component?: string;
  issue?: string;
  evidence?: string;
  severity?: 'low' | 'medium' | 'high';
};

export type SandboxJudgeResult = {
  overall_score?: number;
  overall_verdict?: 'pass' | 'needs_review' | 'fail';
  therapist_quality?: SandboxJudgeQualitySection;
  extraction_quality?: SandboxJudgeExtractionQuality;
  contextuality?: { score?: number; findings?: string[] };
  psychologist_liveness?: { score?: number; findings?: string[] };
  architecture_bottlenecks?: SandboxJudgeBottleneck[];
  latency_notes?: string[];
  diversity_notes?: string[];
  recommended_fixes?: string[];
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
