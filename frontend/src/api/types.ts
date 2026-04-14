export type SessionStatus = 'pending' | 'running' | 'completed' | 'failed';

export interface SessionInfo {
  session_id: string;
  status: SessionStatus;
  created_at: string;
  last_accessed: string;
  workspace_dir?: string | null;
  duration_seconds?: number | null;
  error?: string | null;
}

export interface SessionDetail extends SessionInfo {
  total_tokens: number;
  duration_ms: number;
  output_zip_path?: string | null;
  has_conversation: boolean;
  has_summary: boolean;
}

export interface FileEntry {
  name: string;
  path: string;
  is_dir: boolean;
  size: number;
}

export interface DiffEntry {
  path: string;
  status: 'added' | 'deleted' | 'modified';
  diff: string;
  additions: number;
  deletions: number;
}

// Conversation message types
export interface TextBlock {
  type: 'text';
  text: string;
}

export interface ToolUseBlock {
  type: 'tool_use';
  id: string;
  name: string;
  input: Record<string, unknown>;
}

export interface ThinkingBlock {
  type: 'thinking';
  thinking: string;
}

export interface ToolResultBlock {
  type: 'tool_result';
  tool_use_id: string;
  content: string | unknown;
  is_error?: boolean;
}

export type ContentBlock = TextBlock | ToolUseBlock | ThinkingBlock | ToolResultBlock;

export interface ConversationMessage {
  type: 'assistant' | 'user' | 'system' | 'result';
  content?: string | ContentBlock[];
  model?: string;
  subtype?: string;
  data?: Record<string, unknown>;
  // Result fields
  duration_ms?: number;
  num_turns?: number;
  total_cost_usd?: number;
  is_error?: boolean;
  result?: string;
}
