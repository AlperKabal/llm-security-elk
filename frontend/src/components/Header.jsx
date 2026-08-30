import UserDropdown from "./UserDropdown";

function Header({ chatTitle, users, currentUserId, onSelectUser, onAddUser }) {
  return (
    <header className="flex items-center justify-between px-6 py-4 border-b border-slate-800 bg-slate-900">
      <h1 className="text-lg font-medium text-slate-100">
        {chatTitle || "New Chat"}
      </h1>

      <UserDropdown
        users={users}
        currentUserId={currentUserId}
        onSelectUser={onSelectUser}
        onAddUser={onAddUser}
      />
    </header>
  );
}

export default Header;