import { useEffect } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowRight, CheckCircle2, RefreshCw } from "lucide-react";
import { useJob, useLecture } from "@/hooks/useApi";
import { StageList } from "@/components/processing/StageList";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useToast } from "@/components/ui/toast";

export function ProcessingPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const { data: job, isLoading, error, refetch } = useJob(jobId);
  const { data: lecture } = useLecture(job?.lecture_id);
  const { info } = useToast();

  const done = job?.status === "COMPLETED";
  const failed = job?.status === "FAILED";

  useEffect(() => {
    if (done) {
      info("Processing complete", "Your study material is ready.");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [done]);

  useEffect(() => {
    if (done && job) {
      const t = window.setTimeout(() => {
        navigate(`/lectures/${job.lecture_id}`, { replace: true });
      }, 1400);
      return () => window.clearTimeout(t);
    }
  }, [done, job, navigate]);

  return (
    <div className="mx-auto max-w-2xl px-4 py-10 lg:px-8">
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold tracking-tight text-zinc-900">
            {lecture ? lecture.title : "Processing lecture"}
          </h1>
          <div className="mt-2 flex items-center gap-2">
            {job && <StatusBadge status={job.status} />}
            {lecture && (
              <span className="text-xs text-zinc-500">
                {lecture.source_language.toUpperCase()}
                {lecture.target_language &&
                  ` → ${lecture.target_language.toUpperCase()}`}
              </span>
            )}
          </div>
        </div>
        <Button variant="ghost" size="sm" onClick={() => refetch()}>
          <RefreshCw className="h-3.5 w-3.5" /> Refresh
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Processing stages</CardTitle>
        </CardHeader>
        <CardContent>
          {isLoading && (
            <div className="space-y-3">
              <Skeleton className="h-5 w-2/3" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-4/5" />
            </div>
          )}

          {error && (
            <div className="text-center">
              <p className="text-sm text-red-600">
                Could not load job status.
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() => refetch()}
              >
                Try again
              </Button>
            </div>
          )}

          {job && <StageList job={job} />}
        </CardContent>
      </Card>

      <div className="mt-6 flex justify-center">
        {failed ? (
          <div className="flex flex-col items-center gap-3">
            <p className="text-sm text-zinc-600">
              Processing failed — you can delete this lecture and try a
              different recording.
            </p>
            <div className="flex gap-2">
              <Button variant="secondary" asChild>
                <Link to="/lectures">Back to lectures</Link>
              </Button>
              <Button asChild>
                <Link to="/new">
                  New lecture <ArrowRight className="h-4 w-4" />
                </Link>
              </Button>
            </div>
          </div>
        ) : done ? (
          <p className="flex items-center gap-2 text-sm font-medium text-emerald-700">
            <CheckCircle2 className="h-4 w-4" /> Opening your workspace…
          </p>
        ) : (
          <p className="text-sm text-zinc-500">
            You can leave this page — processing continues in the background.
          </p>
        )}
      </div>
    </div>
  );
}
