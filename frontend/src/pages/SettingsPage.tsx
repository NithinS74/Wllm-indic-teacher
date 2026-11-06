import { Cpu, Database, Languages, Server, Sparkles } from "lucide-react";
import { useSettings } from "@/hooks/useApi";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";

export function SettingsPage() {
  const { data, isLoading } = useSettings();

  return (
    <div className="mx-auto max-w-4xl px-4 py-8 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          Settings
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Runtime configuration and AI provider status.
        </p>
      </div>

      <div className="space-y-6">
        {/* Providers */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Cpu className="h-4 w-4 text-primary" /> AI providers
            </CardTitle>
            <CardDescription>
              Mock providers are used for development and demos — results are
              clearly flagged in the UI. Real checkpoints are loaded lazily on
              first use, never at startup.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {isLoading && (
              <>
                <Skeleton className="h-16 w-full" />
                <Skeleton className="h-16 w-full" />
              </>
            )}
            {data?.providers.map((p) => (
              <div
                key={p.name}
                className="flex flex-wrap items-start justify-between gap-3 rounded-md border border-zinc-200 p-4"
              >
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <p className="text-sm font-medium capitalize text-zinc-900">
                      {p.name}
                    </p>
                    <Badge
                      className={
                        p.mode === "mock"
                          ? "border-amber-200 bg-amber-50 text-amber-700"
                          : "border-emerald-200 bg-emerald-50 text-emerald-700"
                      }
                    >
                      {p.mode === "mock" ? "mock" : "real"}
                    </Badge>
                    {p.loaded && (
                      <Badge className="border-zinc-200 bg-zinc-50 text-zinc-500">
                        loaded
                      </Badge>
                    )}
                  </div>
                  <p className="mt-1 break-words text-xs text-zinc-500">
                    <span className="font-medium">{p.provider}</span> — {p.detail}
                  </p>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        {/* Languages */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Languages className="h-4 w-4 text-primary" /> Supported languages
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {isLoading && <Skeleton className="h-12 w-full" />}
              {data?.languages.map((l) => (
                <div
                  key={l.key}
                  className="flex items-center justify-between rounded-md border border-zinc-200 px-3 py-2.5"
                >
                  <div>
                    <p className="text-sm font-medium text-zinc-800">{l.label}</p>
                    <p className="text-xs text-zinc-500">{l.script} script</p>
                  </div>
                  <code className="text-xs text-zinc-400">{l.indictrans}</code>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Limits */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Server className="h-4 w-4 text-primary" /> Upload & processing limits
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <dl className="grid gap-x-8 gap-y-3 text-sm sm:grid-cols-2">
                <Row
                  label="Max file size"
                  value={`${Math.round((data?.limits.max_upload_bytes ?? 0) / (1024 * 1024))} MB`}
                />
                <Row
                  label="Max duration"
                  value={`${Math.round((data?.limits.max_audio_duration_seconds ?? 0) / 60)} min`}
                />
                <Row
                  label="Min duration"
                  value={`${data?.limits.min_audio_duration_seconds ?? 0} s`}
                />
                <Row
                  label="Chunk length"
                  value={`${data?.limits.chunk_duration_seconds ?? 0} s (speech-aware)`}
                />
                <Row
                  label="Accepted formats"
                  value={(data?.limits.allowed_extensions ?? [])
                    .join(", ")
                    .toUpperCase()}
                />
                <Row label="Storage" value="Local filesystem (server-side)" />
              </dl>
            )}
          </CardContent>
        </Card>

        {/* Stack */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-4 w-4 text-primary" /> Application
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-zinc-600">
            <p className="flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              {data?.app_name ?? "LectureLens"} — React + FastAPI + PostgreSQL +
              Redis/RQ. Model integration: IndicConformer (ASR), Param-1
              (notes/quiz), IndicTrans2 (translation).
            </p>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between border-b border-zinc-100 pb-2">
      <dt className="text-zinc-500">{label}</dt>
      <dd className="font-medium text-zinc-800">{value}</dd>
    </div>
  );
}
