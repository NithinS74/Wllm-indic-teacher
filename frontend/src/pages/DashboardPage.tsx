import { Link, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BookOpenCheck,
  FileAudio,
  GraduationCap,
  Inbox,
  Plus,
  RefreshCw,
  Timer,
} from "lucide-react";
import { useLectures } from "@/hooks/useApi";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDate, formatDuration } from "@/lib/utils";
import { LANG_LABEL } from "@/lib/languages";

export function DashboardPage() {
  const { data, isLoading, error, refetch } = useLectures();
  const navigate = useNavigate();

  const lectures = data ?? [];
  const completed = lectures.filter((l) => l.status === "COMPLETED").length;
  const processing = lectures.filter(
    (l) => l.status === "QUEUED" || l.status === "PROCESSING",
  ).length;
  const failed = lectures.filter((l) => l.status === "FAILED").length;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 lg:px-8">
      {/* Welcome */}
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Welcome back
          </h1>
          <p className="mt-1 text-sm text-zinc-500">
            Turn lecture recordings into structured notes and practice quizzes.
          </p>
        </div>
        <Button onClick={() => navigate("/new")}>
          <Plus className="h-4 w-4" /> New Lecture
        </Button>
      </div>

      {/* Stats */}
      <div className="mb-8 grid gap-4 sm:grid-cols-3">
        <StatCard
          icon={<BookOpenCheck className="h-4 w-4 text-emerald-600" />}
          label="Completed"
          value={completed}
        />
        <StatCard
          icon={<RefreshCw className="h-4 w-4 text-blue-600" />}
          label="In progress"
          value={processing}
        />
        <StatCard
          icon={<FileAudio className="h-4 w-4 text-zinc-500" />}
          label="Total lectures"
          value={lectures.length}
        />
      </div>

      {/* Recent */}
      <div className="rounded-lg border border-zinc-200 bg-white shadow-sm">
        <div className="flex items-center justify-between border-b border-zinc-200 px-5 py-4">
          <h2 className="text-sm font-semibold text-zinc-900">
            Recently processed
          </h2>
          <Link
            to="/lectures"
            className="flex items-center gap-1 text-sm font-medium text-primary hover:underline"
          >
            View all <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>

        {isLoading && (
          <div className="space-y-3 p-5">
            {[0, 1, 2].map((i) => (
              <div key={i} className="flex items-center gap-4">
                <Skeleton className="h-10 w-10 rounded-md" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-1/3" />
                  <Skeleton className="h-3 w-1/4" />
                </div>
              </div>
            ))}
          </div>
        )}

        {error && (
          <div className="p-5 text-center">
            <p className="text-sm text-red-600">
              Could not load lectures. Is the API running?
            </p>
            <Button variant="secondary" size="sm" className="mt-3" onClick={() => refetch()}>
              Try again
            </Button>
          </div>
        )}

        {!isLoading && !error && lectures.length === 0 && (
          <div className="flex flex-col items-center px-5 py-14 text-center">
            <div className="flex h-12 w-12 items-center justify-center rounded-full bg-zinc-100">
              <Inbox className="h-6 w-6 text-zinc-400" />
            </div>
            <p className="mt-3 text-sm font-medium text-zinc-700">
              No lectures yet
            </p>
            <p className="mt-1 max-w-sm text-sm text-zinc-500">
              Upload your first recording to generate structured notes and a
              five-question quiz automatically.
            </p>
            <Button className="mt-4" onClick={() => navigate("/new")}>
              <Plus className="h-4 w-4" /> Upload a lecture
            </Button>
          </div>
        )}

        {!isLoading && !error && lectures.length > 0 && (
          <ul className="divide-y divide-zinc-100">
            {lectures.slice(0, 6).map((l) => (
              <li key={l.id}>
                <Link
                  to={
                    l.status === "COMPLETED"
                      ? `/lectures/${l.id}`
                      : l.job_id
                        ? `/processing/${l.job_id}`
                        : `/lectures/${l.id}`
                  }
                  className="flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-zinc-50"
                >
                  <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                    <GraduationCap className="h-5 w-5" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-zinc-900">
                      {l.title}
                    </p>
                    <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-xs text-zinc-500">
                      <span>{LANG_LABEL[l.source_language] ?? l.source_language}</span>
                      <span>·</span>
                      <span>{formatDate(l.created_at)}</span>
                      {l.duration != null && (
                        <>
                          <span>·</span>
                          <span className="inline-flex items-center gap-1">
                            <Timer className="h-3 w-3" />
                            {formatDuration(l.duration)}
                          </span>
                        </>
                      )}
                    </p>
                  </div>
                  <StatusBadge status={l.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </div>

      {failed > 0 && (
        <p className="mt-4 text-sm text-zinc-500">
          {failed} lecture{failed > 1 ? "s" : ""} failed — open them from My
          Lectures to see the error.
        </p>
      )}
    </div>
  );
}

function StatCard({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: number;
}) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-10 w-10 items-center justify-center rounded-md bg-zinc-100">
          {icon}
        </div>
        <div>
          <p className="text-2xl font-semibold tabular-nums text-zinc-900">
            {value}
          </p>
          <p className="text-xs text-zinc-500">{label}</p>
        </div>
      </CardContent>
    </Card>
  );
}
