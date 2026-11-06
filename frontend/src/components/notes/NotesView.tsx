import { BookOpen, Download, FileText, Printer, Sparkles } from "lucide-react";
import type { NotesResponse } from "@/types";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import type { LanguageInfo } from "@/types";
import { api } from "@/services/api";
import { useToast } from "@/components/ui/toast";

interface Props {
  notes: NotesResponse;
  languages: LanguageInfo[];
  language: string;
  onLanguageChange: (lang: string) => void;
  availableLanguages: string[];
  lectureTitle: string;
}

export function NotesView({
  notes,
  languages,
  language,
  onLanguageChange,
  availableLanguages,
  lectureTitle,
}: Props) {
  const c = notes.content;
  const { success, error } = useToast();

  const download = async (format: "notes" | "markdown") => {
    try {
      const res = await api.get(`/lectures/${notes.lecture_id}/export`, {
        params: { format: format === "notes" ? "notes" : "markdown", language },
        responseType: "text",
      });
      const blob = new Blob([res.data as string], {
        type: "text/markdown;charset=utf-8",
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `${lectureTitle.replace(/[^\w\- ]+/g, "_").slice(0, 60) || "notes"}.md`;
      a.click();
      URL.revokeObjectURL(url);
      success("Notes downloaded");
    } catch {
      error("Export failed");
    }
  };

  const print = () => {
    window.print();
  };

  return (
    <div className="space-y-5">
      {/* Toolbar */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <label className="text-sm font-medium text-zinc-600" htmlFor="notes-lang">
            Language
          </label>
          <Select value={language} onValueChange={onLanguageChange}>
            <SelectTrigger id="notes-lang" className="h-9 w-44">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {languages.map((l) => (
                <SelectItem key={l.key} value={l.key}>
                  {l.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          {language !== "en" && !availableLanguages.includes(language) && (
            <Badge className="border-zinc-200 bg-zinc-50 text-zinc-500">
              not translated yet
            </Badge>
          )}
          {notes.is_mock && (
            <Badge className="border-amber-200 bg-amber-50 text-amber-700">
              mock notes
            </Badge>
          )}
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={() => download("notes")}>
            <Download className="h-3.5 w-3.5" /> Markdown
          </Button>
          <Button variant="secondary" size="sm" onClick={() => download("markdown")}>
            <FileText className="h-3.5 w-3.5" /> Full pack
          </Button>
          <Button variant="secondary" size="sm" onClick={print}>
            <Printer className="h-3.5 w-3.5" /> Print / PDF
          </Button>
        </div>
      </div>

      {/* Overview */}
      <Card>
        <CardHeader className="pb-3">
          <CardTitle className="flex items-center gap-2 text-lg">
            <BookOpen className="h-5 w-5 text-primary" />
            {c.title}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-zinc-700">{c.overview}</p>
        </CardContent>
      </Card>

      {/* Sections */}
      <div className="space-y-4 print:space-y-3">
        {c.sections.map((s) => (
          <Card key={s.id} className="print:shadow-none print:border-0">
            <CardHeader className="pb-2">
              <CardTitle className="text-base">{s.heading}</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <ul className="list-disc space-y-2 pl-5 text-sm leading-relaxed text-zinc-700">
                {s.content.map((line, i) => (
                  <li key={i}>{line}</li>
                ))}
              </ul>
              {s.source_segments.length > 0 && (
                <p className="text-xs text-zinc-400">
                  Source segments: {s.source_segments.join(", ")}
                </p>
              )}
            </CardContent>
          </Card>
        ))}
      </div>

      {/* Key terms */}
      {c.key_terms.length > 0 && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-base">Key concepts & definitions</CardTitle>
          </CardHeader>
          <CardContent>
            <dl className="space-y-3">
              {c.key_terms.map((t, i) => (
                <div key={i} className="border-l-2 border-primary/40 pl-3">
                  <dt className="text-sm font-semibold text-zinc-800">{t.term}</dt>
                  <dd className="text-sm text-zinc-600">{t.definition}</dd>
                </div>
              ))}
            </dl>
          </CardContent>
        </Card>
      )}

      {/* Examples + important points */}
      {(c.examples.length > 0 || c.important_points.length > 0) && (
        <div className="grid gap-4 md:grid-cols-2">
          {c.examples.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Examples from the lecture</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-zinc-700">
                  {c.examples.map((e, i) => (
                    <li key={i}>{e}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
          {c.important_points.length > 0 && (
            <Card>
              <CardHeader className="pb-2">
                <CardTitle className="text-base">Important points</CardTitle>
              </CardHeader>
              <CardContent>
                <ul className="list-disc space-y-1.5 pl-5 text-sm text-zinc-700">
                  {c.important_points.map((p, i) => (
                    <li key={i}>{p}</li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </div>
      )}

      {/* Takeaways */}
      {c.key_takeaways.length > 0 && (
        <Card className="border-primary/20 bg-primary/[0.03]">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base">
              <Sparkles className="h-4 w-4 text-primary" />
              Key takeaways
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-zinc-700">
              {c.key_takeaways.map((k, i) => (
                <li key={i}>{k}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {c.uncertain.length > 0 && (
        <Card className="border-amber-200 bg-amber-50/50">
          <CardHeader className="pb-2">
            <CardTitle className="text-base text-amber-800">
              Uncertain — needs review
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="list-disc space-y-1.5 pl-5 text-sm text-amber-900/80">
              {c.uncertain.map((u, i) => (
                <li key={i}>{u}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
