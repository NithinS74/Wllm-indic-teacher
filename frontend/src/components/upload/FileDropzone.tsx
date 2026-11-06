import { useCallback, useRef, useState } from "react";
import { FileAudio, UploadCloud, X } from "lucide-react";
import { cn, formatBytes } from "@/lib/utils";

interface Props {
  file: File | null;
  onChange: (file: File | null) => void;
  accepted: string[];
  maxBytes: number;
  uploadPct?: number | null;
  error?: string | null;
}

export function FileDropzone({
  file,
  onChange,
  accepted,
  maxBytes,
  uploadPct,
  error,
}: Props) {
  const [dragging, setDragging] = useState(false);
  const [localError, setLocalError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const validate = useCallback(
    (f: File) => {
      const ext = "." + f.name.split(".").pop()?.toLowerCase();
      if (!accepted.includes(ext)) {
        return `File type ${ext} is not allowed. Accepted: ${accepted.join(", ")}`;
      }
      if (f.size > maxBytes) {
        return `File is ${formatBytes(f.size)} — limit is ${formatBytes(maxBytes)}.`;
      }
      return null;
    },
    [accepted, maxBytes],
  );

  const handleFiles = useCallback(
    (files: FileList | null) => {
      const f = files?.[0];
      if (!f) return;
      const err = validate(f);
      setLocalError(err);
      onChange(err ? null : f);
    },
    [validate, onChange],
  );

  const shownError = error ?? localError;

  return (
    <div>
      <div
        role="button"
        tabIndex={0}
        onClick={() => inputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
        }}
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFiles(e.dataTransfer.files);
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-10 text-center transition-colors",
          dragging
            ? "border-primary bg-primary/5"
            : "border-zinc-300 bg-zinc-50/60 hover:border-zinc-400 hover:bg-zinc-50",
          shownError && "border-red-300 bg-red-50/40",
        )}
      >
        <input
          ref={inputRef}
          type="file"
          className="hidden"
          accept={accepted.join(",")}
          onChange={(e) => handleFiles(e.target.files)}
        />
        {!file ? (
          <>
            <UploadCloud className="mb-3 h-9 w-9 text-zinc-400" />
            <p className="text-sm font-medium text-zinc-700">
              Drag & drop your lecture recording, or click to browse
            </p>
            <p className="mt-1.5 text-xs text-zinc-500">
              {accepted.join(" · ").toUpperCase()} — up to{" "}
              {formatBytes(maxBytes)}
            </p>
          </>
        ) : (
          <div className="flex w-full max-w-md items-center gap-3 rounded-md border border-zinc-200 bg-white p-3 text-left shadow-sm">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
              <FileAudio className="h-5 w-5" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-medium text-zinc-800">
                {file.name}
              </p>
              <p className="text-xs text-zinc-500">{formatBytes(file.size)}</p>
              {uploadPct != null && uploadPct < 100 && (
                <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-zinc-200">
                  <div
                    className="h-full rounded-full bg-primary transition-all"
                    style={{ width: `${uploadPct}%` }}
                  />
                </div>
              )}
              {uploadPct === 100 && (
                <p className="mt-1 text-xs text-emerald-600">Uploaded</p>
              )}
            </div>
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onChange(null);
                setLocalError(null);
                if (inputRef.current) inputRef.current.value = "";
              }}
              className="rounded p-1.5 text-zinc-400 hover:bg-zinc-100 hover:text-zinc-600"
              aria-label="Remove file"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>
      {shownError && (
        <p className="mt-2 text-sm text-red-600" role="alert">
          {shownError}
        </p>
      )}
    </div>
  );
}
