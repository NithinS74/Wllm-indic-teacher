// API types mirroring the FastAPI Pydantic schemas

export type LanguageKey = "en" | "hi" | "kn" | "ta" | "te" | "ml";

export interface LanguageInfo {
  key: LanguageKey;
  label: string;
  script: string;
  indictrans: string;
}

export type LectureStatus = "QUEUED" | "PROCESSING" | "COMPLETED" | "FAILED";

export type JobStage =
  | "QUEUED"
  | "PREPROCESSING"
  | "TRANSCRIBING"
  | "TRANSLATING_INPUT"
  | "GENERATING_NOTES"
  | "GENERATING_QUIZ"
  | "TRANSLATING_OUTPUT"
  | "VALIDATING"
  | "COMPLETED"
  | "FAILED";

export interface LectureSummary {
  id: string;
  title: string;
  source_language: LanguageKey;
  target_language: LanguageKey | null;
  duration: number | null;
  status: LectureStatus;
  generate_notes: boolean;
  generate_quiz: boolean;
  translate_content: boolean;
  providers: Record<string, string> | null;
  created_at: string;
  updated_at: string;
  job_id: string | null;
  job_status: JobStage | null;
  current_stage: JobStage | null;
  progress: number | null;
  error_message: string | null;
  audio_original_name: string | null;
}

export interface LectureDetail extends LectureSummary {
  has_transcript: boolean;
  has_notes: boolean;
  has_quiz: boolean;
  available_note_languages: string[];
  available_translation_languages: string[];
}

export interface Job {
  id: string;
  lecture_id: string;
  kind: "PROCESSING" | "TRANSLATION";
  status: JobStage;
  current_stage: JobStage;
  stages: JobStage[] | null;
  progress: number;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}

export interface TranscriptSegment {
  segment_index: number;
  start_time: number;
  end_time: number;
  text: string;
  language: string;
}

export interface Transcript {
  lecture_id: string;
  language: LanguageKey;
  language_label: string;
  is_mock: boolean;
  duration: number | null;
  segments: TranscriptSegment[];
  audio_url: string | null;
}

export interface NoteSection {
  id: string;
  heading: string;
  content: string[];
  source_segments: number[];
}

export interface KeyTerm {
  term: string;
  definition: string;
  source_segments: number[];
}

export interface NotesContent {
  title: string;
  overview: string;
  sections: NoteSection[];
  key_terms: KeyTerm[];
  key_takeaways: string[];
  examples: string[];
  important_points: string[];
  uncertain: string[];
}

export interface NotesResponse {
  lecture_id: string;
  language: LanguageKey;
  is_mock: boolean;
  content: NotesContent;
  note?: string;
}

export interface QuizOption {
  id: "A" | "B" | "C" | "D";
  text: string;
}

export interface QuizQuestion {
  id: string;
  question: string;
  options: QuizOption[];
  correct_option: "A" | "B" | "C" | "D";
  explanation: string;
  difficulty: string;
  source_segments: number[];
}

export interface Quiz {
  lecture_id: string;
  language: LanguageKey;
  is_mock: boolean;
  questions: QuizQuestion[];
}

export interface QuizAttempt {
  id: string;
  lecture_id: string;
  answers: Record<string, string>;
  score: number;
  total_questions: number;
  created_at: string;
}

export interface ProviderStatus {
  name: string;
  provider: string;
  mode: "mock" | "real";
  loaded: boolean;
  detail: string;
}

export interface AppSettings {
  app_name: string;
  providers: ProviderStatus[];
  languages: LanguageInfo[];
  limits: {
    max_upload_bytes: number;
    max_audio_duration_seconds: number;
    min_audio_duration_seconds: number;
    allowed_extensions: string[];
    chunk_duration_seconds: number;
  };
}

export interface ApiErrorBody {
  error: { code: string; message: string; detail?: unknown };
}
