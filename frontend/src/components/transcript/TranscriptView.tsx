import { useMemo, useRef, useState } from "react";
import { Copy, Search, Volume2 } from "lucide-react";
import type { Transcript } from "@/types";
import { formatTimestamp } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { useToast } from "@/components/ui/toast";

interface Props {
  transcript: Transcript;
}

export function TranscriptView({ transcript }: Props) {
  const [query, setQuery] = useState("");
  const [activeIdx, setActiveIdx] = useState<number | null>(null);
  const audioRef = useRef<HTMLAudioElement>(null);
  const { success, error } = useToast();

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return transcript.segments.map((s) => ({ seg: s, match: false }));
    return transcript.segments
      .map((s) => ({ seg: s, match: s.text.toLowerCase().includes(q) }))
      .filter((x) => x.match);
  }, [query, transcript.segments]);

  const seek = (time: number) => {
    const el = audioRef.current;
    if (!el) return;
    el.currentTime = time;
    void el.play().catch(() => undefined);
  };

  const copyAll = async () => {
    try {
      await navigator.clipboard.writeText(
        transcript.segments
          .map((s) => `[${formatTimestamp(s.start_time)}] ${s.text}`)
          .join("\n"),
      );
      success("Transcript copied to clipboard");
    } catch {
      error("Could not access the clipboard");
    }
  };

  return (
    <div className="space-y-4">
      {/* Audio player */}
      <div className="rounded-lg border border-zinc-200 bg-white p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <div className="flex items-center gap-2 text-sm text-zinc-600">
            <Volume2 className="h-4 w-4" />
            <span>Lecture audio</span>
            <Badge className="border-zinc-200 bg-zinc-50 text-zinc-600">
              {transcript.language_label} ({transcript.language})
            </Badge>
            {transcript.is_mock && (
              <Badge className="border-amber-200 bg-amber-50 text-amber-700">
                mock transcript
              </Badge>
            )}
          </div>
          <div className="flex gap-2">
            <Button variant="secondary" size="sm" onClick={copyAll}>
              <Copy className="h-3.5 w-3.5" /> Copy transcript
            </Button>
          </div>
        </div>
        <audio
          ref={audioRef}
          controls
          src={transcript.audio_url ?? undefined}
          className="w-full"
        >
          <track kind="captions" />
        </audio>
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-zinc-400" />
        <Input
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Search transcript…"
          className="pl-9"
          aria-label="Search transcript"
        />
      </div>

      {filtered.length === 0 && (
        <p className="rounded-lg border border-dashed border-zinc-300 p-6 text-center text-sm text-zinc-500">
          No segments match “{query}”.
        </p>
      )}

      <ol className="space-y-1.5">
        {filtered.map(({ seg }) => (
          <li
            key={seg.segment_index}
            className={
              "group flex gap-3 rounded-md border border-transparent p-3 transition-colors hover:border-zinc-200 hover:bg-white " +
              (activeIdx === seg.segment_index ? "border-zinc-200 bg-white" : "")
            }
          >
            <button
              onClick={() => {
                setActiveIdx(seg.segment_index);
                seek(seg.start_time);
              }}
              className="h-fit shrink-0 rounded border border-zinc-200 bg-zinc-50 px-1.5 py-0.5 font-mono text-xs tabular-nums text-zinc-600 hover:border-primary hover:text-primary"
              title="Click to play from here"
            >
              {formatTimestamp(seg.start_time)}
            </button>
            <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-zinc-700">
              {seg.text}
            </p>
          </li>
        ))}
      </ol>
    </div>
  );
}
