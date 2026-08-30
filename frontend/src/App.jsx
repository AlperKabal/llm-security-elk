import { useState, useEffect } from "react";
import Header from "./components/Header";
import Sidebar from "./components/Sidebar";
import ChatWindow from "./components/ChatWindow";
import QueryForm from "./components/QueryForm";
import {fetchUsers,addUser,fetchChats,fetchChatMessages,deleteChat,sendMessage,} from "./api/client";

function App() {
  
  const [sessionId] = useState(() => crypto.randomUUID());

  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [users, setUsers] = useState([]);
  const [currentUserId, setCurrentUserId] = useState(null);

  const [chats, setChats] = useState([]);
  const [activeChatId, setActiveChatId] = useState(null);
  const [activeChatTitle, setActiveChatTitle] = useState(null);

  const [messages, setMessages] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAppLoading, setIsAppLoading] = useState(true);
  const [isSwitchingChat, setIsSwitchingChat] = useState(false);

  useEffect(() => {
    async function init() {
      const userList = await fetchUsers();
      setUsers(userList);
      if (userList.length > 0) {
        setCurrentUserId(userList[0]);
      }
      setIsAppLoading(false);
    }
    init();
  }, []);

  useEffect(() => {
    if (!currentUserId) return;
    async function loadChats() {
      const chatList = await fetchChats(currentUserId);
      setChats(chatList);
    }
    loadChats();
  }, [currentUserId]);

  function handleNewChat() {
    setActiveChatId(null);
    setActiveChatTitle(null);
    setMessages([]);
  }

  async function handleSelectChat(chatId) {
    setIsSwitchingChat(true);
    const data = await fetchChatMessages(chatId);
    setMessages(data);
    setActiveChatId(chatId);
    const chat = chats.find((c) => c.id === chatId);
    setActiveChatTitle(chat?.title || null);
    setIsSwitchingChat(false);
  }

  async function handleDeleteChat(chatId) {
    const confirmed = window.confirm("Delete this chat? This can't be undone.");
    if (!confirmed) return;
    await deleteChat(chatId);
    setChats((prev) => prev.filter((c) => c.id !== chatId));
    if (activeChatId === chatId) {
      handleNewChat();
    }
  }

  async function handleSubmit(promptText) {
    setIsLoading(true);
    setMessages((prev) => [
      ...prev,
      { role: "user", content: promptText, created_at: new Date().toISOString() },
    ]);

    try {
      const data = await sendMessage(currentUserId, activeChatId, sessionId, promptText);

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: data.final_response,
          blocked: data.blocked,
          created_at: data.event_time,
        },
      ]);

      if (!activeChatId && data.chat_id) {
        setActiveChatId(data.chat_id);
        setActiveChatTitle(promptText.slice(0, 50));
        const chatList = await fetchChats(currentUserId);
        setChats(chatList);
      }
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: "Could not reach the server. Please try again.",
          blocked: true,
          created_at: new Date().toISOString(),
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  }

  async function handleAddUser(newUserId) {
    await addUser(newUserId);
    setUsers((prev) => [...prev, newUserId]);
    setCurrentUserId(newUserId);
  }

  function handleSelectUser(userId) {
    setCurrentUserId(userId);
    handleNewChat();
  }

  if (isAppLoading) {
    return (
      <div className="flex items-center justify-center h-screen bg-slate-950">
        <div className="flex flex-col items-center gap-3">
          <div className="w-8 h-8 border-4 border-slate-700 border-t-blue-400 rounded-full animate-spin"></div>
          <p className="text-sm text-slate-400">Loading...</p>
        </div>
      </div>
    );
  }

  return (
    <div
      className={`grid h-screen grid-rows-[64px_1fr] ${
        sidebarOpen ? "grid-cols-[260px_1fr]" : "grid-cols-[56px_1fr]"
      } transition-[grid-template-columns] duration-200 bg-slate-950`}
    >
      <Sidebar
        sidebarOpen={sidebarOpen}
        onToggleSidebar={() => setSidebarOpen(!sidebarOpen)}
        chats={chats}
        activeChatId={activeChatId}
        onSelectChat={handleSelectChat}
        onNewChat={handleNewChat}
        onDeleteChat={handleDeleteChat}
      />

      <Header
        chatTitle={activeChatTitle}
        users={users}
        currentUserId={currentUserId}
        onSelectUser={handleSelectUser}
        onAddUser={handleAddUser}
      />

      <main className="flex flex-col h-full overflow-hidden">
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          isSwitchingChat={isSwitchingChat}
        />
        <QueryForm onSubmit={handleSubmit} disabled={isLoading} />
      </main>
    </div>
  );
}

export default App;