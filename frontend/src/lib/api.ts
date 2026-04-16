const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export const api = {
  getTriageItems: (priority?: string) =>
    request<{ items: TriageItem[]; count: number }>(
      `/triage${priority ? `?priority=${priority}` : ""}`
    ),

  getTriageItem: (id: number) => request<TriageItem>(`/triage/${id}`),

  resolveTriage: (id: number, body: ResolveBody) =>
    request(`/triage/${id}/resolve`, {
      method: "POST",
      body: JSON.stringify(body),
    }),

  dismissTriage: (id: number) =>
    request(`/triage/${id}/dismiss`, { method: "POST" }),

  getConversations: (params?: ConversationParams) => {
    const q = new URLSearchParams();
    if (params?.intent) q.set("intent", params.intent);
    if (params?.topic) q.set("topic", params.topic);
    if (params?.escalated !== undefined) q.set("escalated", String(params.escalated));
    if (params?.limit) q.set("limit", String(params.limit));
    if (params?.offset) q.set("offset", String(params.offset));
    const qs = q.toString();
    return request<{ conversations: Conversation[]; count: number }>(
      `/conversations${qs ? `?${qs}` : ""}`
    );
  },

  getStats: () => request<Stats>("/stats"),

  createOverride: (body: OverrideBody) =>
    request(`/override`, { method: "POST", body: JSON.stringify(body) }),

  getOverrides: () =>
    request<{ overrides: Override[]; count: number }>("/overrides"),

  deleteOverride: (id: number) =>
    request(`/overrides/${id}`, { method: "DELETE" }),

  getDocuments: () =>
    request<{ documents: DocumentItem[]; count: number }>("/documents"),

  deleteDocument: (id: number) =>
    request<{
      status: string;
      chunks_pruned: number;
      file_deleted: boolean;
      file_error: string | null;
    }>(`/documents/${id}`, { method: "DELETE" }),

  getOnboardingStatus: () =>
    request<{ configured: boolean; config: Record<string, string> }>("/onboarding/status"),

  completeOnboarding: (body: OnboardingBody) =>
    request("/onboarding/complete", {
      method: "POST",
      body: JSON.stringify(body),
    }),
};

export interface TriageItem {
  id: number;
  created_at: string;
  conversation_id: number;
  parent_email: string | null;
  priority: string;
  status: string;
  question: string;
  answer: string;
  intent: string;
  topic: string;
  topic_guess: string | null;
  confidence: number;
  escalation_reason: string;
}

export interface Conversation {
  id: number;
  created_at: string;
  session_id: string;
  question: string;
  answer: string;
  intent: string;
  topic: string;
  topic_guess: string | null;
  confidence: number;
  escalated: boolean;
  escalation_reason: string;
  policy_cited: string;
  guardrail_flags: string;
}

export interface Stats {
  total_conversations: number;
  escalation_rate: number;
  intent_distribution: Record<string, number>;
  topic_distribution: { topic: string; cnt: number }[];
  triage: {
    open_count: number;
    by_topic: { topic: string; cnt: number }[];
    novel_topics: { topic_guess: string; cnt: number }[];
  };
}

export interface Override {
  id: number;
  created_at: string;
  topic: string;
  question_pattern: string;
  answer: string;
  author: string;
}

export interface DocumentSection {
  chunk_index: number;
  heading_path: string;
  topic: string;
  page_start: number | null;
  page_end: number | null;
}

export interface DocumentItem {
  id: number;
  filename: string;
  status: "pending" | "processing" | "ready" | "failed" | string;
  uploaded_at: string | null;
  processed_at: string | null;
  error_message: string | null;
  page_count: number | null;
  chunk_count: number | null;
  topics: string[];
  summary: string | null;
  sections: DocumentSection[];
}

export interface ResolveBody {
  resolution_text: string;
  resolved_by?: string;
  promote_to_override?: boolean;
  override_topic?: string;
}

export interface OverrideBody {
  topic: string;
  question_pattern: string;
  answer: string;
  author?: string;
}

export interface ConversationParams {
  intent?: string;
  topic?: string;
  escalated?: boolean;
  limit?: number;
  offset?: number;
}

export interface OnboardingBody {
  center_name: string;
  operator_email: string;
  operating_hours: string;
  holidays_closed: string;
  tuition_infant: string;
  tuition_toddler: string;
  tuition_preschool: string;
  sick_policy: string;
  meals_info: string;
  tour_scheduling: string;
}
