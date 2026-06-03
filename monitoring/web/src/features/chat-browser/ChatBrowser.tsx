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
  const sources = [
    { value: '', label: 'All' },
    { value: 'telegram', label: 'Telegram' },
    { value: 'sandbox', label: 'Sandbox' },
  ] as const;

  return (
    <section className="sidebar">
      <div className="sidebarHeader">
        <div className="sidebarTitle">
          <h1>Opora Monitor</h1>
          <small>Telegram and Sandbox, one trace view</small>
        </div>
        <button type="button" className="sidebarRefresh" onClick={onRefresh} disabled={loading}>
          {loading ? '...' : 'Refresh'}
        </button>
      </div>

      <div className="sourceFilter" role="group" aria-label="Source">
        {sources.map((item) => (
          <button
            key={item.value || 'all'}
            type="button"
            className={source === item.value ? 'sourceFilterBtn active' : 'sourceFilterBtn'}
            aria-pressed={source === item.value}
            onClick={() => onSourceChange(item.value)}
          >
            {item.label}
          </button>
        ))}
      </div>

      {error && <pre className="error sidebarError">{error}</pre>}

      <div className="chatList">
        {chats.map((chat) => (
          <button
            key={chat.session_id}
            type="button"
            className={selectedChat?.session_id === chat.session_id ? 'chat active' : 'chat'}
            onClick={() => onSelect(chat)}
          >
            <strong>{chat.display_name || chat.username || chat.telegram_id}</strong>
            <span>{chat.source} / session #{chat.session_number}</span>
            <small>{chat.dialog_count} turns / {chat.therapy_type}</small>
          </button>
        ))}
        {!loading && chats.length === 0 && <p className="muted chatListEmpty">No chats yet.</p>}
      </div>
    </section>
  );
}
