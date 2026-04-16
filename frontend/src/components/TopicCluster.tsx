import { cn } from "../lib/utils";

interface TopicClusterProps {
  stats: {
    open_count: number;
    by_topic: { topic: string; cnt: number }[];
    novel_topics: { topic_guess: string; cnt: number }[];
  };
  topicDistribution: { topic: string; cnt: number }[];
  totalConversations: number;
  escalationRate: number;
}

export function TopicCluster({ stats, topicDistribution, totalConversations, escalationRate }: TopicClusterProps) {
  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        <StatCard label="Total Conversations" value={totalConversations} />
        <StatCard label="Open Triage" value={stats.open_count} accent={stats.open_count > 0 ? "red" : "green"} />
        <StatCard label="Escalation Rate" value={`${escalationRate.toFixed(1)}%`} />
        <StatCard label="Novel Topics" value={stats.novel_topics.length} accent={stats.novel_topics.length > 0 ? "amber" : undefined} />
      </div>

      {/* Topic Distribution */}
      <div className="rounded-xl border border-border p-4">
        <h3 className="text-sm font-medium text-foreground mb-3">Topic Distribution</h3>
        {topicDistribution.length === 0 ? (
          <p className="text-sm text-muted-foreground">No conversations yet.</p>
        ) : (
          <div className="space-y-2">
            {topicDistribution.map(({ topic, cnt }) => {
              const pct = totalConversations > 0 ? (cnt / totalConversations) * 100 : 0;
              return (
                <div key={topic} className="flex items-center gap-3">
                  <span className="text-xs text-muted-foreground w-24 truncate">{topic.replace(/_/g, " ")}</span>
                  <div className="flex-1 h-5 bg-secondary rounded-full overflow-hidden">
                    <div className="h-full bg-primary/60 rounded-full" style={{ width: `${pct}%` }} />
                  </div>
                  <span className="text-xs text-muted-foreground w-8 text-right">{cnt}</span>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Novel Topics */}
      {stats.novel_topics.length > 0 && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h3 className="text-sm font-medium text-amber-900 mb-3">Novel Topics (not in handbook)</h3>
          <div className="space-y-2">
            {stats.novel_topics.map(({ topic_guess, cnt }) => (
              <div key={topic_guess} className="flex items-center justify-between">
                <span className="text-sm text-amber-800">{topic_guess}</span>
                <span className="rounded-full bg-amber-200 px-2 py-0.5 text-xs text-amber-900">{cnt} question{cnt > 1 ? "s" : ""}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Triage by Topic */}
      {stats.by_topic.length > 0 && (
        <div className="rounded-xl border border-border p-4">
          <h3 className="text-sm font-medium text-foreground mb-3">Open Triage by Topic</h3>
          <div className="space-y-2">
            {stats.by_topic.map(({ topic, cnt }) => (
              <div key={topic} className="flex items-center justify-between">
                <span className="text-sm text-foreground">{topic.replace(/_/g, " ")}</span>
                <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800">{cnt} open</span>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

function StatCard({ label, value, accent }: { label: string; value: string | number; accent?: "red" | "green" | "amber" }) {
  return (
    <div className="rounded-xl border border-border p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className={cn(
        "text-2xl font-bold mt-1",
        accent === "red" && "text-red-600",
        accent === "green" && "text-green-600",
        accent === "amber" && "text-amber-600",
        !accent && "text-foreground"
      )}>
        {value}
      </p>
    </div>
  );
}
