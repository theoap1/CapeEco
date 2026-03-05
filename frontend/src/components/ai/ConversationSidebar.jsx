import { useState, useRef, useEffect } from 'react';
import { Plus, MessageSquare, MoreHorizontal, Trash2, Pencil, X, PanelLeftClose, PanelLeft } from 'lucide-react';

function groupByDate(conversations) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today); yesterday.setDate(today.getDate() - 1);
  const weekAgo = new Date(today); weekAgo.setDate(today.getDate() - 7);

  const groups = { today: [], yesterday: [], week: [], older: [] };
  for (const c of conversations) {
    const d = new Date(c.updated_at);
    if (d >= today) groups.today.push(c);
    else if (d >= yesterday) groups.yesterday.push(c);
    else if (d >= weekAgo) groups.week.push(c);
    else groups.older.push(c);
  }
  return groups;
}

function ConversationItem({ conv, isActive, onSelect, onDelete, onRename }) {
  const [menuOpen, setMenuOpen] = useState(false);
  const [renaming, setRenaming] = useState(false);
  const [title, setTitle] = useState(conv.title);
  const inputRef = useRef(null);

  useEffect(() => {
    if (renaming) inputRef.current?.focus();
  }, [renaming]);

  const handleRename = () => {
    const trimmed = title.trim();
    if (trimmed && trimmed !== conv.title) {
      onRename(conv.id, trimmed);
    } else {
      setTitle(conv.title);
    }
    setRenaming(false);
    setMenuOpen(false);
  };

  return (
    <div
      className={`group relative flex items-center gap-2 px-2.5 py-2 rounded-lg cursor-pointer text-sm transition-colors ${
        isActive ? 'bg-gray-800 text-white' : 'text-gray-400 hover:bg-gray-800/50 hover:text-gray-200'
      }`}
      onClick={() => !renaming && onSelect(conv.id)}
    >
      <MessageSquare className="w-3.5 h-3.5 shrink-0 text-gray-500" />
      {renaming ? (
        <input
          ref={inputRef}
          value={title}
          onChange={e => setTitle(e.target.value)}
          onKeyDown={e => {
            if (e.key === 'Enter') handleRename();
            if (e.key === 'Escape') { setTitle(conv.title); setRenaming(false); setMenuOpen(false); }
          }}
          onBlur={handleRename}
          onClick={e => e.stopPropagation()}
          className="flex-1 min-w-0 bg-gray-700 border border-gray-600 rounded px-1.5 py-0.5 text-xs text-white focus:outline-none focus:border-ocean-500"
        />
      ) : (
        <span className="flex-1 min-w-0 truncate text-xs">{conv.title}</span>
      )}

      {/* Menu trigger */}
      {!renaming && (
        <button
          onClick={e => { e.stopPropagation(); setMenuOpen(!menuOpen); }}
          className="opacity-0 group-hover:opacity-100 shrink-0 w-5 h-5 flex items-center justify-center rounded hover:bg-gray-700 transition-opacity"
        >
          <MoreHorizontal className="w-3.5 h-3.5" />
        </button>
      )}

      {/* Dropdown menu */}
      {menuOpen && !renaming && (
        <div className="absolute right-0 top-full mt-1 z-20 bg-gray-800 border border-gray-700 rounded-lg shadow-xl py-1 min-w-[120px]">
          <button
            onClick={e => { e.stopPropagation(); setRenaming(true); setMenuOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-gray-300 hover:bg-gray-700 hover:text-white"
          >
            <Pencil className="w-3 h-3" /> Rename
          </button>
          <button
            onClick={e => { e.stopPropagation(); onDelete(conv.id); setMenuOpen(false); }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
          >
            <Trash2 className="w-3 h-3" /> Delete
          </button>
        </div>
      )}
    </div>
  );
}

function GroupLabel({ label }) {
  return <div className="text-[10px] text-gray-600 uppercase tracking-wider font-medium px-2.5 pt-3 pb-1">{label}</div>;
}

export default function ConversationSidebar({ conversations, activeId, onSelect, onNewChat, onDelete, onRename, collapsed, onToggle }) {
  const groups = groupByDate(conversations);

  if (collapsed) {
    return (
      <div className="w-10 shrink-0 border-r border-gray-800 bg-gray-950 flex flex-col items-center pt-2 gap-2">
        <button onClick={onToggle} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors">
          <PanelLeft className="w-4 h-4" />
        </button>
        <button onClick={onNewChat} className="w-7 h-7 rounded-lg flex items-center justify-center text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors">
          <Plus className="w-4 h-4" />
        </button>
      </div>
    );
  }

  return (
    <div className="w-[260px] shrink-0 border-r border-gray-800 bg-gray-950 flex flex-col h-full">
      {/* Header */}
      <div className="h-10 border-b border-gray-800 flex items-center justify-between px-3 shrink-0">
        <span className="text-xs font-medium text-gray-400">Chats</span>
        <div className="flex items-center gap-1">
          <button
            onClick={onNewChat}
            className="w-6 h-6 rounded-md flex items-center justify-center text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
            title="New chat"
          >
            <Plus className="w-3.5 h-3.5" />
          </button>
          <button
            onClick={onToggle}
            className="w-6 h-6 rounded-md flex items-center justify-center text-gray-500 hover:text-gray-300 hover:bg-gray-800 transition-colors"
            title="Collapse sidebar"
          >
            <PanelLeftClose className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      {/* Conversation list */}
      <div className="flex-1 overflow-y-auto sidebar-scroll px-1.5 py-1">
        {conversations.length === 0 ? (
          <div className="text-xs text-gray-600 text-center py-8 px-4">
            No conversations yet. Start a new chat to begin.
          </div>
        ) : (
          <>
            {groups.today.length > 0 && (
              <>
                <GroupLabel label="Today" />
                {groups.today.map(c => (
                  <ConversationItem key={c.id} conv={c} isActive={c.id === activeId} onSelect={onSelect} onDelete={onDelete} onRename={onRename} />
                ))}
              </>
            )}
            {groups.yesterday.length > 0 && (
              <>
                <GroupLabel label="Yesterday" />
                {groups.yesterday.map(c => (
                  <ConversationItem key={c.id} conv={c} isActive={c.id === activeId} onSelect={onSelect} onDelete={onDelete} onRename={onRename} />
                ))}
              </>
            )}
            {groups.week.length > 0 && (
              <>
                <GroupLabel label="Previous 7 days" />
                {groups.week.map(c => (
                  <ConversationItem key={c.id} conv={c} isActive={c.id === activeId} onSelect={onSelect} onDelete={onDelete} onRename={onRename} />
                ))}
              </>
            )}
            {groups.older.length > 0 && (
              <>
                <GroupLabel label="Older" />
                {groups.older.map(c => (
                  <ConversationItem key={c.id} conv={c} isActive={c.id === activeId} onSelect={onSelect} onDelete={onDelete} onRename={onRename} />
                ))}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
