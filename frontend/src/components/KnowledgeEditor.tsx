import { useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api } from "../lib/api";
import type { Override } from "../lib/api";

const TOPICS = [
  "hours", "tuition", "sick_policy", "meals", "tours", "enrollment",
  "holidays", "billing", "staff", "curriculum", "safety", "other",
];

interface KnowledgeEditorProps {
  overrides: Override[];
  onRefresh: () => void;
}

export function KnowledgeEditor({ overrides, onRefresh }: KnowledgeEditorProps) {
  const [adding, setAdding] = useState(false);
  const [topic, setTopic] = useState("other");
  const [pattern, setPattern] = useState("");
  const [answer, setAnswer] = useState("");
  const [loading, setLoading] = useState(false);

  const handleAdd = async () => {
    if (!pattern.trim() || !answer.trim()) return;
    setLoading(true);
    try {
      await api.createOverride({ topic, question_pattern: pattern, answer });
      setAdding(false);
      setPattern("");
      setAnswer("");
      onRefresh();
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteOverride(id);
      onRefresh();
    } catch (err) {
      console.error(err);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">Knowledge Overrides ({overrides.length})</h3>
        {!adding && (
          <button
            onClick={() => setAdding(true)}
            className="flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-3 w-3" /> Add Override
          </button>
        )}
      </div>

      {adding && (
        <div className="rounded-xl border border-border p-4 space-y-3">
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Topic</label>
            <select
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              className="w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring bg-background"
            >
              {TOPICS.map((t) => (
                <option key={t} value={t}>{t.replace(/_/g, " ")}</option>
              ))}
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Question Pattern</label>
            <input
              type="text"
              value={pattern}
              onChange={(e) => setPattern(e.target.value)}
              placeholder='e.g., "Are you open on Christmas Eve?"'
              className="w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
            />
          </div>
          <div>
            <label className="block text-xs font-medium text-muted-foreground mb-1">Answer</label>
            <textarea
              value={answer}
              onChange={(e) => setAnswer(e.target.value)}
              placeholder="The answer parents should receive..."
              className="w-full rounded-lg border border-input px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring min-h-[80px] resize-y"
            />
          </div>
          <div className="flex gap-2 justify-end">
            <button
              onClick={() => { setAdding(false); setPattern(""); setAnswer(""); }}
              className="rounded-lg border border-border px-3 py-1.5 text-xs text-muted-foreground hover:bg-secondary transition-colors"
            >
              Cancel
            </button>
            <button
              onClick={handleAdd}
              disabled={loading || !pattern.trim() || !answer.trim()}
              className="rounded-lg bg-primary px-3 py-1.5 text-xs font-medium text-primary-foreground hover:bg-primary/90 transition-colors disabled:opacity-50"
            >
              {loading ? "Saving..." : "Save Override"}
            </button>
          </div>
        </div>
      )}

      {overrides.length === 0 && !adding ? (
        <p className="text-sm text-muted-foreground py-8 text-center">
          No knowledge overrides yet. Overrides are created when you resolve triage items or add them manually.
        </p>
      ) : (
        <div className="space-y-2">
          {overrides.map((o) => (
            <div key={o.id} className="rounded-xl border border-border p-4">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs text-purple-800">
                      {o.topic.replace(/_/g, " ")}
                    </span>
                    <span className="text-xs text-muted-foreground">by {o.author}</span>
                  </div>
                  <p className="text-sm font-medium text-foreground">{o.question_pattern}</p>
                  <p className="text-sm text-muted-foreground mt-1">{o.answer}</p>
                </div>
                <button
                  onClick={() => handleDelete(o.id)}
                  className="flex h-8 w-8 items-center justify-center rounded-lg hover:bg-destructive/10 text-muted-foreground hover:text-destructive transition-colors shrink-0"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
