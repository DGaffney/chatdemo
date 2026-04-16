import { useState, useEffect, useCallback } from "react";
import { Link } from "react-router-dom";
import { MessageSquare, AlertTriangle, BookOpen, BarChart3, ArrowLeft, RefreshCw, FileText } from "lucide-react";
import { cn } from "../lib/utils";
import { api } from "../lib/api";
import type { TriageItem, Conversation, Override, Stats, DocumentItem } from "../lib/api";
import { TriageQueue } from "../components/TriageQueue";
import { KnowledgeEditor } from "../components/KnowledgeEditor";
import { DocumentsList } from "../components/DocumentsList";
import { TopicCluster } from "../components/TopicCluster";

type Tab = "triage" | "conversations" | "knowledge" | "docs" | "insights";

export function OperatorDashboard() {
  const [tab, setTab] = useState<Tab>("triage");
  const [triageItems, setTriageItems] = useState<TriageItem[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [overrides, setOverrides] = useState<Override[]>([]);
  const [documents, setDocuments] = useState<DocumentItem[]>([]);
  const [stats, setStats] = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [triageRes, convRes, overrideRes, docsRes, statsRes] = await Promise.all([
        api.getTriageItems(),
        api.getConversations({ limit: 100 }),
        api.getOverrides(),
        api.getDocuments(),
        api.getStats(),
      ]);
      setTriageItems(triageRes.items);
      setConversations(convRes.conversations);
      setOverrides(overrideRes.overrides);
      setDocuments(docsRes.documents);
      setStats(statsRes);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const tabs: { id: Tab; label: string; icon: typeof AlertTriangle; badge?: number }[] = [
    { id: "triage", label: "Triage", icon: AlertTriangle, badge: triageItems.length },
    { id: "conversations", label: "Conversations", icon: MessageSquare, badge: conversations.length },
    { id: "knowledge", label: "Knowledge", icon: BookOpen, badge: overrides.length },
    { id: "docs", label: "Docs", icon: FileText, badge: documents.length },
    { id: "insights", label: "Insights", icon: BarChart3 },
  ];

  return (
    <div className="min-h-dvh bg-background">
      {/* Header */}
      <header className="border-b border-border px-4 py-3 bg-card">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              to="/"
              className="flex h-8 w-8 items-center justify-center rounded-full hover:bg-secondary transition-colors"
            >
              <ArrowLeft className="h-4 w-4 text-muted-foreground" />
            </Link>
            <div>
              <h1 className="text-sm font-semibold text-foreground">Operator Dashboard</h1>
              <p className="text-xs text-muted-foreground">Sunrise Early Learning</p>
            </div>
          </div>
          <button
            onClick={loadData}
            disabled={loading}
            className="flex items-center gap-1.5 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary transition-colors"
          >
            <RefreshCw className={cn("h-3 w-3", loading && "animate-spin")} />
            Refresh
          </button>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-border bg-card">
        <div className="max-w-6xl mx-auto flex">
          {tabs.map(({ id, label, icon: Icon, badge }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={cn(
                "flex items-center gap-2 px-4 py-3 text-sm font-medium border-b-2 transition-colors",
                tab === id
                  ? "border-primary text-primary"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              )}
            >
              <Icon className="h-4 w-4" />
              {label}
              {badge !== undefined && badge > 0 && (
                <span className={cn(
                  "rounded-full px-1.5 py-0.5 text-xs font-medium",
                  id === "triage" ? "bg-red-100 text-red-800" : "bg-gray-100 text-gray-600"
                )}>
                  {badge}
                </span>
              )}
            </button>
          ))}
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto p-4">
        {tab === "triage" && (
          <TriageQueue items={triageItems} onRefresh={loadData} />
        )}

        {tab === "conversations" && (
          <ConversationsTable conversations={conversations} />
        )}

        {tab === "knowledge" && (
          <KnowledgeEditor overrides={overrides} onRefresh={loadData} />
        )}

        {tab === "docs" && (
          <DocumentsList documents={documents} onRefresh={loadData} />
        )}

        {tab === "insights" && stats && (
          <TopicCluster
            stats={stats.triage}
            topicDistribution={stats.topic_distribution}
            totalConversations={stats.total_conversations}
            escalationRate={stats.escalation_rate}
          />
        )}
      </div>
    </div>
  );
}

function ConversationsTable({ conversations }: { conversations: Conversation[] }) {
  if (conversations.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <MessageSquare className="h-12 w-12 mb-3 text-gray-300" />
        <p className="text-lg font-medium">No conversations yet</p>
        <p className="text-sm">Conversations will appear here as parents use the chat.</p>
      </div>
    );
  }

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="bg-secondary">
            <tr>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground">Question</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">Intent</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-28">Topic</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">Confidence</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-24">Escalated</th>
              <th className="text-left px-4 py-3 font-medium text-muted-foreground w-36">Time</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {conversations.map((c) => (
              <tr key={c.id} className="hover:bg-secondary/50 transition-colors">
                <td className="px-4 py-3 max-w-xs truncate">{c.question}</td>
                <td className="px-4 py-3">
                  <span className={cn(
                    "rounded-full px-2 py-0.5 text-xs font-medium",
                    c.intent === "lookup" && "bg-blue-100 text-blue-800",
                    c.intent === "policy" && "bg-green-100 text-green-800",
                    c.intent === "lead" && "bg-purple-100 text-purple-800",
                    c.intent === "sensitive" && "bg-red-100 text-red-800",
                  )}>
                    {c.intent}
                  </span>
                </td>
                <td className="px-4 py-3 text-muted-foreground">{c.topic?.replace(/_/g, " ")}</td>
                <td className="px-4 py-3">
                  <span className={cn(
                    "text-xs font-medium",
                    (c.confidence ?? 0) >= 0.75 ? "text-green-600" : (c.confidence ?? 0) >= 0.5 ? "text-amber-600" : "text-red-600"
                  )}>
                    {((c.confidence ?? 0) * 100).toFixed(0)}%
                  </span>
                </td>
                <td className="px-4 py-3">
                  {c.escalated ? (
                    <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">Yes</span>
                  ) : (
                    <span className="text-xs text-muted-foreground">No</span>
                  )}
                </td>
                <td className="px-4 py-3 text-xs text-muted-foreground">
                  {new Date(c.created_at).toLocaleString()}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
