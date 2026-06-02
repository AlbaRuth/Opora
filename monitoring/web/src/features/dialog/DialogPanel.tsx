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
        <h2>Dialog</h2>
        {selectedChat && <small>{selectedChat.source} / session #{selectedChat.session_number}</small>}
      </div>
      {!selectedChat && <p className="muted">Select a chat on the left.</p>}
      {loading && <p className="muted">Loading messages...</p>}
      {messages.map((message) => (
        <article key={message.id} className={`message ${message.role}`}>
          <div>
            <strong>{message.role === 'patient' ? 'Patient' : 'Model'}</strong>
            <span>#{message.message_number}</span>
          </div>
          <p>{message.content}</p>
          {message.primary_emotion && <small>{message.primary_emotion}</small>}
        </article>
      ))}
    </section>
  );
}
