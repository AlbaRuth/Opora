import type { MessageItem, SandboxTurnResponse, TraceSummary } from '../../types';

export type DialogueTurn = {
  turnIndex: number;
  patient: MessageItem | null;
  doctor: MessageItem | null;
};

export type TraceTurnMeta = {
  turnIndex: number | null;
  label: string;
};

export type TurnTraceInfo = {
  patientTraceId: string | null;
  psychologistTraceId: string | null;
  closureSegments: SandboxTurnResponse['closure_segments'];
  intakeCompleted: boolean;
};

export type PartitionedTraces = {
  dialogueTraces: TraceSummary[];
  judgeTraces: TraceSummary[];
  setupTraces: TraceSummary[];
};

export function partitionTraces(traces: TraceSummary[]): PartitionedTraces {
  const dialogueTraces: TraceSummary[] = [];
  const judgeTraces: TraceSummary[] = [];
  const setupTraces: TraceSummary[] = [];

  for (const trace of traces) {
    const source = trace.source || '';
    if (source.includes('judge')) {
      judgeTraces.push(trace);
    } else if (source.includes('setup') || source.includes('prescreening')) {
      setupTraces.push(trace);
    } else {
      dialogueTraces.push(trace);
    }
  }

  return { dialogueTraces, judgeTraces, setupTraces };
}

export function buildTurnTraceMap(
  sandboxTurns: SandboxTurnResponse[],
): Map<number, TurnTraceInfo> {
  const map = new Map<number, TurnTraceInfo>();
  sandboxTurns.forEach((turn, index) => {
    const metadata = turn.metadata ?? {};
    map.set(index + 1, {
      patientTraceId:
        turn.patient_trace_id ?? (metadata.patient_trace_id as string | undefined) ?? null,
      psychologistTraceId:
        turn.trace_id ?? (metadata.psychologist_trace_id as string | undefined) ?? null,
      closureSegments:
        turn.closure_segments ??
        (metadata.closure_segments as TurnTraceInfo['closureSegments']) ??
        null,
      intakeCompleted: Boolean(turn.intake_completed ?? metadata.intake_completed),
    });
  });
  return map;
}

export function groupMessagesIntoTurns(messages: MessageItem[]): DialogueTurn[] {
  const sorted = [...messages].sort((a, b) => a.message_number - b.message_number);
  const turns: DialogueTurn[] = [];

  for (const message of sorted) {
    if (message.role === 'patient') {
      turns.push({
        turnIndex: turns.length + 1,
        patient: message,
        doctor: null,
      });
      continue;
    }

    const last = turns[turns.length - 1];
    if (last && !last.doctor) {
      last.doctor = message;
    } else {
      turns.push({
        turnIndex: turns.length + 1,
        patient: null,
        doctor: message,
      });
    }
  }

  return turns;
}

export function buildTraceToTurnIndexMap(messages: MessageItem[]): Map<string, number> {
  const map = new Map<string, number>();
  for (const turn of groupMessagesIntoTurns(messages)) {
    const traceId = turn.doctor?.trace_id ?? turn.patient?.trace_id;
    if (traceId) {
      map.set(traceId, turn.turnIndex);
    }
  }
  return map;
}

function sortedTraces(traces: TraceSummary[]): TraceSummary[] {
  return [...traces].sort((left, right) => left.started_at.localeCompare(right.started_at));
}

export function resolveTraceTurnMeta(
  trace: TraceSummary,
  traceOrdinal: number,
  messages: MessageItem[],
  orderedTraces: TraceSummary[],
): TraceTurnMeta {
  const doctorMap = buildTraceToTurnIndexMap(messages);
  const direct = doctorMap.get(trace.trace_id);
  if (direct != null) {
    return { turnIndex: direct, label: `Turn ${direct}` };
  }

  const source = trace.source || '';
  if (source.includes('judge')) {
    const turns = groupMessagesIntoTurns(messages);
    return {
      turnIndex: turns.length || null,
      label: 'Judge',
    };
  }
  if (source.includes('setup') || source.includes('prescreening')) {
    return { turnIndex: 1, label: 'Setup' };
  }
  if (source.includes('auto_patient')) {
    const index = orderedTraces.findIndex((item) => item.trace_id === trace.trace_id);
    const nextDoctor = orderedTraces
      .slice(index + 1)
      .find((item) => doctorMap.has(item.trace_id));
    const turnIndex = nextDoctor ? doctorMap.get(nextDoctor.trace_id)! : null;
    return {
      turnIndex,
      label: turnIndex != null ? `Turn ${turnIndex} · patient` : `Trace ${traceOrdinal}`,
    };
  }

  return { turnIndex: null, label: `Trace ${traceOrdinal}` };
}

export function buildTraceTurnMetaList(
  messages: MessageItem[],
  traces: TraceSummary[],
): Map<string, TraceTurnMeta> {
  const ordered = sortedTraces(traces);
  const map = new Map<string, TraceTurnMeta>();
  ordered.forEach((trace, index) => {
    map.set(trace.trace_id, resolveTraceTurnMeta(trace, index + 1, messages, ordered));
  });
  return map;
}

export function findTurnIndexForTrace(
  messages: MessageItem[],
  traces: TraceSummary[],
  traceId: string,
): number | null {
  return buildTraceTurnMetaList(messages, traces).get(traceId)?.turnIndex ?? null;
}
