import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Sparkles, Upload } from "lucide-react";
import { uploadLecture, toApiError } from "@/services/api";
import { useSettings } from "@/hooks/useApi";
import { FileDropzone } from "@/components/upload/FileDropzone";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";
import { LANG_OPTIONS } from "@/lib/languages";

const NONE = "__none__";

export function NewLecturePage() {
  const navigate = useNavigate();
  const { data: settings } = useSettings();
  const { error: toastError } = useToast();

  const [title, setTitle] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [source, setSource] = useState("en");
  const [target, setTarget] = useState(NONE);
  const [genNotes, setGenNotes] = useState(true);
  const [genQuiz, setGenQuiz] = useState(true);
  const [translate, setTranslate] = useState(false);
  const [pct, setPct] = useState<number | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const accepted = settings?.limits.allowed_extensions ?? [
    ".wav", ".mp3", ".m4a", ".flac",
  ];
  const maxBytes = settings?.limits.max_upload_bytes ?? 100 * 1024 * 1024;

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);

    if (!title.trim()) {
      setFormError("Please enter a lecture title.");
      return;
    }
    if (!file) {
      setFormError("Please choose an audio file.");
      return;
    }
    if (translate && target === NONE) {
      setFormError("Choose a target language, or turn off translation.");
      return;
    }
    if (translate && target === source) {
      setFormError("Source and target languages must differ.");
      return;
    }

    const form = new FormData();
    form.append("title", title.trim());
    form.append("source_language", source);
    form.append("target_language", target === NONE ? "" : target);
    form.append("generate_notes", String(genNotes));
    form.append("generate_quiz", String(genQuiz));
    form.append("translate_content", String(translate));
    form.append("audio", file);

    setSubmitting(true);
    setPct(0);
    try {
      const lecture = await uploadLecture(form, setPct);
      navigate(
        lecture.job_id ? `/processing/${lecture.job_id}` : `/lectures/${lecture.id}`,
        { state: { lectureId: lecture.id } },
      );
    } catch (err) {
      const apiErr = toApiError(err);
      setFormError(apiErr.message);
      toastError("Upload failed", apiErr.message);
      setPct(null);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8 lg:px-8">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
          New Lecture
        </h1>
        <p className="mt-1 text-sm text-zinc-500">
          Upload a recording — LectureLens will transcribe it, generate notes
          and a five-question quiz.
        </p>
      </div>

      <form onSubmit={submit} className="space-y-6">
        <Card>
          <CardHeader>
            <CardTitle>Recording details</CardTitle>
            <CardDescription>
              WAV, MP3, M4A, FLAC up to{" "}
              {settings
                ? `${Math.round(settings.limits.max_upload_bytes / (1024 * 1024))} MB`
                : "100 MB"}
              .
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="title">Lecture title</Label>
              <Input
                id="title"
                placeholder="e.g. Introduction to Operating Systems"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                maxLength={300}
                required
              />
            </div>

            <div className="space-y-2">
              <Label>Audio file</Label>
              <FileDropzone
                file={file}
                onChange={(f) => {
                  setFile(f);
                  setFormError(null);
                }}
                accepted={accepted}
                maxBytes={maxBytes}
                uploadPct={pct}
              />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Languages</CardTitle>
          </CardHeader>
          <CardContent className="grid gap-5 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="source-lang">Source language</Label>
              <Select value={source} onValueChange={setSource}>
                <SelectTrigger id="source-lang">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {LANG_OPTIONS.map((l) => (
                    <SelectItem key={l.key} value={l.key}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                Language spoken in the recording.
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="target-lang">Notes / output language</Label>
              <Select
                value={target}
                onValueChange={setTarget}
                disabled={!translate}
              >
                <SelectTrigger id="target-lang">
                  <SelectValue
                    placeholder={translate ? "Select language" : "English (canonical)"}
                  />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={NONE}>
                    {translate ? "Select…" : "English (canonical)"}
                  </SelectItem>
                  {LANG_OPTIONS.filter((l) => l.key !== source).map((l) => (
                    <SelectItem key={l.key} value={l.key}>
                      {l.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-zinc-500">
                Generated content is produced in English, then translated.
              </p>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Generation</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <ToggleRow
              label="Generate notes"
              description="Structured notes with sections, definitions and takeaways."
              checked={genNotes}
              onChange={setGenNotes}
            />
            <ToggleRow
              label="Generate quiz"
              description="Exactly five multiple-choice questions with explanations."
              checked={genQuiz}
              onChange={setGenQuiz}
            />
            <ToggleRow
              label="Translate content"
              description={`Translate transcript, notes and quiz into the target language (cached — no re-processing).`}
              checked={translate}
              onChange={setTranslate}
            />
            {!translate && (
              <p className="text-xs text-zinc-500">
                Tip: you can translate later from the lecture workspace without
                re-running the pipeline.
              </p>
            )}
          </CardContent>
        </Card>

        {formError && (
          <div
            role="alert"
            className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700"
          >
            {formError}
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <Badge className="border-zinc-200 bg-zinc-50 text-zinc-500">
            <Sparkles className="mr-1 h-3 w-3" />
            {settings
              ? settings.providers.map((p) => p.provider).join(" · ")
              : "loading providers…"}
          </Badge>
          <Button type="submit" disabled={submitting} size="lg">
            <Upload className="h-4 w-4" />
            {submitting ? "Uploading…" : "Start processing"}
          </Button>
        </div>
      </form>
    </div>
  );
}

function ToggleRow({
  label,
  description,
  checked,
  onChange,
}: {
  label: string;
  description: string;
  checked: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <div className="flex items-start justify-between gap-4 rounded-md border border-zinc-200 p-3.5">
      <div>
        <p className="text-sm font-medium text-zinc-800">{label}</p>
        <p className="mt-0.5 text-xs text-zinc-500">{description}</p>
      </div>
      <Switch checked={checked} onCheckedChange={onChange} aria-label={label} />
    </div>
  );
}
