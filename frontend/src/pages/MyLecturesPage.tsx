import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import {
  ArrowUpDown,
  GraduationCap,
  Plus,
  Search,
  Trash2,
} from "lucide-react";
import { useDeleteLecture, useLectures } from "@/hooks/useApi";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { useToast } from "@/components/ui/toast";
import { formatDate, formatDuration } from "@/lib/utils";
import { LANG_LABEL } from "@/lib/languages";

export function MyLecturesPage() {
  const { data, isLoading, error, refetch } = useLectures();
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<string>("ALL");
  const [toDelete, setToDelete] = useState<{ id: string; title: string } | null>(
    null,
  );
  const remove = useDeleteLecture();
  const { success, error: toastError } = useToast();
  const navigate = useNavigate();

  const lectures = (data ?? []).filter((l) => {
    const matchesQuery =
      !query.trim() ||
      l.title.toLowerCase().includes(query.trim().toLowerCase());
    const matchesFilter = filter === "ALL" || l.status === filter;
    return matchesQuery && matchesFilter;
  });

  const confirmDelete = async () => {
    if (!toDelete) return;
    try {
      await remove.mutateAsync(toDelete.id);
      success("Lecture deleted", toDelete.title);
      setToDelete(null);
    } catch (err) {
      toastError("Delete failed", (err as Error).message);
    }
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 lg:px-8">
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            My Lectures
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            All uploaded recordings and their processing status.
          </p>
        </div>
        <Button onClick={() => navigate("/new")}>
          <Plus className="h-4 w-4" /> New Lecture
        </Button>
      </div>

      {/* Filters */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[220px]">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Search by title…"
            className="pl-9"
            aria-label="Search lectures"
          />
        </div>
        <div className="flex gap-1 rounded-lg bg-zinc-100 p-1">
          {["ALL", "COMPLETED", "PROCESSING", "FAILED"].map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                filter === f
                  ? "bg-white text-zinc-900 shadow-sm"
                  : "text-zinc-500 hover:text-zinc-800"
              }`}
            >
              {f === "ALL" ? "All" : f.charAt(0) + f.slice(1).toLowerCase()}
            </button>
          ))}
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <ArrowUpDown className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      <div className="overflow-hidden rounded-lg border border-zinc-200 bg-white shadow-sm">
        {isLoading && (
          <div className="space-y-3 p-5">
            {[0, 1, 2, 3].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-9 w-9 rounded-md" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-5 w-20" />
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="p-6 text-center text-sm text-red-600">
            Failed to load lectures.
          </div>
        )}

        {!isLoading && !error && lectures.length === 0 && (
          <div className="p-10 text-center">
            <GraduationCap className="mx-auto h-8 w-8 text-zinc-300" />
            <p className="mt-3 text-sm font-medium text-zinc-700">
              {query || filter !== "ALL" ? "No matching lectures" : "No lectures yet"}
            </p>
            <Button className="mt-4" size="sm" onClick={() => navigate("/new")}>
              <Plus className="h-3.5 w-3.5" /> Upload your first lecture
            </Button>
          </div>
        )}

        {!isLoading && !error && lectures.length > 0 && (
          <ul className="divide-y divide-zinc-100">
            {lectures.map((l) => (
              <li
                key={l.id}
                className="flex items-center gap-4 px-5 py-4 transition-colors hover:bg-zinc-50/70"
              >
                <Link
                  to={
                    l.status === "COMPLETED"
                      ? `/lectures/${l.id}`
                      : l.job_id
                        ? `/processing/${l.job_id}`
                        : "#"
                  }
                  className="min-w-0 flex-1"
                >
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="truncate text-sm font-medium text-zinc-900">
                      {l.title}
                    </p>
                    {l.translate_content && l.target_language && (
                      <Badge className="border-zinc-200 bg-zinc-50 text-zinc-500">
                        → {LANG_LABEL[l.target_language] ?? l.target_language}
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 flex flex-wrap gap-x-2 text-xs text-zinc-500">
                    <span>
                      {LANG_LABEL[l.source_language] ?? l.source_language}
                    </span>
                    <span>·</span>
                    <span>{formatDate(l.created_at)}</span>
                    {l.duration != null && (
                      <>
                        <span>·</span>
                        <span>{formatDuration(l.duration)}</span>
                      </>
                    )}
                    {l.current_stage && l.status === "PROCESSING" && (
                      <>
                        <span>·</span>
                        <span className="text-blue-600">
                          {l.current_stage.replace(/_/g, " ")}
                        </span>
                      </>
                    )}
                  </p>
                  {l.status === "FAILED" && l.error_message && (
                    <p className="mt-1 truncate text-xs text-red-600">
                      {l.error_message}
                    </p>
                  )}
                </Link>

                <StatusBadge status={l.status} />

                <div className="flex items-center gap-1">
                  {l.status === "COMPLETED" && (
                    <>
                      <Link
                        to={`/lectures/${l.id}?tab=transcript`}
                        className="rounded-md px-2 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
                      >
                        Transcript
                      </Link>
                      <Link
                        to={`/lectures/${l.id}?tab=notes`}
                        className="rounded-md px-2 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
                      >
                        Notes
                      </Link>
                      <Link
                        to={`/lectures/${l.id}?tab=quiz`}
                        className="rounded-md px-2 py-1.5 text-xs font-medium text-zinc-500 hover:bg-zinc-100 hover:text-zinc-800"
                      >
                        Quiz
                      </Link>
                    </>
                  )}
                  <button
                    onClick={() => setToDelete({ id: l.id, title: l.title })}
                    className="rounded-md p-1.5 text-zinc-400 hover:bg-red-50 hover:text-red-600"
                    aria-label={`Delete ${l.title}`}
                  >
                    <Trash2 className="h-4 w-4" />
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* Delete confirmation */}
      <Dialog open={!!toDelete} onOpenChange={(o) => !o && setToDelete(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete lecture?</DialogTitle>
            <DialogDescription>
              “{toDelete?.title}” and its transcript, notes, quiz attempts and
              audio file will be permanently removed. This cannot be undone.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="secondary" onClick={() => setToDelete(null)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={confirmDelete}
              disabled={remove.isPending}
            >
              {remove.isPending ? "Deleting…" : "Delete"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
