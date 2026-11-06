import { CheckCircle2, Circle, Loader2, XCircle } from "lucide-react";
import type { Job, JobStage } from "@/types";
import { STAGE_LABELS } from "@/components/StatusBadge";
import { cn } from "@/lib/utils";
import { Progress } from "@/components/ui/progress";

export function StageList({ job }: { job: Job }) {
  const stages: JobStage[] = (job.stages ??
    (Object.keys(STAGE_LABELS) as JobStage[])).filter((s) => s !== "FAILED");
  const currentIdx = stages.indexOf(job.current_stage);
  const failed = job.status === "FAILED";

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm font-medium text-zinc-700">
            {failed ? "Processing failed" : job.status === "COMPLETED" ? "All stages complete" : "Processing…"}
          </p>
          <p className="text-xs text-zinc-500">
            {failed
              ? job.error_message ?? "An error occurred."
              : STAGE_LABELS[job.current_stage] ?? job.current_stage}
          </p>
        </div>
        <span className="text-sm font-medium tabular-nums text-zinc-600">
          {Math.round((job.progress ?? 0) * 100)}%
        </span>
      </div>
      <Progress value={job.progress ?? 0} />

      <ol className="space-y-1">
        {stages.map((stage, i) => {
          const done =
            (!failed && i < currentIdx) ||
            (job.status === "COMPLETED" && stage === "COMPLETED");
          const active = !failed && stage === job.current_stage && job.status !== "COMPLETED";
          return (
            <li
              key={stage}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm",
                active && "bg-primary/5",
              )}
            >
              {done ? (
                <CheckCircle2 className="h-4 w-4 shrink-0 text-emerald-600" />
              ) : active ? (
                <Loader2 className="h-4 w-4 shrink-0 animate-spin text-primary" />
              ) : failed && i === currentIdx ? (
                <XCircle className="h-4 w-4 shrink-0 text-red-600" />
              ) : (
                <Circle className="h-4 w-4 shrink-0 text-zinc-300" />
              )}
              <span
                className={cn(
                  done && "text-zinc-500",
                  active && "font-medium text-zinc-900",
                  !done && !active && "text-zinc-400",
                  failed && i === currentIdx && "font-medium text-red-700",
                )}
              >
                {STAGE_LABELS[stage] ?? stage}
              </span>
            </li>
          );
        })}
      </ol>

      {failed && job.error_message && (
        <div className="rounded-md border border-red-200 bg-red-50 p-4">
          <p className="text-sm font-medium text-red-800">Error details</p>
          <p className="mt-1 break-words text-sm text-red-700">
            {job.error_message}
          </p>
        </div>
      )}
    </div>
  );
}
