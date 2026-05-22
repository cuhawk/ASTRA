export interface User {
  id: number;
  github_id: number;
  github_login: string;
  email: string | null;
}

export type RunStatus =
  | "pending"
  | "acquiring"
  | "analyzing"
  | "done"
  | "failed";

export interface Run {
  id: string;
  user_id: number;
  url: string | null;
  status: RunStatus;
  error: string | null;
  created_at: number;
  started_at: number | null;
  finished_at: number | null;
  files: number;
  functions: number;
  edges: number;
}

export type FeatureStatus = "pending" | "recording" | "done" | "failed";

export interface Feature {
  id: string;
  run_id: string;
  name: string;
  created_at: number;
  last_run_at: number | null;
  last_status: FeatureStatus | null;
  error: string | null;
  matched_functions: number;
}

export interface CompletionOut {
  text: string;
  provider: string;
  model: string;
  cost_usd: number;
  duration_ms: number;
}

export interface RecordAction {
  type: "click" | "wait" | "fill" | "navigate" | "press";
  selector?: string;
  ms?: number;
  value?: string;
  url?: string;
  key?: string;
}
