import { useRef } from 'react';
import type { ClinicalCardResponse } from '../../types';

type PanelProps = {
  card: ClinicalCardResponse | null;
  loading: boolean;
  compact?: boolean;
};

export function ClinicalCardDrawer({
  card,
  loading,
  show,
}: {
  card: ClinicalCardResponse | null;
  loading: boolean;
  show: boolean;
}) {  const detailsRef = useRef<HTMLDetailsElement>(null);

  if (!show) return null;

  return (
    <details
      ref={detailsRef}
      className="clinicalCardDrawer"
      onToggle={(event) => {
        const element = event.currentTarget;
        if (element.open) {
          requestAnimationFrame(() => {
            element.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
          });
        }
      }}
    >
      <summary className="clinicalCardDrawerSummary">
        <span>Клиническая карточка</span>
        <span className="clinicalCardDrawerHint">нажмите, чтобы развернуть</span>
      </summary>
      <ClinicalCardPanel card={card} loading={loading} compact />
    </details>
  );
}

export function ClinicalCardPanel({ card, loading, compact = false }: PanelProps) {  if (loading) {
    return (
      <div className={`clinicalCardPanel ${compact ? 'compact' : ''}`}>
        <p className="muted">Загрузка карточки…</p>
      </div>
    );
  }

  if (!card) {
    return null;
  }

  if (!card.has_data) {
    return (
      <div className={`clinicalCardPanel ${compact ? 'compact' : ''}`}>
        <p className="muted">Карточка пока пуста или intake ещё не завершён.</p>
      </div>
    );
  }

  return (
    <div className={`clinicalCardPanel ${compact ? 'compact' : ''}`}>
      {!compact && (
        <div className="clinicalCardHeader">
          <h3>Клиническая карточка</h3>
          {card.initial_info_insufficient && (
            <span className="badge warn">Недостаточно данных</span>
          )}
        </div>
      )}
      {compact && card.initial_info_insufficient && (
        <span className="badge warn clinicalCardInlineBadge">Недостаточно данных</span>
      )}
      <dl className="clinicalCardMeta">
        <div><dt>Имя</dt><dd>{card.display_name}</dd></div>
        <div><dt>Возраст</dt><dd>{card.age}</dd></div>
        <div><dt>Пол</dt><dd>{card.sex_display}</dd></div>
      </dl>
      <div className="clinicalCardBody">{card.summary_text}</div>
    </div>
  );
}
