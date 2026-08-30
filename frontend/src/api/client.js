const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5000";

// --- Kullanıcılar ---

export async function fetchUsers() {
  const res = await fetch(`${API_BASE}/users`);
  return res.json();
}

export async function addUser(userId) {
  const res = await fetch(`${API_BASE}/users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId }),
  });
  return res.json();
}

// --- Chatler ---

export async function fetchChats(userId) {
  const res = await fetch(`${API_BASE}/chats?user_id=${userId}`);
  return res.json();
}

export async function fetchChatMessages(chatId) {
  const res = await fetch(`${API_BASE}/chats/${chatId}`);
  return res.json();
}

export async function deleteChat(chatId) {
  return fetch(`${API_BASE}/chats/${chatId}`, {
    method: "DELETE",
  });
}

export async function renameChat(chatId, newTitle) {
  return fetch(`${API_BASE}/chats/${chatId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title: newTitle }),
  });
}

// --- Mesaj Gönderme ---

export async function sendMessage(userId, chatId, sessionId, prompt) {
  const res = await fetch(`${API_BASE}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      user_id: userId,
      chat_id: chatId,
      session_id: sessionId,
      prompt: prompt,
    }),
  });
  return res.json();
}