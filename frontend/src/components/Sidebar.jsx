function Sidebar({
  sidebarOpen,
  onToggleSidebar,
  chats,
  activeChatId,
  onSelectChat,
  onNewChat,
  onDeleteChat,
}) {
  if (!sidebarOpen) {
    return (
      <aside className="row-span-2 flex flex-col items-center gap-5 pt-6 border-r border-slate-800 bg-slate-900 h-full">
        <button
          onClick={onToggleSidebar}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-700 text-slate-300"
        >
          <span className="text-sm">→</span>
        </button>
        <button
          onClick={onNewChat}
          className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-slate-700 text-blue-400"
        >
          <span className="text-lg">+</span>
        </button>
      </aside>
    );
  }

  return (
    <aside className="no-scrollbar row-span-2 flex flex-col border-r border-slate-800 bg-slate-900 overflow-y-auto overflow-x-hidden h-full">
      <div className="flex items-center justify-between px-4 py-4">
        <span className="font-semibold text-slate-100">LLM Security Chat</span>
        <button
          onClick={onToggleSidebar}
          className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-slate-700 text-slate-300 shrink-0"
        >
          <span className="text-sm">←</span>
        </button>
      </div>

      <button
        onClick={onNewChat}
        className={`mx-2 mb-2 px-4 py-2 text-left text-sm font-medium rounded-full text-slate-100 ${
          activeChatId === null ? "bg-slate-800" : "hover:bg-slate-800"
        }`}
      >
        <span className="text-base mr-1">+</span>
        <span>New Chat</span>
      </button>

      <div className="flex flex-col">
        {chats.map((chat) => (
          <div
            key={chat.id}
            onClick={() => onSelectChat(chat.id)}
            className={`group flex items-center justify-between px-4 py-2 rounded-full mx-2 cursor-pointer text-slate-200 ${
              chat.id === activeChatId
                ? "bg-slate-800"
                : "hover:bg-slate-800/60"
            }`}
          >
            <span className="text-sm truncate">
              {chat.title || "Untitled chat"}
            </span>

            <button
              onClick={(e) => {
                e.stopPropagation();
                onDeleteChat(chat.id);
              }}
              className="opacity-0 group-hover:opacity-100 shrink-0 ml-2 px-1 hover:bg-slate-700 rounded-full text-red-400"
            >
              🗑
            </button>
          </div>
        ))}
      </div>
    </aside>
  );
}

export default Sidebar;