import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, RotateCcw, Shield } from "lucide-react";
import { request } from "../api/client";
import { useToast } from "../components/Toast";
import { useLocale } from "../i18n";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const LEVELS = [
  { level: 1, name: "Level 1", desc: "No Protection", text: "text-red-600", border: "border-red-200" },
  { level: 2, name: "Level 2", desc: "Basic Filtering", text: "text-orange-600", border: "border-orange-200" },
  { level: 3, name: "Level 3", desc: "Moderate Defense", text: "text-amber-600", border: "border-amber-200" },
  { level: 4, name: "Level 4", desc: "Strong Defense", text: "text-green-600", border: "border-green-200" },
];

export function Playground() {
  const [level, setLevel] = useState(1);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const { toast } = useToast();
  const { t } = useLocale();

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages]);

  async function handleSend() {
    const text = input.trim();
    if (!text || sending) return;

    const userMsg: Message = { role: "user", content: text };
    const updatedMessages = [...messages, userMsg];
    setMessages(updatedMessages);
    setInput("");
    setSending(true);

    try {
      const res = await request<{ data: { response: string } }>("/targets/chat", {
        method: "POST",
        body: JSON.stringify({
          message: text,
          level,
          history: messages.map((m) => ({ role: m.role, content: m.content })),
        }),
      });
      setMessages([...updatedMessages, { role: "assistant", content: res.data.response }]);
    } catch (err) {
      toast("error", `Chat failed: ${err instanceof Error ? err.message : err}`);
      setMessages(updatedMessages);
    } finally {
      setSending(false);
    }
  }

  function handleReset() {
    setMessages([]);
    setInput("");
  }

  function handleKeyDown(e: React.KeyboardEvent) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  const currentLevel = LEVELS.find((l) => l.level === level)!;

  return (
    <div className="flex flex-col h-[calc(100vh-48px)]">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold text-gray-900 flex items-center gap-3">
          <Shield className="w-6 h-6 text-indigo-500" />
          {t("playground.title")}
        </h1>
        <div className="flex items-center gap-2">
          {LEVELS.map((l) => (
            <button
              key={l.level}
              onClick={() => {
                setLevel(l.level);
                handleReset();
              }}
              className={`px-3 py-1.5 text-xs rounded-lg border transition-colors ${
                level === l.level
                  ? `${l.text} ${l.border} bg-gray-50`
                  : "text-gray-500 border-gray-200 hover:border-gray-300"
              }`}
            >
              {l.name}
            </button>
          ))}
          <button
            onClick={handleReset}
            className="ml-2 p-2 text-gray-400 hover:text-gray-700 transition-colors"
          title={t("playground.resetConversation")}
          >
            <RotateCcw className="w-4 h-4" />
          </button>
        </div>
      </div>

      <div className="card px-4 py-2 mb-4 flex items-center gap-2">
        <span className={`text-xs font-mono font-medium ${currentLevel.text}`}>{currentLevel.name}</span>
        <span className="text-xs text-gray-400">-</span>
        <span className="text-xs text-gray-600">{currentLevel.desc}</span>
            <span className="text-xs text-gray-400 ml-auto">{t("playground.techCorpTarget")}</span>
      </div>

      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto bg-gray-50 border border-gray-100 rounded-xl p-4 space-y-4 mb-4"
      >
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-gray-500 text-sm space-y-2">
            <Bot className="w-10 h-10 text-gray-300" />
            <p>{t("playground.startChatting")}</p>
            <p className="text-xs text-gray-400">{t("playground.tryAttacks")}</p>
          </div>
        )}
        {messages.map((msg, i) => (
          <div
            key={i}
            className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            {msg.role === "assistant" && (
              <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
                <Bot className="w-4 h-4 text-indigo-600" />
              </div>
            )}
            <div
              className={`max-w-[70%] px-4 py-3 rounded-xl text-sm whitespace-pre-wrap ${
                msg.role === "user"
                  ? "bg-gray-900 text-white"
                  : "bg-white border border-gray-200 text-gray-700 shadow-sm"
              }`}
            >
              {msg.content}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-lg bg-gray-100 flex items-center justify-center shrink-0">
                <User className="w-4 h-4 text-gray-600" />
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-indigo-50 border border-indigo-100 flex items-center justify-center shrink-0">
              <Bot className="w-4 h-4 text-indigo-600" />
            </div>
            <div className="bg-white border border-gray-200 px-4 py-3 rounded-xl shadow-sm">
              <div className="flex gap-1">
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        <textarea
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={t("playground.inputPlaceholder")}
          rows={2}
          className="flex-1 px-4 py-3 bg-white border border-gray-200 rounded-xl text-gray-900 placeholder:text-gray-400 focus:border-gray-900 focus:outline-none focus:ring-1 focus:ring-gray-900/10 resize-none text-sm shadow-sm"
        />
        <button
          onClick={handleSend}
          disabled={sending || !input.trim()}
          className="px-6 bg-gray-900 hover:bg-gray-800 disabled:opacity-50 text-white rounded-xl transition-colors flex items-center gap-2 shadow-sm"
        >
          <Send className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
