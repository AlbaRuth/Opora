import type { ChatSummary, MessageItem } from '../../types';

type Props = {
  selectedChat: ChatSummary | null;
  messages: MessageItem[];
  loading: boolean;
};

export function DialogPanel({ selectedChat, messages, loading }: Props) {
  return (
    <section className="panel dialogPanel">
      <div className="panelHeader">
        <h2>Диалог</h2>
        {selectedChat && <small>{selectedChat.source} · session #{selectedChat.session_number}</small>}
      </div>
      {!selectedChat && <p className="muted">Выберите чат слева.</p>}
      {loading && <p className="muted">Загружаю сообщения...</p>}
      {messages.map((message) => (
        <article key={message.id} className={`message ${message.role}`}>
          <div>
            <strong>{message.role === 'patient' ? 'Пациент' : 'Модель'}</strong>
            <span>#{message.message_number}</span>
          </div>
          <p>{message.content}</p>
          {message.primary_emotion && <small>{message.primary_emotion}</small>}
        </article>
      ))}
    </section>
  );
}
