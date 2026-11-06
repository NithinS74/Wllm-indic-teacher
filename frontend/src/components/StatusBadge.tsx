import { Badge } from "@/components/ui/badge";
import type { JobStage, LectureStatus } from "@/types";
import { cn } from "@/lib/utils";

const statusStyles: Record<string, string> = {
  COMPLETED: "border-emerald-200 bg-emerald-50 text-emerald-700",
  FAILED: "border-red-200 bg-red-50 text-red-700",
  PROCESSING: "border-blue-200 bg-blue-50 text-blue-700",
  QUEUED: "border-zinc-200 bg-zinc-50 text-zinc-600",
};

export function StatusBadge({ status }: { status: LectureStatus | JobStage }) {
  const cls = statusStyles[status] ?? statusStyles.QUEUED;
  const terminal =
    status === "COMPLETED" || status === "FAILED" || status === "QUEUED";
  const active = status === "PROCESSING" || !terminal;
  return (
    <Badge className={cn(cls, "gap-1.5")}>
      {active && status !== "PROCESSING" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {status === "PROCESSING" && (
        <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
      )}
      {status.replace(/_/g, " ")}
    </Badge>
  );
}

export const STAGE_LABELS: Record<JobStage, string> = {
  QUEUED: "Audio uploaded",
  PREPROCESSING: "Audio preprocessing",
  TRANSCRIBING: "Speech recognition",
  TRANSLATING_INPUT: "Input translation",
  GENERATING_NOTES: "Generating notes",
  GENERATING_QUIZ: "Generating quiz",
  TRANSLATING_OUTPUT: "Output translation",
  VALIDATING: "Validating results",
  COMPLETED: "Completed",
  FAILED: "Failed",
};
