import { useState } from "react";
import {
  Trash2,
  FileText,
  AlertCircle,
  CheckCircle2,
  Loader2,
  ChevronDown,
  ChevronRight,
} from "lucide-react";
import { api } from "../lib/api";
import type { DocumentItem, DocumentSection } from "../lib/api";
import { cn } from "../lib/utils";

interface DocumentsListProps {
  documents: DocumentItem[];
  onRefresh: () => void;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "ready") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-2 py-0.5 text-xs text-green-800">
        <CheckCircle2 className="h-3 w-3" /> ready
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800">
        <AlertCircle className="h-3 w-3" /> failed
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-100 px-2 py-0.5 text-xs text-amber-800">
      <Loader2 className="h-3 w-3 animate-spin" /> {status}
    </span>
  );
}

function formatPageRange(section: DocumentSection): string | null {
  if (section.page_start == null) return null;
  if (section.page_end == null || section.page_end === section.page_start) {
    return `p. ${section.page_start}`;
  }
  return `pp. ${section.page_start}–${section.page_end}`;
}

function SectionsTable({ sections }: { sections: DocumentSection[] }) {
  if (sections.length === 0) {
    return (
      <p className="text-xs text-muted-foreground italic">
        No sections were incorporated from this document.
      </p>
    );
  }

  const topicCounts = sections.reduce<Record<string, number>>((acc, s) => {
    acc[s.topic] = (acc[s.topic] || 0) + 1;
    return acc;
  }, {});

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-1.5">
        {Object.entries(topicCounts)
          .sort((a, b) => b[1] - a[1])
          .map(([topic, count]) => (
            <span
              key={topic}
              className="rounded-full bg-purple-50 px-2 py-0.5 text-xs text-purple-800 border border-purple-200"
            >
              {topic.replace(/_/g, " ")} · {count}
            </span>
          ))}
      </div>

      <div className="rounded-lg border border-border overflow-hidden">
        <table className="w-full text-xs">
          <thead className="bg-secondary/60">
            <tr>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground w-8">#</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground">Heading</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground w-28">Topic</th>
              <th className="text-left px-3 py-2 font-medium text-muted-foreground w-20">Pages</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {sections.map((s) => (
              <tr key={s.chunk_index} className="hover:bg-secondary/30">
                <td className="px-3 py-2 text-muted-foreground tabular-nums">
                  {s.chunk_index}
                </td>
                <td className="px-3 py-2 font-mono text-[0.7rem] leading-snug">
                  {s.heading_path || (
                    <span className="italic text-muted-foreground">(untitled)</span>
                  )}
                </td>
                <td className="px-3 py-2">
                  <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[0.7rem] text-gray-700">
                    {s.topic.replace(/_/g, " ")}
                  </span>
                </td>
                <td className="px-3 py-2 text-muted-foreground tabular-nums">
                  {formatPageRange(s) || "—"}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function DocumentsList({ documents, onRefresh }: DocumentsListProps) {
  const [deletingId, setDeletingId] = useState<number | null>(null);
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});

  const toggleExpanded = (id: number) => {
    setExpanded((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleDelete = async (doc: DocumentItem) => {
    const ok = window.confirm(
      `Delete "${doc.filename}"?\n\nThis removes the database records and the file on disk. This cannot be undone.`
    );
    if (!ok) return;
    setDeletingId(doc.id);
    try {
      const res = await api.deleteDocument(doc.id);
      if (!res.file_deleted && res.file_error) {
        console.warn("DB record removed but file deletion failed:", res.file_error);
      }
      onRefresh();
    } catch (err) {
      console.error(err);
      window.alert("Failed to delete document. See console for details.");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-medium text-foreground">
          Documents ({documents.length})
        </h3>
        <p className="text-xs text-muted-foreground">
          Drop PDFs into the <code className="rounded bg-secondary px-1 py-0.5">docs/</code> folder
          and restart to ingest.
        </p>
      </div>

      {documents.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-16 text-muted-foreground">
          <FileText className="h-12 w-12 mb-3 text-gray-300" />
          <p className="text-lg font-medium">No documents yet</p>
          <p className="text-sm">
            Drop a PDF into the <code className="rounded bg-secondary px-1 py-0.5">docs/</code>{" "}
            folder and restart the app.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {documents.map((doc) => {
            const isOpen = !!expanded[doc.id];
            const canExpand = doc.status === "ready" && doc.sections.length > 0;

            return (
              <div key={doc.id} className="rounded-xl border border-border">
                <div className="p-4 flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1 flex-wrap">
                      <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
                      <p className="text-sm font-medium text-foreground truncate">
                        {doc.filename}
                      </p>
                      <StatusBadge status={doc.status} />
                    </div>

                    {doc.summary && (
                      <p className="mt-2 text-sm text-foreground/80 leading-relaxed">
                        {doc.summary}
                      </p>
                    )}

                    <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                      {doc.page_count !== null && <span>{doc.page_count} pages</span>}
                      {doc.chunk_count !== null && (
                        <span>
                          {doc.chunk_count} section{doc.chunk_count === 1 ? "" : "s"} incorporated
                        </span>
                      )}
                      {doc.processed_at && (
                        <span>
                          processed {new Date(doc.processed_at).toLocaleString()}
                        </span>
                      )}
                      {!doc.processed_at && doc.uploaded_at && (
                        <span>added {new Date(doc.uploaded_at).toLocaleString()}</span>
                      )}
                    </div>

                    {doc.status === "failed" && doc.error_message && (
                      <p className="mt-2 rounded-md bg-red-50 px-2 py-1 text-xs text-red-800 font-mono break-all">
                        {doc.error_message}
                      </p>
                    )}

                    {canExpand && (
                      <button
                        onClick={() => toggleExpanded(doc.id)}
                        className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                      >
                        {isOpen ? (
                          <ChevronDown className="h-3.5 w-3.5" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5" />
                        )}
                        {isOpen ? "Hide sections" : "Show sections"}
                      </button>
                    )}
                  </div>

                  <button
                    onClick={() => handleDelete(doc)}
                    disabled={deletingId === doc.id}
                    title="Delete document and remove file from disk"
                    className={cn(
                      "flex h-8 w-8 items-center justify-center rounded-lg transition-colors shrink-0",
                      "hover:bg-destructive/10 text-muted-foreground hover:text-destructive",
                      deletingId === doc.id && "opacity-50 cursor-not-allowed"
                    )}
                  >
                    {deletingId === doc.id ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Trash2 className="h-4 w-4" />
                    )}
                  </button>
                </div>

                {isOpen && canExpand && (
                  <div className="border-t border-border bg-secondary/20 px-4 py-3">
                    <SectionsTable sections={doc.sections} />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
