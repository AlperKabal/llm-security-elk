import { useEffect, useRef } from "react";

function ChatWindow({ messages, isLoading, isSwitchingChat }) {
  const bottomRef = useRef(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading]);

  if (messages.length === 0) {
    return (
      <div className="no-scrollbar flex-1 overflow-y-auto flex items-center justify-center px-4">
        <div className="max-w-md text-center">
          <p className="text-sm text-slate-400 mb-1">
            This assistant is monitored by an LLM security pipeline that detects:
          </p>
          <ul className="text-sm text-slate-400 text-left list-disc list-inside space-y-0.5 mb-6">
            <li>Prompt injection and jailbreak attempts</li>
            <li>Sensitive information disclosure</li>
            <li>Behavioral anomalies (rate, length, repetition)</li>
            <li>Semantic similarity to known attack patterns</li>
          </ul>
          <p className="text-3xl font-bold text-slate-100 py-4">
            Start a New Chat
          </p>
        </div>
      </div>
    );
  }

  function formatTime(isoString) {
    const date = new Date(isoString);
    const now = new Date();

    const isToday = date.toDateString() === now.toDateString();

    const yesterday = new Date(now);
    yesterday.setDate(now.getDate() - 1);
    const isYesterday = date.toDateString() === yesterday.toDateString();

    const time = date.toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
    });

    if (isToday) return time;
    if (isYesterday) return `Yesterday - ${time}`;

    const day = String(date.getDate()).padStart(2, "0");
    const month = String(date.getMonth() + 1).padStart(2, "0");
    const year = date.getFullYear();
    return `${day}.${month}.${year} - ${time}`;
  }

  return (
    <div
      className={`no-scrollbar flex-1 overflow-y-auto px-4 py-6 transition-opacity duration-150 ${
        isSwitchingChat ? "opacity-50" : "opacity-100"
      }`}
    >
      <div className="max-w-2xl mx-auto flex flex-col gap-4">
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex flex-col ${
              msg.role === "user" ? "items-end" : "items-start"
            }`}
          >
            <div
              className={`max-w-[75%] px-4 py-2.5 rounded-2xl ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : msg?.blocked
                    ? "bg-red-950 text-red-300 border border-red-800"
                    : "bg-slate-800 text-slate-100"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
            </div>
            {msg.created_at && (
              <p className="text-xs text-slate-500 mt-1 px-1">
                {formatTime(msg.created_at)}
              </p>
            )}
          </div>
        ))}

        {isLoading && (
          <div className="flex justify-start">
            <div className="flex items-center gap-1 px-4 py-3 bg-slate-800 rounded-2xl">
              <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.3s]"></span>
              <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce [animation-delay:-0.15s]"></span>
              <span className="w-2 h-2 bg-blue-400 rounded-full animate-bounce"></span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  );
}

export default ChatWindow;