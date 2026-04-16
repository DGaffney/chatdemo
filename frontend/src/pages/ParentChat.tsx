import { useState, useRef, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { Send, Loader2, Settings } from "lucide-react";
import { ChatMessage } from "../components/ChatMessage";
import { streamChat } from "../lib/sse";
import type { ChatMetadata } from "../lib/sse";
import { cn } from "../lib/utils";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  metadata?: ChatMetadata | null;
  isStreaming?: boolean;
}

export function ParentChat() {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "Hi! I'm the AI assistant for Sunrise Early Learning. I can help with questions about our hours, tuition, policies, meals, and more. How can I help you today?",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [parentEmail, setParentEmail] = useState("");
  const [showEmailPrompt, setShowEmailPrompt] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const scrollToBottom = useCallback(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, []);

  useEffect(() => { scrollToBottom(); }, [messages, scrollToBottom]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const q = input.trim();
    if (!q || isLoading) return;
    setInput("");

    const userMsg: Message = { id: crypto.randomUUID(), role: "user", content: q };
    const assistantId = crypto.randomUUID();
    const assistantMsg: Message = { id: assistantId, role: "assistant", content: "", isStreaming: true };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setIsLoading(true);

    await streamChat(q, {
      onToken: (content) => {
        setMessages((prev) =>
          prev.map((m) => (m.id === assistantId ? { ...m, content: m.content + content } : m))
        );
      },
      onDone: (metadata) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, isStreaming: false, metadata } : m
          )
        );
        if (metadata.escalated && !parentEmail) {
          setShowEmailPrompt(true);
        }
        setIsLoading(false);
      },
      onError: (err) => {
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: "Sorry, something went wrong. Please try again.", isStreaming: false }
              : m
          )
        );
        console.error(err);
        setIsLoading(false);
      },
    }, { session_id: sessionId, parent_email: parentEmail });
  };

  const handleEmailSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setShowEmailPrompt(false);
    setMessages((prev) => [
      ...prev,
      {
        id: crypto.randomUUID(),
        role: "assistant",
        content: `Thanks! We have your email (${parentEmail}) on file. Our director will follow up with you there.`,
      },
    ]);
  };

  return (
    <div className="flex h-dvh flex-col bg-background">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-primary text-primary-foreground text-lg">
            S
          </div>
          <div>
            <h1 className="text-sm font-semibold text-foreground">Sunrise Early Learning</h1>
            <p className="text-xs text-muted-foreground">AI Front Desk</p>
          </div>
        </div>
        <Link
          to="/operator"
          className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-secondary transition-colors"
          title="Operator Dashboard"
        >
          <Settings className="h-4 w-4 text-muted-foreground" />
        </Link>
      </header>

      {/* Messages */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto py-4">
        {messages.map((msg) => (
          <ChatMessage
            key={msg.id}
            role={msg.role}
            content={msg.content}
            isStreaming={msg.isStreaming}
            metadata={msg.metadata}
          />
        ))}

        {/* Email capture prompt */}
        {showEmailPrompt && (
          <div className="mx-4 mt-2 rounded-xl border border-amber-200 bg-amber-50 p-4">
            <p className="text-sm text-amber-900 mb-2">
              To help our director follow up with you, could you share your email?
            </p>
            <form onSubmit={handleEmailSubmit} className="flex gap-2">
              <input
                type="email"
                value={parentEmail}
                onChange={(e) => setParentEmail(e.target.value)}
                placeholder="your.email@example.com"
                required
                className="flex-1 rounded-lg border border-amber-300 bg-white px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="submit"
                className="rounded-lg bg-primary px-3 py-1.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                Submit
              </button>
            </form>
          </div>
        )}
      </div>

      {/* Input */}
      <div className="border-t border-border p-4 pb-safe">
        <form onSubmit={handleSubmit} className="flex gap-2">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about hours, tuition, policies..."
            disabled={isLoading}
            className="flex-1 rounded-full border border-input bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-ring disabled:opacity-50"
          />
          <button
            type="submit"
            disabled={isLoading || !input.trim()}
            className={cn(
              "flex h-10 w-10 items-center justify-center rounded-full transition-colors",
              input.trim() && !isLoading
                ? "bg-primary text-primary-foreground hover:bg-primary/90"
                : "bg-secondary text-muted-foreground"
            )}
          >
            {isLoading ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
