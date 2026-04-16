import { useState } from "react";
import { CheckCircle, X, ChevronDown, ChevronUp, BookOpen } from "lucide-react";
import { cn } from "../lib/utils";
import type { TriageItem } from "../lib/api";
import { api } from "../lib/api";

interface TriageQueueProps {
  items: TriageItem[];
  onRefresh: () => void;
}

export function TriageQueue({ items, onRefresh }: TriageQueueProps) {
  if (items.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
        <CheckCircle className="h-12 w-12 mb-3 text-green-400" />
        <p className="text-lg font-medium">All caught up!</p>
        <p className="text-sm">No items in the triage queue.</p>
      </div>
    );
  }

  const grouped = items.reduce<Record<string, TriageItem[]>>((acc, item) => {
    const key = item.topic === "other" && item.topic_guess ? item.topic_guess : item.topic;
    if (!acc[key]) acc[key] = [];
    acc[key].push(item);
    return acc;
  }, {});

  return (
    <div className="space-y-4">
      {Object.entries(grouped).map(([topic, group]) => (
        <TopicGroup key={topic} topic={topic} items={group} onRefresh={onRefresh} />
      ))}
    </div>
  );
}

function TopicGroup({ topic, items, onRefresh }: { topic: string; items: TriageItem[]; onRefresh: () => void }) {
  const [expanded, setExpanded] = useState(true);
  const hasHigh = items.some((i) => i.priority === "high");
  const isNovel = items.some((i) => i.topic === "other");

  return (
    <div className="rounded-xl border border-border overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between p-4 hover:bg-secondary/50 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className={cn(
            "h-3 w-3 rounded-full",
            hasHigh ? "bg-red-500" : isNovel ? "bg-amber-500" : "bg-blue-500"
          )} />
          <span className="font-medium text-sm">{items.length} question{items.length > 1 ? "s" : ""} about {topic.replace(/_/g, " ")}</span>
          {isNovel && (
            <span className="rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">Novel topic</span>
          )}
          {hasHigh && (
            <span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800">High priority</span>
          )}
        </div>
        {expanded ? <ChevronUp className="h-4 w-4 text-muted-foreground" /> : <ChevronDown className="h-4 w-4 text-muted-foreground" />}
      </button>

      {expanded && (
        <div className="border-t border-border divide-y divide-border">
          {items.map((item) => (
            <TriageCard key={item.id} item={item} onRefresh={onRefresh} />
          ))}
        </div>
      )}
    </div>
  );
}

function TriageCard({ item, onRefresh }: { item: TriageItem; onRefresh: () => void }) {
  const [resolving, setResolving] = useState(false);
  const [resolution, setResolution] = useState("");
  const [promoteToOverride, setPromoteToOverride] = useState(true);
  const [loading, setLoading] = useState(false);

  const handleResolve = async () => {
    if (!resolution.trim()) return;
    setLoading(true);
    try {
      await api.resolveTriage(item.id, {
        resolution_text: resolution,
        promote_to_override: promoteToOverride,
        override_topic: item.topic,
      });
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    setLoading(true);
    try {
      await api.dismissTriage(item.id);
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="p-4 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 mb-1">
            <span className={cn(
              "rounded-full px-2 py-0.5 text-xs font-medium",
              item.priority === "high" ? "bg-red-100 text-red-800" : "bg-blue-100 text-blue-800"
            )}>
              {item.priority}
            </span>
            <span className="text-xs text-muted-foreground">{item.escalation_reason}</span>
            {item.parent_email && (
              <span className="text-xs text-muted-foreground">({item.parent_email})</span>
            )}
          </div>
          <p className="text-sm font-medium text-foreground">{item.question}</p>
          {item.answer && (
            <p className="text-sm text-muted-foreground mt-1 line-clamp-2">AI answered: {item.answer}</p>
          )}
        </div>
        <div className="flex gap-1 shrink-0">
          {!resolving && (
            <>
              <button
                onClick={() => setResolving(true)}
                className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
              >
                <CheckCircle className="h-3 w-3" /> Resolve
              </button>
              <button
                onClick={handleDismiss}
                disabled={loading}
                className="flex items-center gap-1 rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary transition-colors"
              >
                <X className="h-3 w-3" /> Dismiss
              </button>
            </>
          )}
        </div>
      </div>

      {resolving && (
        <div className="space-y-2 pt-2 border-t border-border">
          <textarea
            value={resolution}
            onChange={(e) => setResolution(e.target.value)}
            placeholder="Type your answer for the parent..."
            className="w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring min-h-[80px] resize-y"
          />
          <div className="flex items-center justify-between">
            <label className="flex items-center gap-2 text-xs text-muted-foreground cursor-pointer">
              <input
                type="checkbox"
                checked={promoteToOverride}
                onChange={(e) => setPromoteToOverride(e.target.checked)}
                className="rounded border-input"
              />
              <BookOpen className="h-3 w-3" />
              Save as knowledge override
            </label>
            <div className="flex gap-2">
              <button
                onClick={() => setResolving(false)}
                className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleResolve}
                disabled={loading || !resolution.trim()}
                className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
              >
                {loading ? "Saving..." : "Save & Resolve"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
