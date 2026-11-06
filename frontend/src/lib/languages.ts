import type { LanguageKey } from "@/types";

export const LANG_LABEL: Record<string, string> = {
  en: "English",
  hi: "Hindi",
  kn: "Kannada",
  ta: "Tamil",
  te: "Telugu",
  ml: "Malayalam",
};

export const LANG_OPTIONS: { key: LanguageKey; label: string }[] = (
  Object.entries(LANG_LABEL) as [LanguageKey, string][]
).map(([key, label]) => ({ key, label }));
