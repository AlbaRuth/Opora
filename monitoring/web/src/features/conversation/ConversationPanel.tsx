import { useEffect, useMemo, useRef } from 'react';
import type {
  ChatSummary,
  ClinicalCardResponse,
  MessageItem,
  SandboxJudgeResult,
  SandboxTurnResponse,
  TraceDetail,
  TraceSummary,
} from '../../types';
import { ClinicalCardDrawer } from './ClinicalCardPanel';
import {
  buildTraceTurnMetaList,
  buildTurnTraceMap,
  groupMessagesIntoTurns,
  partitionTraces,
  type TurnTraceInfo,
} from './dialogueTurns';
import { TraceInspector } from './TraceInspector';

type Props = {
  selectedChat: ChatSummary | null;
  messages: MessageItem[];
  traces: TraceSummary[];
  sandboxTurns?: SandboxTurnResponse[];
  traceDetail: TraceDetail | null;
  selectedTraceId: string | null;
  clinicalCard: ClinicalCardResponse | null;
  clinicalCardLoading: boolean;
  loading: boolean;
  traceLoading: boolean;
  judgeResult?: SandboxJudgeResult | null;
  judgeBusy?: boolean;
  onOpenTrace: (traceId: string) => void;
  onCloseTrace: () => void;
  onRunJudge?: () => void;
  onOpenJudgeReport?: () => void;
};

function TraceActionButton({
  label,
  traceId,
  selectedTraceId,
  onOpenTrace,
}: {
  label: string;
  traceId: string | null;
  selectedTraceId: string | null;
  onOpenTrace: (traceId: string) => void;
}) {
  if (!traceId) {
    return (
      <button type="button" className="turnTraceButton disabled" disabled>
        {label}
      </button>
    );
  }

  return (
    <button
      type="button"
      className={traceId === selectedTraceId ? 'turnTraceButton active' : 'turnTraceButton'}
      onClick={() => onOpenTrace(traceId)}
    >
      {label}
    </button>
  );
}

function DoctorMessageContent({
  message,
  traceInfo,
  selectedTraceId,
  onOpenTrace,
}: {
  message: MessageItem;
  traceInfo: TurnTraceInfo | null;
  selectedTraceId: string | null;
  onOpenTrace: (traceId: string) => void;
}) {
  const psychologistTraceId =
    traceInfo?.psychologistTraceId ?? message.trace_id ?? null;
  const segments = traceInfo?.closureSegments;
  const isActive = psychologistTraceId && psychologistTraceId === selectedTraceId;

  if (traceInfo?.intakeCompleted && segments) {
    return (
      <div className={`doctorMessageSegments ${isActive ? 'traceActive' : ''}`}>
        <section className="closureSegment closureSegmentTherapist">
          {psychologistTraceId ? (
            <button
              type="button"
              className="messageContentButton"
              onClick={() => onOpenTrace(psychologistTraceId)}
            >
              {segments.therapist_closure ?? message.content}
            </button>
          ) : (
            <p className="messageContent">{segments.therapist_closure ?? message.content}</p>
          )}
        </section>
        {segments.extracted_summary && (
          <section className="closureSegment closureSegmentSummary">
            <span className="closureSegmentLabel">Extracted summary</span>
            <p className="messageContent">{segments.extracted_summary}</p>
          </section>
        )}
        {segments.completion_notice && (
          <section className="closureSegment closureSegmentNotice">
            <span className="closureSegmentLabel">Intake completed</span>
            <p className="messageContent">{segments.completion_notice}</p>
          </section>
        )}
        {psychologistTraceId && (
          <button
            type="button"
            className="traceLink"
            onClick={() => onOpenTrace(psychologistTraceId)}
          >
            View pipeline · agents & prompts
          </button>
        )}
      </div>
    );
  }

  const clickable = Boolean(psychologistTraceId);
  return (
    <>
      {clickable ? (
        <button
          type="button"
          className={`messageContentButton ${isActive ? 'traceActive' : ''}`}
          onClick={() => onOpenTrace(psychologistTraceId!)}
        >
          {message.content}
        </button>
      ) : (
        <p className="messageContent">{message.content}</p>
      )}
      {clickable && (
        <button
          type="button"
          className="traceLink"
          onClick={() => onOpenTrace(psychologistTraceId!)}
        >
          View pipeline · agents & prompts
        </button>
      )}
    </>
  );
}

function TurnMessage({
  message,
  role,
  traceInfo,
  selectedTraceId,
  onOpenTrace,
}: {
  message: MessageItem | null;
  role: 'patient' | 'doctor';
  traceInfo: TurnTraceInfo | null;
  selectedTraceId: string | null;
  onOpenTrace: (traceId: string) => void;
}) {
  const label = role === 'doctor' ? 'Psychologist' : 'Patient';

  if (!message) {
    return (
      <article className={`turnMessage ${role} empty`}>
        <div className="messageHeader">
          <strong>{label}</strong>
          <span>—</span>
        </div>
        <p className="messageContent muted">No message</p>
      </article>
    );
  }

  const patientTraceId = traceInfo?.patientTraceId ?? null;
  const isPatientActive = patientTraceId && patientTraceId === selectedTraceId;

  return (
    <article className={`turnMessage ${message.role}`}>
      <div className="messageHeader">
        <strong>{label}</strong>
        <span>#{message.message_number}</span>
      </div>
      {role === 'doctor' ? (
        <DoctorMessageContent
          message={message}
          traceInfo={traceInfo}
          selectedTraceId={selectedTraceId}
          onOpenTrace={onOpenTrace}
        />
      ) : patientTraceId ? (
        <button
          type="button"
          className={`messageContentButton ${isPatientActive ? 'traceActive' : ''}`}
          onClick={() => onOpenTrace(patientTraceId)}
        >
          {message.content}
        </button>
      ) : (
        <p className="messageContent">{message.content}</p>
      )}
      {role === 'patient' && patientTraceId && (
        <button type="button" className="traceLink" onClick={() => onOpenTrace(patientTraceId)}>
          View auto patient · prompt & response
        </button>
      )}
      {message.primary_emotion && (
        <small className="messageMeta">{message.primary_emotion}</small>
      )}
    </article>
  );
}

function formatJudgeScore(score?: number) {
  if (typeof score !== 'number') return null;
  return score.toFixed(1);
}

export function ConversationPanel({
  selectedChat,
  messages,
  traces,
  sandboxTurns = [],
  traceDetail,
  selectedTraceId,
  clinicalCard,
  clinicalCardLoading,
  loading,
  traceLoading,
  judgeResult,
  judgeBusy = false,
  onOpenTrace,
  onCloseTrace,
  onRunJudge,
  onOpenJudgeReport,
}: Props) {
  const turns = groupMessagesIntoTurns(messages);
  const turnRefs = useRef(new Map<number, HTMLElement>());
  const { dialogueTraces, setupTraces } = useMemo(() => partitionTraces(traces), [traces]);
  const headerTraces = useMemo(
    () => [...setupTraces, ...dialogueTraces].sort((a, b) => a.started_at.localeCompare(b.started_at)),
    [setupTraces, dialogueTraces],
  );
  const traceMetaById = useMemo(
    () => buildTraceTurnMetaList(messages, headerTraces),
    [messages, headerTraces],
  );
  const turnTraceMap = useMemo(() => buildTurnTraceMap(sandboxTurns), [sandboxTurns]);
  const showClinicalCard = Boolean(clinicalCard?.has_data || clinicalCardLoading);
  const isSandbox = selectedChat?.source === 'sandbox';
  const activeTurnIndex = selectedTraceId
    ? traceMetaById.get(selectedTraceId)?.turnIndex ?? null
    : null;
  const judgeScore = formatJudgeScore(judgeResult?.overall_score);

  useEffect(() => {
    if (!selectedTraceId || loading || !activeTurnIndex) return;
    const element = turnRefs.current.get(activeTurnIndex);
    if (!element) return;
    requestAnimationFrame(() => {
      element.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
  }, [selectedTraceId, activeTurnIndex, loading]);

  return (
    <section className={`panel conversationPanel ${traceDetail ? 'withInspector' : ''}`}>
      <div className="panelHeader conversationPanelHeader">
        <div>
          <h2>Conversation</h2>
          {selectedChat && (
            <small>
              {selectedChat.display_name || selectedChat.username || selectedChat.telegram_id}
              {' · '}
              {selectedChat.source} / session #{selectedChat.session_number}
            </small>
          )}
          {selectedChat && headerTraces.length > 0 && (
            <div className="traceListBar">
              {headerTraces.map((trace) => {
                const meta = traceMetaById.get(trace.trace_id);
                return (
                  <button
                    key={trace.trace_id}
                    type="button"
                    className={trace.trace_id === selectedTraceId ? 'traceChip active' : 'traceChip'}
                    onClick={() => onOpenTrace(trace.trace_id)}
                  >
                    {meta?.label ?? 'Trace'}
                    {' · '}
                    {trace.status}
                    {' · '}
                    {trace.total_tokens_input + trace.total_tokens_output} tok
                  </button>
                );
              })}
            </div>
          )}
        </div>
        <div className="conversationPanelHeaderAside">
          {selectedChat && (
            <span className="badge">
              {selectedChat.dialog_count} turns · {headerTraces.length} dialogue traces
            </span>
          )}
          {isSandbox && onRunJudge && (
            <div className="judgeActionBar">
              <button
                type="button"
                className="judgeActionButton"
                onClick={onRunJudge}
                disabled={judgeBusy}
              >
                {judgeBusy ? 'Running judge…' : 'LLM Judge'}
              </button>
              {judgeScore && (
                <button
                  type="button"
                  className="judgeScoreBadge"
                  onClick={onOpenJudgeReport}
                  title="Open judge report"
                >
                  {judgeScore} · {judgeResult?.overall_verdict ?? '—'}
                </button>
              )}
            </div>
          )}
        </div>
      </div>

      {showClinicalCard && (
        <ClinicalCardDrawer
          card={clinicalCard}
          loading={clinicalCardLoading}
          show={showClinicalCard}
        />
      )}

      {!selectedChat && (
        <p className="muted">Select a chat on the left or run a sandbox session.</p>
      )}

      <div className="conversationLayout">
        <div className="conversationTranscript">
          {loading && <p className="muted">Loading messages...</p>}
          {!loading && selectedChat && messages.length === 0 && (
            <p className="muted">No messages yet. Send a patient message in Sandbox.</p>
          )}
          {!loading && selectedChat && messages.length > 0 && dialogueTraces.length === 0 && (
            <p className="muted">Messages loaded, but no pipeline traces are linked yet.</p>
          )}
          {turns.map((turn) => {
            const traceInfo = turnTraceMap.get(turn.turnIndex) ?? null;
            return (
              <section
                key={`turn-${turn.turnIndex}-${turn.patient?.id ?? 'p'}-${turn.doctor?.id ?? 'd'}`}
                ref={(element) => {
                  if (element) {
                    turnRefs.current.set(turn.turnIndex, element);
                  } else {
                    turnRefs.current.delete(turn.turnIndex);
                  }
                }}
                className={`dialogueTurn ${activeTurnIndex === turn.turnIndex ? 'turnActive' : ''}`}
                data-turn-index={turn.turnIndex}
                data-trace-id={turn.doctor?.trace_id ?? undefined}
              >
                <div className="dialogueTurnHeader">
                  <div className="dialogueTurnLabel">
                    Turn {turn.turnIndex}
                    {traceInfo?.intakeCompleted && (
                      <span className="turnCompletionBadge">Intake completed</span>
                    )}
                  </div>
                  {(traceInfo?.patientTraceId || traceInfo?.psychologistTraceId) && (
                    <div className="turnTraceActions">
                      <TraceActionButton
                        label="Patient trace"
                        traceId={traceInfo?.patientTraceId ?? null}
                        selectedTraceId={selectedTraceId}
                        onOpenTrace={onOpenTrace}
                      />
                      <TraceActionButton
                        label="Psychologist trace"
                        traceId={traceInfo?.psychologistTraceId ?? null}
                        selectedTraceId={selectedTraceId}
                        onOpenTrace={onOpenTrace}
                      />
                    </div>
                  )}
                </div>
                <TurnMessage
                  message={turn.patient}
                  role="patient"
                  traceInfo={traceInfo}
                  selectedTraceId={selectedTraceId}
                  onOpenTrace={onOpenTrace}
                />
                <TurnMessage
                  message={turn.doctor}
                  role="doctor"
                  traceInfo={traceInfo}
                  selectedTraceId={selectedTraceId}
                  onOpenTrace={onOpenTrace}
                />
              </section>
            );
          })}
        </div>

        {traceDetail && (
          <TraceInspector
            traceDetail={traceDetail}
            loading={traceLoading}
            onClose={onCloseTrace}
            onOpenJudgeReport={judgeResult ? onOpenJudgeReport : undefined}
          />
        )}
      </div>
    </section>
  );
}
