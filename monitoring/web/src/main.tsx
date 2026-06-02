import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { ChatBrowser } from './features/chat-browser/ChatBrowser';
import { DialogPanel } from './features/dialog/DialogPanel';
import { SandboxConsole } from './features/sandbox-console/SandboxConsole';
import { TraceExplorer } from './features/trace-explorer/TraceExplorer';
import './styles.css';
import type {
  ChatSummary,
  EffectiveModelConfig,
  GenerationConfig,
  MessageItem,
  ModelOverrides,
  PatientTemplate,
  SandboxPrescreeningProfile,
  SandboxSessionResponse,
  SandboxTurnResponse,
  TraceDetail,
  TraceSummary,
} from './types';

function App() {
  const [source, setSource] = useState<string>('');
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [traceDetail, setTraceDetail] = useState<TraceDetail | null>(null);
  const [templates, setTemplates] = useState<PatientTemplate[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | undefined>();
  const [sandboxStartPhase, setSandboxStartPhase] = useState<'prescreening' | 'intake' | 'therapy'>('intake');
  const [prescreeningMode, setPrescreeningMode] = useState<'manual' | 'ai_generated'>('manual');
  const [aiPrescreeningSeed, setAiPrescreeningSeed] = useState('');
  const [scenarioSeed, setScenarioSeed] = useState('');
  const [autoRunTurns, setAutoRunTurns] = useState(3);
  const [manualProfile, setManualProfile] = useState<SandboxPrescreeningProfile>({
    patient_name: 'Sandbox Пациент',
    patient_age: 32,
    patient_sex: 'prefer_not_to_say',
    address_mode: 'formal',
    therapist_name: 'Опора',
    therapist_gender: 'female',
    therapist_styles: ['friendly'],
  });
  const [modelConfig, setModelConfig] = useState<EffectiveModelConfig | null>(null);
  const [selectedModelTask, setSelectedModelTask] = useState('therapist.generate_response');
  const [draftModelConfig, setDraftModelConfig] = useState<GenerationConfig | null>(null);
  const [sandbox, setSandbox] = useState<SandboxSessionResponse | null>(null);
  const [sandboxMessage, setSandboxMessage] = useState('');
  const [sandboxTurns, setSandboxTurns] = useState<SandboxTurnResponse[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [chatLoading, setChatLoading] = useState(false);
  const [workspaceLoading, setWorkspaceLoading] = useState(false);
  const [traceLoading, setTraceLoading] = useState(false);
  const [sandboxBusy, setSandboxBusy] = useState(false);

  async function loadChats(nextSource = source) {
    setChatLoading(true);
    setError(null);
    try {
      setChats(await api.chats(nextSource || undefined));
    } catch (err) {
      setError(String(err));
    } finally {
      setChatLoading(false);
    }
  }

  async function selectChat(chat: ChatSummary) {
    setWorkspaceLoading(true);
    setSelectedChat(chat);
    setTraceDetail(null);
    setError(null);
    try {
      const [nextMessages, nextTraces] = await Promise.all([
        api.messages(chat.session_id),
        api.traces(chat.session_id),
      ]);
      setMessages(nextMessages);
      setTraces(nextTraces);
    } catch (err) {
      setError(String(err));
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function selectTrace(trace: TraceSummary) {
    setTraceLoading(true);
    setError(null);
    try {
      setTraceDetail(await api.traceDetail(trace.trace_id));
    } catch (err) {
      setError(String(err));
    } finally {
      setTraceLoading(false);
    }
  }

  async function createSandbox() {
    setSandboxBusy(true);
    setError(null);
    try {
      const created = await api.createSandbox({
        name: 'UI sandbox run',
        patient_template_id: selectedTemplateId ?? templates[0]?.id,
        start_phase: sandboxStartPhase,
        prescreening_mode: prescreeningMode,
        manual_prescreening_profile: prescreeningMode === 'manual' ? manualProfile : undefined,
        ai_prescreening_seed: aiPrescreeningSeed,
        scenario_seed: scenarioSeed,
        patient_persona_source: 'generated',
        model_overrides: currentOverrides(),
      });
      setSandbox(created);
      setSandboxTurns([]);
      setSource('sandbox');
      await loadChats('sandbox');
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function sendSandbox() {
    if (!sandbox || !sandboxMessage.trim()) return;
    setSandboxBusy(true);
    setError(null);
    try {
      const turn = await api.sendSandboxMessage(
        sandbox.run_id,
        sandboxMessage.trim(),
        currentOverrides(),
      );
      setSandboxMessage('');
      setSandboxTurns((items) => [...items, turn]);
      await loadChats('sandbox');
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function runAutoPatient() {
    if (!sandbox) return;
    setSandboxBusy(true);
    setError(null);
    try {
      const turns = await api.autoRun(sandbox.run_id, autoRunTurns, currentOverrides());
      setSandboxTurns((items) => [...items, ...turns]);
      await loadChats('sandbox');
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function stopSandbox() {
    if (!sandbox) return;
    setSandboxBusy(true);
    setError(null);
    try {
      setSandbox(await api.stopSandbox(sandbox.run_id));
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function refreshSandboxTurns() {
    if (!sandbox) return;
    setSandboxBusy(true);
    setError(null);
    try {
      setSandboxTurns(await api.sandboxTurns(sandbox.run_id));
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  function currentOverrides(): ModelOverrides | undefined {
    if (!draftModelConfig) return undefined;
    const [agent, task] = selectedModelTask.split('.');
    return {
      [agent]: {
        [task]: {
          ...draftModelConfig,
          config_source: 'sandbox_run_override',
        },
      },
    };
  }

  function resetDraftFromDefaults(nextTask = selectedModelTask) {
    const [agent, task] = nextTask.split('.');
    const defaults = modelConfig?.agents[agent]?.[task];
    setDraftModelConfig(defaults ? { ...defaults } : null);
  }

  function changeModelTask(nextTask: string) {
    setSelectedModelTask(nextTask);
    resetDraftFromDefaults(nextTask);
  }

  useEffect(() => {
    loadChats();
    api.templates()
      .then((items) => {
        setTemplates(items);
        setSelectedTemplateId(items[0]?.id);
      })
      .catch((err) => setError(String(err)));
    api.modelConfig()
      .then((config) => {
        setModelConfig(config);
        const defaults = config.agents.therapist?.generate_response;
        if (defaults) setDraftModelConfig({ ...defaults });
      })
      .catch((err) => setError(String(err)));
  }, []);

  return (
    <main className="layout">
      <ChatBrowser
        source={source}
        chats={chats}
        selectedChat={selectedChat}
        loading={chatLoading}
        error={error}
        onSourceChange={(nextSource) => {
          setSource(nextSource);
          loadChats(nextSource);
        }}
        onRefresh={() => loadChats()}
        onSelect={selectChat}
      />
      <section className="content">
        <DialogPanel selectedChat={selectedChat} messages={messages} loading={workspaceLoading} />
        <TraceExplorer
          traces={traces}
          traceDetail={traceDetail}
          loading={traceLoading}
          onSelectTrace={selectTrace}
        />
        <SandboxConsole
          templates={templates}
          selectedTemplateId={selectedTemplateId}
          startPhase={sandboxStartPhase}
          prescreeningMode={prescreeningMode}
          manualProfile={manualProfile}
          aiPrescreeningSeed={aiPrescreeningSeed}
          scenarioSeed={scenarioSeed}
          autoRunTurns={autoRunTurns}
          sandbox={sandbox}
          sandboxMessage={sandboxMessage}
          sandboxTurns={sandboxTurns}
          busy={sandboxBusy}
          modelConfig={modelConfig}
          selectedModelTask={selectedModelTask}
          draftModelConfig={draftModelConfig}
          onTemplateChange={setSelectedTemplateId}
          onStartPhaseChange={setSandboxStartPhase}
          onPrescreeningModeChange={setPrescreeningMode}
          onManualProfileChange={setManualProfile}
          onAiPrescreeningSeedChange={setAiPrescreeningSeed}
          onScenarioSeedChange={setScenarioSeed}
          onAutoRunTurnsChange={setAutoRunTurns}
          onMessageChange={setSandboxMessage}
          onCreate={createSandbox}
          onSend={sendSandbox}
          onAutoRun={runAutoPatient}
          onStop={stopSandbox}
          onRefreshTurns={refreshSandboxTurns}
          onOpenTrace={selectTrace}
          onModelTaskChange={changeModelTask}
          onDraftModelChange={setDraftModelConfig}
          onResetModel={() => resetDraftFromDefaults()}
        />
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
