import { useState } from "react";

function UserDropdown({ users, currentUserId, onSelectUser, onAddUser }) {
  const [isOpen, setIsOpen] = useState(false);
  const [isAdding, setIsAdding] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [error, setError] = useState("");

  function handleAddSubmit(e) {
    e.preventDefault();
    if (!newUsername.trim()) return;

    const exists = users.some((u) => u === newUsername.trim());
    if (exists) {
      setError("This user already exists");
      return;
    }

    onAddUser(newUsername.trim());
    setNewUsername("");
    setIsAdding(false);
    setError("");
  }

  return (
    <div className="relative">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-sm text-slate-100"
      >
        <span>👤</span>
        <span>{currentUserId || "Select user"}</span>
        <span className="text-xs">▼</span>
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-56 bg-slate-800 border border-slate-700 rounded-lg shadow-lg z-10">
          {users.map((u) => (
            <button
              key={u}
              onClick={() => {
                onSelectUser(u);
                setIsOpen(false);
              }}
              className={`w-full text-left px-4 py-2 text-sm hover:bg-slate-700 ${
                u === currentUserId ? "bg-slate-700 text-blue-400" : "text-slate-200"
              }`}
            >
              {u}
            </button>
          ))}

          <div className="border-t border-slate-700">
            {isAdding ? (
              <form onSubmit={handleAddSubmit} className="p-2">
                <input
                  autoFocus
                  value={newUsername}
                  onChange={(e) => {
                    setNewUsername(e.target.value);
                    setError("");
                  }}
                  placeholder="Enter username..."
                  className="w-full px-2 py-1 rounded bg-slate-900 border border-slate-600 text-sm text-slate-100 focus:outline-none focus:ring-1 focus:ring-blue-400"
                />
                {error && (
                  <p className="text-xs text-red-400 mt-1">{error}</p>
                )}
              </form>
            ) : (
              <button
                onClick={() => setIsAdding(true)}
                className="w-full text-left px-4 py-2 text-sm text-blue-400 hover:bg-slate-700"
              >
                + Add User
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default UserDropdown;