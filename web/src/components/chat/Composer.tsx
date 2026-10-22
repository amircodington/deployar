"use client";

import { useState } from "react";
import { fa } from "@/lib/fa";

export function Composer({ onSend, busy }: { onSend: (text: string) => void; busy: boolean }) {
  const [text, setText] = useState("");
  const send = () => {
    const t = text.trim();
    if (!t || busy) return;
    onSend(t);
    setText("");
  };
  return (
    <form
      onSubmit={(e) => {
        e.preventDefault();
        send();
      }}
      className="flex items-end gap-2 rounded-[24px] bg-card p-2"
    >
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
            e.preventDefault();
            send();
          }
        }}
        rows={1}
        enterKeyHint="send"
        placeholder={fa.composerPlaceholder}
        aria-label={fa.composerPlaceholder}
        className="max-h-40 min-h-11 flex-1 resize-none bg-transparent px-3 py-2.5 leading-6 outline-none placeholder:text-ink-faint [field-sizing:content]"
      />
      <button
        type="submit"
        disabled={busy || !text.trim()}
        className="pressable min-h-11 rounded-full bg-ink px-5 text-[15px] font-medium text-ground disabled:opacity-40"
      >
        {fa.send}
      </button>
    </form>
  );
}
