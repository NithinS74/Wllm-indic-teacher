import axios, { AxiosError } from "axios";
import type { ApiErrorBody } from "@/types";

export const api = axios.create({
  baseURL: "/api/v1",
  timeout: 30000,
});

export class ApiError extends Error {
  code: string;
  status: number;
  detail?: unknown;

  constructor(message: string, status: number, code: string, detail?: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

export function toApiError(err: unknown): ApiError {
  if (err instanceof ApiError) return err;
  const axiosErr = err as AxiosError<ApiErrorBody>;
  if (axiosErr?.response?.data?.error) {
    const body = axiosErr.response.data.error;
    return new ApiError(
      body.message || "Request failed",
      axiosErr.response.status,
      body.code,
      body.detail,
    );
  }
  if (axiosErr?.message) {
    return new ApiError(axiosErr.message, 0, "network_error");
  }
  return new ApiError("Unexpected error", 0, "unknown");
}

export async function uploadLecture(form: FormData, onProgress?: (pct: number) => void) {
  const res = await api.post("/lectures", form, {
    timeout: 120000,
    headers: { "Content-Type": "multipart/form-data" },
    onUploadProgress: (evt) => {
      if (evt.total) onProgress?.(Math.round((evt.loaded / evt.total) * 100));
    },
  });
  return res.data;
}
