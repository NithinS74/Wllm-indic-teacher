import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryOptions,
} from "@tanstack/react-query";
import { api, toApiError } from "@/services/api";
import type {
  AppSettings,
  Job,
  LectureDetail,
  LectureSummary,
  NotesResponse,
  Quiz,
  QuizAttempt,
  Transcript,
} from "@/types";

export function useSettings() {
  return useQuery({
    queryKey: ["settings"],
    queryFn: async () => (await api.get<AppSettings>("/settings")).data,
    staleTime: 60_000,
  });
}

export function useLectures() {
  return useQuery({
    queryKey: ["lectures"],
    queryFn: async () => (await api.get<LectureSummary[]>("/lectures")).data,
    refetchInterval: 5000,
  });
}

export function useLecture(id: string | undefined) {
  return useQuery({
    queryKey: ["lecture", id],
    queryFn: async () => (await api.get<LectureDetail>(`/lectures/${id}`)).data,
    enabled: !!id,
    refetchInterval: 4000,
  });
}

export function useJob(
  jobId: string | undefined,
  opts?: Partial<UseQueryOptions<Job>>,
) {
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: async () => (await api.get<Job>(`/jobs/${jobId}`)).data,
    enabled: !!jobId,
    refetchInterval: (query) => {
      const status = query.state.data?.status;
      if (status === "COMPLETED" || status === "FAILED") return false;
      return 1500;
    },
    ...opts,
  });
}

export function useTranscript(lectureId: string | undefined, language?: string) {
  return useQuery({
    queryKey: ["transcript", lectureId, language ?? "orig"],
    queryFn: async () =>
      (
        await api.get<Transcript>(`/lectures/${lectureId}/transcript`, {
          params: language ? { language } : {},
        })
      ).data,
    enabled: !!lectureId,
    retry: false,
  });
}

export function useNotes(lectureId: string | undefined, language?: string) {
  return useQuery({
    queryKey: ["notes", lectureId, language ?? "en"],
    queryFn: async () =>
      (
        await api.get<NotesResponse>(`/lectures/${lectureId}/notes`, {
          params: language ? { language } : {},
        })
      ).data,
    enabled: !!lectureId,
    retry: false,
  });
}

export function useQuiz(lectureId: string | undefined, language?: string) {
  return useQuery({
    queryKey: ["quiz", lectureId, language ?? "en"],
    queryFn: async () =>
      (
        await api.get<Quiz>(`/lectures/${lectureId}/quiz`, {
          params: language ? { language } : {},
        })
      ).data,
    enabled: !!lectureId,
    retry: false,
  });
}

export function useTranslate(lectureId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload: {
      content_types: ("transcript" | "notes" | "quiz")[];
      language: string;
    }) =>
      (
        await api.post<{ job_id: string }>(
          `/lectures/${lectureId}/translate`,
          payload,
        )
      ).data,
    onSuccess: (_data, vars) => {
      // invalidate possible cached results so they refetch after translation
      void qc.invalidateQueries({ queryKey: ["notes", lectureId] });
      void qc.invalidateQueries({ queryKey: ["quiz", lectureId] });
      void qc.invalidateQueries({ queryKey: ["transcript", lectureId] });
      void qc.invalidateQueries({ queryKey: ["lecture", lectureId] });
      void vars;
    },
  });
}

export function useSubmitAttempt(lectureId: string | undefined) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (answers: Record<string, string>) =>
      (
        await api.post<QuizAttempt>(`/lectures/${lectureId}/quiz/attempt`, {
          answers,
        })
      ).data,
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lecture", lectureId] });
    },
  });
}

export function useDeleteLecture() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (id: string) => {
      try {
        await api.delete(`/lectures/${id}`);
      } catch (err) {
        throw toApiError(err);
      }
    },
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["lectures"] });
    },
  });
}
