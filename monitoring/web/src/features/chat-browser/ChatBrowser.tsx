import type { ChatSummary } from '../../types';

type Props = {
  source: string;
  chats: ChatSummary[];
  selectedChat: ChatSummary | null;
  loading: boolean;
  error: string | null;
  onSourceChange: (source: string) => void;
  onRefresh: () => void;
  onSelect: (chat: ChatSummary) => void;
};

export function ChatBrowser({
  source,
  chats,
  selectedChat,
  loading,
  error,
  onSourceChange,
  onRefresh,
  onSelect,
}: Props) {
  return (
    <section className="sidebar">
      <div className="header">
        <div>
          <h1>Opora Monitor</h1>
          <small>Telegram и Sandbox раздельно, один trace view</small>
        </div>
        <button onClick={onRefresh} disabled={loading}>
          {loading ? '...' : 'Обновить'}
        </button>
      </div>
      <label>
        Источник
        <select value={source} onChange={(event) => onSourceChange(event.target.value)}>
          <option value="">Все</option>
          <option value="telegram">Telegram</option>
          <option value="sandbox">Sandbox</option>
        </select>
      </label>
      {error && <pre className="error">{error}</pre>}
      <div className="chatList">
        {chats.map((chat) => (
          <button
            key={chat.session_id}
            className={selectedChat?.session_id === chat.session_id ? 'chat active' : 'chat'}
            onClick={() => onSelect(chat)}
          >
            <strong>{chat.display_name || chat.username || chat.telegram_id}</strong>
            <span>{chat.source} · session #{chat.session_number}</span>
            <small>{chat.dialog_count} turns · {chat.therapy_type}</small>
          </button>
        ))}
        {!loading && chats.length === 0 && <p className="muted">Чатов пока нет.</p>}
      </div>
    </section>
  );
}
