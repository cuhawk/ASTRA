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

export interface VaultStatus {
  provider: string;
  present: boolean;
  updated_at: number | null;
}

export interface ChatMessage {
  id: number;
  run_id: string;
  role: "user" | "assistant";
  content: string;
  llm_call_id: number | null;
  created_at: number;
}

export interface ActivityEvent {
  id: number;
  user_id: number;
  action: string;
  entity: string;
  entity_id: string | null;
  payload: Record<string, unknown> | null;
  at: number;
}

export interface RecordAction {
  type: "click" | "wait" | "fill" | "navigate" | "press";
  selector?: string;
  ms?: number;
  value?: string;
  url?: string;
  key?: string;
}
