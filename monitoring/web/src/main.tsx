import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { api } from './api';
import { ChatBrowser } from './features/chat-browser/ChatBrowser';
import { ConversationPanel } from './features/conversation/ConversationPanel';
import { SandboxConsole } from './features/sandbox-console/SandboxConsole';
import './styles.css';
import type {
  ChatSummary,
  ClinicalCardResponse,
  EffectiveModelConfig,
  GenerationConfig,
  MessageItem,
  ModelOverrides,
  SandboxBatchResponse,
  SandboxPrescreeningProfile,
  SandboxJudgeResult,
  SandboxSessionResponse,
  SandboxTurnResponse,
  TraceDetail,
  TraceSummary,
} from './types';

type WorkspaceTab = 'conversation' | 'sandbox';

function App() {
  const [source, setSource] = useState<string>('');
  const [workspaceTab, setWorkspaceTab] = useState<WorkspaceTab>('conversation');
  const [chats, setChats] = useState<ChatSummary[]>([]);
  const [selectedChat, setSelectedChat] = useState<ChatSummary | null>(null);
  const [messages, setMessages] = useState<MessageItem[]>([]);
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [traceDetail, setTraceDetail] = useState<TraceDetail | null>(null);
  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [sandboxStartPhase, setSandboxStartPhase] = useState<'prescreening' | 'intake' | 'therapy'>('intake');
  const [prescreeningMode, setPrescreeningMode] = useState<'manual' | 'ai_generated'>('ai_generated');
  const [aiPrescreeningSeed, setAiPrescreeningSeed] = useState('');
  const [scenarioSeed, setScenarioSeed] = useState('');
  const [autoRunTurns, setAutoRunTurns] = useState(3);
  const [batchCount, setBatchCount] = useState(20);
  const [batchParallelism, setBatchParallelism] = useState(5);
  const [sandboxBatch, setSandboxBatch] = useState<SandboxBatchResponse | null>(null);
  const [sandboxBatchRuns, setSandboxBatchRuns] = useState<SandboxSessionResponse[]>([]);
  const [manualProfile, setManualProfile] = useState<SandboxPrescreeningProfile>({
    patient_name: 'Sandbox Patient',
    patient_age: 32,
    patient_sex: 'prefer_not_to_say',
    address_mode: 'formal',
    therapist_name: 'Opora',
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
  const [clinicalCard, setClinicalCard] = useState<ClinicalCardResponse | null>(null);
  const [clinicalCardLoading, setClinicalCardLoading] = useState(false);
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

  async function loadClinicalCard(sessionId: number) {
    setClinicalCardLoading(true);
    try {
      setClinicalCard(await api.clinicalCard(sessionId));
    } catch {
      setClinicalCard(null);
    } finally {
      setClinicalCardLoading(false);
    }
  }

  async function refreshSandboxSession(runId: number) {
    const updated = await api.getSandboxSession(runId);
    setSandbox(updated);
    setSandboxBatchRuns((runs) =>
      runs.map((run) => (run.run_id === updated.run_id ? updated : run)),
    );
    return updated;
  }

  async function loadChatWorkspace(chat: ChatSummary) {
    setWorkspaceLoading(true);
    setError(null);
    try {
      const [nextMessages, nextTraces] = await Promise.all([
        api.messages(chat.session_id),
        api.traces(chat.session_id),
      ]);
      setMessages(nextMessages);
      setTraces(nextTraces);
      if (chat.source === 'sandbox') {
        const runId = nextTraces.find((trace) => trace.sandbox_run_id)?.sandbox_run_id;
        if (runId) {
          setSandboxTurns(await api.sandboxTurns(runId));
          try {
            setSandbox(await api.getSandboxSession(runId));
          } catch {
            /* session metadata optional when browsing history */
          }
        } else {
          setSandboxTurns([]);
        }
      }
      await loadClinicalCard(chat.session_id);
    } catch (err) {
      setError(String(err));
    } finally {
      setWorkspaceLoading(false);
    }
  }

  async function openLatestDoctorTrace(sessionId: number) {
    const nextMessages = await api.messages(sessionId);
    const latestDoctorTrace = [...nextMessages]
      .reverse()
      .find((message) => message.role === 'doctor' && message.trace_id);
    if (latestDoctorTrace?.trace_id) {
      await openTrace(latestDoctorTrace.trace_id);
    }
  }

  async function selectChat(chat: ChatSummary) {
    setWorkspaceTab('conversation');
    setSelectedChat(chat);
    setTraceDetail(null);
    setSelectedTraceId(null);
    setTraces([]);
    await loadChatWorkspace(chat);
  }

  async function focusSession(sessionId: number, nextSource = 'sandbox') {
    setSource(nextSource);
    await loadChats(nextSource);
    const chat = await api.chat(sessionId);
    await selectChat(chat);
  }

  async function refreshSelectedChat() {
    if (!selectedChat) return;
    await loadChatWorkspace(selectedChat);
  }

  async function openTrace(traceId: string) {
    setWorkspaceTab('conversation');
    setSelectedTraceId(traceId);
    setTraceLoading(true);
    setError(null);
    try {
      setTraceDetail(await api.traceDetail(traceId));
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
      await focusSession(created.session_id, 'sandbox');
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
      if (selectedChat?.session_id === sandbox.session_id) {
        await refreshSelectedChat();
      } else {
        await focusSession(sandbox.session_id, 'sandbox');
      }
      if (turn.trace_id) {
        await openTrace(turn.trace_id);
      }
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
      await refreshSandboxSession(sandbox.run_id);
      await loadClinicalCard(sandbox.session_id);
      await loadChats('sandbox');
      if (selectedChat?.session_id === sandbox.session_id) {
        await refreshSelectedChat();
      } else {
        await focusSession(sandbox.session_id, 'sandbox');
      }
      const lastTrace = [...turns].reverse().find((turn) => turn.trace_id)?.trace_id;
      if (lastTrace) {
        await openTrace(lastTrace);
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function createSandboxBatch() {
    setSandboxBusy(true);
    setError(null);
    try {
      const batch = await api.createSandboxBatch({
        name: 'UI sandbox batch',
        count: batchCount,
        parallelism: batchParallelism,
        max_turns_per_run: autoRunTurns,
        start_phase: sandboxStartPhase,
        prescreening_mode: 'ai_generated',
        patient_persona_source: 'generated',
        seed: aiPrescreeningSeed || scenarioSeed,
        model_overrides: currentOverrides(),
      });
      setSandboxBatch(batch);
      const runs = await api.sandboxBatchRuns(batch.batch_id);
      setSandboxBatchRuns(runs);
      if (runs[0]) {
        setSandbox(runs[0]);
        setSandboxTurns(await api.sandboxTurns(runs[0].run_id));
        await focusSession(runs[0].session_id, 'sandbox');
        await openLatestDoctorTrace(runs[0].session_id);
      } else {
        setSource('sandbox');
        await loadChats('sandbox');
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function exportCurrentRun(format: 'json' | 'md') {
    if (!sandbox) return;
    const data = await api.exportSandboxRun(sandbox.run_id, format);
    downloadExport(`sandbox-run-${sandbox.run_id}.${format}`, data, format);
  }

  async function exportCurrentBatch(format: 'json' | 'md') {
    if (!sandboxBatch) return;
    const data = await api.exportSandboxBatch(sandboxBatch.batch_id, format);
    downloadExport(`sandbox-batch-${sandboxBatch.batch_id}.${format}`, data, format);
  }

  function downloadExport(filename: string, data: unknown, format: 'json' | 'md') {
    const body = typeof data === 'string' ? data : JSON.stringify(data, null, 2);
    const blob = new Blob([body], { type: format === 'md' ? 'text/markdown' : 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = filename;
    link.click();
    URL.revokeObjectURL(url);
  }

  async function runJudge() {
    if (!sandbox) return;
    setSandboxBusy(true);
    setError(null);
    try {
      const updated = await api.judgeSandbox(sandbox.run_id);
      setSandbox(updated);
      setSandboxBatchRuns((runs) =>
        runs.map((run) => (run.run_id === updated.run_id ? updated : run)),
      );
      if (selectedChat?.session_id === updated.session_id) {
        await refreshSelectedChat();
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setSandboxBusy(false);
    }
  }

  async function selectBatchRun(run: SandboxSessionResponse) {
    setSandbox(run);
    setSandboxBusy(true);
    setError(null);
    try {
      setSandboxTurns(await api.sandboxTurns(run.run_id));
      await focusSession(run.session_id, 'sandbox');
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
      await refreshSelectedChat();
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
      <section className="workspace">
        <nav className="workspaceTabs" aria-label="Workspace">
          <button
            type="button"
            className={workspaceTab === 'conversation' ? 'workspaceTab active' : 'workspaceTab'}
            aria-selected={workspaceTab === 'conversation'}
            onClick={() => setWorkspaceTab('conversation')}
          >
            Conversation
          </button>
          <button
            type="button"
            className={workspaceTab === 'sandbox' ? 'workspaceTab active' : 'workspaceTab'}
            aria-selected={workspaceTab === 'sandbox'}
            onClick={() => setWorkspaceTab('sandbox')}
          >
            Sandbox
          </button>
        </nav>
        <div className="workspaceBody">
          {workspaceTab === 'conversation' && (
            <ConversationPanel
              selectedChat={selectedChat}
              messages={messages}
              traces={traces}
              sandboxTurns={sandboxTurns}
              traceDetail={traceDetail}
              selectedTraceId={selectedTraceId}
              clinicalCard={clinicalCard}
              clinicalCardLoading={clinicalCardLoading}
              loading={workspaceLoading}
              traceLoading={traceLoading}
              judgeResult={(sandbox?.judge_result ?? null) as SandboxJudgeResult | null}
              judgeBusy={sandboxBusy}
              onOpenTrace={openTrace}
              onCloseTrace={() => {
                setTraceDetail(null);
                setSelectedTraceId(null);
              }}
              onRunJudge={sandbox ? runJudge : undefined}
              onOpenJudgeReport={() => setWorkspaceTab('sandbox')}
            />
          )}
          {workspaceTab === 'sandbox' && (
            <SandboxConsole
              startPhase={sandboxStartPhase}
              prescreeningMode={prescreeningMode}
              manualProfile={manualProfile}
              aiPrescreeningSeed={aiPrescreeningSeed}
              scenarioSeed={scenarioSeed}
              autoRunTurns={autoRunTurns}
              batchCount={batchCount}
              batchParallelism={batchParallelism}
              sandboxBatch={sandboxBatch}
              sandboxBatchRuns={sandboxBatchRuns}
              sandbox={sandbox}
              sandboxMessage={sandboxMessage}
              sandboxTurns={sandboxTurns}
              busy={sandboxBusy}
              modelConfig={modelConfig}
              selectedModelTask={selectedModelTask}
              draftModelConfig={draftModelConfig}
              onStartPhaseChange={setSandboxStartPhase}
              onPrescreeningModeChange={setPrescreeningMode}
              onManualProfileChange={setManualProfile}
              onAiPrescreeningSeedChange={setAiPrescreeningSeed}
              onScenarioSeedChange={setScenarioSeed}
              onAutoRunTurnsChange={setAutoRunTurns}
              onBatchCountChange={setBatchCount}
              onBatchParallelismChange={setBatchParallelism}
              onMessageChange={setSandboxMessage}
              onCreate={createSandbox}
              onCreateBatch={createSandboxBatch}
              onSend={sendSandbox}
              onAutoRun={runAutoPatient}
              onStop={stopSandbox}
              onRefreshTurns={refreshSandboxTurns}
              onExportRun={exportCurrentRun}
              onExportBatch={exportCurrentBatch}
              onOpenTrace={(trace) => openTrace(trace.trace_id)}
              onRunJudge={runJudge}
              onSelectBatchRun={selectBatchRun}
              onModelTaskChange={changeModelTask}
              onDraftModelChange={setDraftModelConfig}
              onResetModel={() => resetDraftFromDefaults()}
            />
          )}
        </div>
      </section>
    </main>
  );
}

createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
