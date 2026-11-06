import { GraduationCap, Github, Info } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";

export function AboutPage() {
  return (
    <div className="mx-auto max-w-3xl px-4 py-8 lg:px-8">
      <div className="mb-6 flex items-center gap-3">
        <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-primary text-white">
          <GraduationCap className="h-6 w-6" />
        </div>
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            LectureLens
          </h1>
          <p className="text-sm text-zinc-500">
            Multilingual AI lecture-to-notes & quiz generator
          </p>
        </div>
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader>
            <CardTitle>What it does</CardTitle>
          </CardHeader>
          <CardContent className="text-sm leading-relaxed text-zinc-700">
            <p>
              Upload a lecture recording in English, Hindi, Kannada, Tamil,
              Telugu or Malayalam. LectureLens transcribes it with
              IndicConformer, translates when needed with IndicTrans2, and uses
              BharatGen Param-1 to generate structured notes and exactly five
              multiple-choice questions with explanations. Everything can be
              translated, reviewed and exported.
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Info className="h-4 w-4 text-primary" /> Pipeline
            </CardTitle>
            <CardDescription>
              Long-running inference happens in background RQ workers — the API
              never blocks on model execution.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ol className="list-decimal space-y-1.5 pl-5 text-sm text-zinc-700">
              <li>Audio validation &amp; FFmpeg preprocessing (16 kHz mono)</li>
              <li>Speech-aware VAD segmentation with overlap</li>
              <li>IndicConformer ASR (chunked, de-duplicated)</li>
              <li>Input translation to English when required</li>
              <li>Param-1 hierarchical note generation</li>
              <li>Param-1 quiz generation + strict validation</li>
              <li>Optional output translation (cached per language)</li>
              <li>Persist → transcript, notes, quiz ready to explore</li>
            </ol>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Model mode</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-zinc-700">
            <p>
              Check <strong>Settings</strong> to see whether each provider runs
              in <Badge className="mx-1 border-amber-200 bg-amber-50 text-amber-700">mock</Badge>{" "}
              or <Badge className="mx-1 border-emerald-200 bg-emerald-50 text-emerald-700">real</Badge>{" "}
              mode. Mock providers produce clearly-flagged demo output so the
              full workflow can be demonstrated without multi-gigabyte
              checkpoints; real inference is enabled entirely through
              environment variables.
            </p>
          </CardContent>
        </Card>

        <p className="flex items-center justify-center gap-2 pt-2 text-xs text-zinc-400">
          <Github className="h-3.5 w-3.5" /> Built as a CS3235 mini-project
          demonstration
        </p>
      </div>
    </div>
  );
}
