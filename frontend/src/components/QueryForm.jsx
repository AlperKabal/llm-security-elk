import { useState } from "react";

function QueryForm({ onSubmit, disabled }) {
  const [text, setText] = useState("");

  const handleChange = (e) => {
    setText(e.target.value);
    e.target.style.height = "auto";
    e.target.style.height = Math.min(e.target.scrollHeight, 80) + "px";
  };

  const handleFormSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onSubmit(text);
    setText("");
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleFormSubmit(e);
    }
  };

  return (
    <form
      onSubmit={handleFormSubmit}
      className="w-full flex items-center justify-center gap-3 px-4 py-9 bg-slate-950"
    >
      <div className="flex items-center justify-center gap-3 w-full max-w-2xl">
        <textarea
          id="queryForm"
          name="queryForm"
          value={text}
          onChange={handleChange}
          onKeyDown={handleKeyDown}
          placeholder="Ask a question..."
          rows={1}
          disabled={disabled}
          className="no-scrollbar flex-1 resize-none rounded-3xl bg-slate-800 px-4 py-2.5 max-h-20 overflow-y-auto border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-400 focus:bg-slate-900 transition-colors disabled:opacity-50"
          required
        />
        <button
          type="submit"
          disabled={disabled}
          className="w-10 h-10 flex items-center justify-center rounded-full bg-blue-600 hover:bg-blue-500 active:bg-blue-700 transition-colors shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <span className="text-white text-lg">↑</span>
        </button>
      </div>
    </form>
  );
}

export default QueryForm;