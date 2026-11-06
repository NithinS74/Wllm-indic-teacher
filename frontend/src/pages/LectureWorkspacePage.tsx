import { useEffect, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import {
  ArrowLeft,
  Download,
  FileText,
  Languages,
  Loader2,
  MessageSquareQuote,
  ScrollText,
  StickyNote,
} from "lucide-react";
import {
  useLecture,
  useNotes,
  useQuiz,
  useTranslate,
  useTranscript,
  useSettings,
} from "@/hooks/useApi";
import { StatusBadge } from "@/components/StatusBadge";
import { TranscriptView } from "@/components/transcript/TranscriptView";
import { NotesView } from "@/components/notes/NotesView";
import { QuizView } from "@/components/quiz/QuizView";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useToast } from "@/components/ui/toast";
import { formatDate, formatDuration } from "@/lib/utils";
import { api } from "@/services/api";
import { LANG_LABEL } from "@/lib/languages";

const NONE = "__none__";

export function LectureWorkspacePage() {
  const { id } = useParams<{ id: string }>();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "transcript";
  const { data: lecture, isLoading, error, refetch } = useLecture(id);
  const { data: settings } = useSettings();

  const [displayLang, setDisplayLang] = useState<string>(NONE);
  const { success, error: toastError, info } = useToast();
  const translate = useTranslate(id);

  const activeLang = displayLang === NONE ? undefined : displayLang;
  const transcriptQ = useTranscript(id, activeLang);
  const notesQ = useNotes(id, activeLang);
  const quizQ = useQuiz(id, activeLang);

  useEffect(() => {
    if (lecture && displayLang === NONE && lecture.target_language) {
      // default to target language when translations were pre-generated
      if (lecture.available_translation_languages.includes(lecture.target_language)) {
        setDisplayLang(lecture.target_language);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lecture]);

  if (isLoading) {
    return (
      <div className="mx-auto max-w-5xl space-y-4 px-4 py-8 lg:px-8">
        <Skeleton className="h-8 w-1/2" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-64 w-full" />
      </div>
    );
  }

  if (error || !lecture) {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <p className="text-sm font-medium text-red-600">
          Could not load this lecture.
        </p>
        <Button variant="secondary" className="mt-4" asChild>
          <Link to="/lectures">Back to My Lectures</Link>
        </Button>
      </div>
    );
  }

  if (lecture.status === "FAILED") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <h1 className="text-lg font-semibold text-zinc-900">{lecture.title}</h1>
        <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-4 text-left">
          <p className="text-sm font-medium text-red-800">Processing failed</p>
          <p className="mt-1 break-words text-sm text-red-700">
            {lecture.error_message ?? "Unknown error."}
          </p>
        </div>
        <div className="mt-4 flex justify-center gap-2">
          <Button variant="secondary" asChild>
            <Link to="/lectures">Back</Link>
          </Button>
          <Button asChild>
            <Link to="/new">Try another recording</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (lecture.status !== "COMPLETED") {
    return (
      <div className="mx-auto max-w-2xl px-4 py-16 text-center">
        <Loader2 className="mx-auto h-6 w-6 animate-spin text-primary" />
        <p className="mt-3 text-sm text-zinc-600">This lecture is still processing…</p>
        {lecture.job_id && (
          <Button className="mt-4" asChild>
            <Link to={`/processing/${lecture.job_id}`}>View progress</Link>
          </Button>
        )}
      </div>
    );
  }

  const doTranslate = async (lang: string) => {
    if (lang === NONE) {
      setDisplayLang(NONE);
      return;
    }
    setDisplayLang(lang);
    const needed = ["transcript", "notes", "quiz"].filter((ct) => {
      if (ct === "notes") return lecture.has_notes;
      if (ct === "quiz") return lecture.has_quiz;
      return lecture.has_transcript;
    });
    try {
      await translate.mutateAsync({
        content_types: needed as ("transcript" | "notes" | "quiz")[],
        language: lang,
      });
      info(
        `Translating to ${LANG_LABEL[lang] ?? lang}…`,
        "Content will update automatically — cached translations are reused.",
      );
    } catch (err) {
      toastError("Translation request failed", (err as Error).message);
    }
  };

  const exportFile = async (format: string) => {
    try {
      const res = await api.get(`/lectures/${lecture.id}/export`, {
        params: {
          format,
          ...(activeLang ? { language: activeLang } : {}),
        },
        responseType: "text",
      });
      const ext = format === "transcript" ? "txt" : "md";
      const blob = new Blob([res.data as string], {
        type: format === "transcript" ? "text/plain" : "text/markdown",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${lecture.title.replace(/[^\w\- ]+/g, "_").slice(0, 60) || "lecture"}.${ext}`;
      a.click();
      URL.revokeObjectURL(url);
      success("Download started");
    } catch {
      toastError("Export failed");
    }
  };

  const translatedLangs = new Set(lecture.available_translation_languages);

  return (
    <div className="mx-auto max-w-5xl px-4 py-6 lg:px-8">
      {/* Header */}
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <Link
            to="/lectures"
            className="mb-2 inline-flex items-center gap-1 text-sm text-zinc-500 hover:text-zinc-800"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> My Lectures
          </Link>
          <h1 className="truncate text-xl font-semibold tracking-tight text-zinc-900">
            {lecture.title}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-zinc-500">
            <StatusBadge status={lecture.status} />
            <span>
              Source: {LANG_LABEL[lecture.source_language] ?? lecture.source_language}
            </span>
            {lecture.duration != null && (
              <span>· {formatDuration(lecture.duration)}</span>
            )}
            <span>· {formatDate(lecture.created_at)}</span>
            {Object.values(lecture.providers ?? {}).includes("mock") && (
              <Badge className="border-amber-200 bg-amber-50 text-amber-700">
                demo mode outputs
              </Badge>
            )}
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          {/* Language switcher */}
          <div className="flex items-center gap-1.5 rounded-md border border-zinc-200 bg-white px-2 py-1.5">
            <Languages className="h-4 w-4 text-zinc-400" />
            <Select value={displayLang} onValueChange={doTranslate}>
              <SelectTrigger className="h-7 w-40 border-0 bg-transparent text-sm shadow-none focus:ring-0">
                <SelectValue placeholder="Display language" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={NONE}>
                  {LANG_LABEL[lecture.source_language]} (original)
                </SelectItem>
                <SelectItem value="en">English (generated)</SelectItem>
                {(settings?.languages ?? [])
                  .map((l) => l.key)
                  .filter((k) => k !== "en" && k !== lecture.source_language)
                  .map((k) => (
                    <SelectItem key={k} value={k}>
                      {LANG_LABEL[k] ?? k}
                      {translatedLangs.has(k) ? " ✓" : ""}
                    </SelectItem>
                  ))}
              </SelectContent>
            </Select>
          </div>

          <Button variant="secondary" size="sm" onClick={() => exportFile("markdown")}>
            <Download className="h-3.5 w-3.5" /> Export
          </Button>
        </div>
      </div>

      {/* Tabs */}
      <Tabs
        value={tab}
        onValueChange={(v) => {
          const next = new URLSearchParams(params);
          next.set("tab", v);
          setParams(next, { replace: true });
        }}
      >
        <TabsList>
          <TabsTrigger value="transcript">
            <ScrollText className="h-4 w-4" /> Transcript
          </TabsTrigger>
          <TabsTrigger value="notes" disabled={!lecture.has_notes}>
            <StickyNote className="h-4 w-4" /> Notes
          </TabsTrigger>
          <TabsTrigger value="quiz" disabled={!lecture.has_quiz}>
            <MessageSquareQuote className="h-4 w-4" /> Quiz
          </TabsTrigger>
        </TabsList>

        <TabsContent value="transcript">
          {transcriptQ.isLoading && <Skeleton className="h-64 w-full" />}
          {transcriptQ.isError && (
            <EmptyPanel
              message={
                (transcriptQ.error as Error)?.message?.includes("404")
                  ? "Transcript is not ready yet."
                  : "Could not load the transcript."
              }
            />
          )}
          {transcriptQ.data && <TranscriptView transcript={transcriptQ.data} />}
        </TabsContent>

        <TabsContent value="notes">
          {notesQ.isLoading && <Skeleton className="h-64 w-full" />}
          {notesQ.isError && (
            <EmptyPanel message="Notes are not available for this lecture." />
          )}
          {notesQ.data && (
            <NotesView
              notes={notesQ.data}
              languages={settings?.languages ?? []}
              language={notesQ.data.language}
              onLanguageChange={doTranslate}
              availableLanguages={lecture.available_note_languages}
              lectureTitle={lecture.title}
            />
          )}
        </TabsContent>

        <TabsContent value="quiz">
          {quizQ.isLoading && <Skeleton className="h-64 w-full" />}
          {quizQ.isError && (
            <EmptyPanel message="Quiz is not available for this lecture." />
          )}
          {quizQ.data && <QuizView quiz={quizQ.data} />}
        </TabsContent>
      </Tabs>

      {/* Export footer */}
      <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-zinc-200 pt-5">
        <p className="text-xs text-zinc-500">
          Export includes lecture title, source language and generated content.
        </p>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => exportFile("notes")}>
            <FileText className="h-3.5 w-3.5" /> Notes (.md)
          </Button>
          <Button variant="secondary" size="sm" onClick={() => exportFile("transcript")}>
            <ScrollText className="h-3.5 w-3.5" /> Transcript (.txt)
          </Button>
          <Button variant="secondary" size="sm" onClick={() => exportFile("markdown")}>
            <Download className="h-3.5 w-3.5" /> Full pack (.md)
          </Button>
        </div>
      </div>
    </div>
  );
}

function EmptyPanel({ message }: { message: string }) {
  return (
    <div className="rounded-lg border border-dashed border-zinc-300 p-8 text-center text-sm text-zinc-500">
      {message}
    </div>
  );
}
