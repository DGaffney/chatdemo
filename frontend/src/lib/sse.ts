export interface SSECallbacks {
  onToken: (content: string) => void;
  onDone: (metadata: ChatMetadata) => void;
  onError: (error: Error) => void;
}

export interface ChatMetadata {
  session_id: string;
  intent: string;
  topic: string;
  topic_guess: string | null;
  confidence: number;
  escalated: boolean;
  escalation_reason: string | null;
  policy_cited: string | null;
  guardrail_flags: string[];
}

export async function streamChat(
  question: string,
  callbacks: SSECallbacks,
  options?: { session_id?: string; parent_email?: string }
): Promise<void> {
  const body = {
    question,
    session_id: options?.session_id,
    parent_email: options?.parent_email,
  };

  const response = await fetch("/api/ask", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    callbacks.onError(new Error(`HTTP ${response.status}`));
    return;
  }

  const reader = response.body?.getReader();
  if (!reader) {
    callbacks.onError(new Error("No response body"));
    return;
  }

  const decoder = new TextDecoder();
  let buffer = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          const raw = line.slice(6).trim();
          if (!raw) continue;
          try {
            const data = JSON.parse(raw);
            if (data.type === "token") {
              callbacks.onToken(data.content);
            } else if (data.type === "done") {
              callbacks.onDone(data as ChatMetadata);
            }
          } catch {
            // skip malformed JSON
          }
        }
      }
    }
  } catch (err) {
    callbacks.onError(err instanceof Error ? err : new Error(String(err)));
  }
}
