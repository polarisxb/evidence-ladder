export type EmailFolder = 'inbox' | 'sent' | 'trash';

export type AuditOperation =
  | 'list_emails'
  | 'read_email'
  | 'send_email'
  | 'forward_email'
  | 'delete_email'
  | 'search_emails';

export interface User {
  id: string;
  name: string;
  email: string;
  createdAt: string;
}

export interface Email {
  id: string;
  ownerUserId: string;
  folder: EmailFolder;
  fromAddr: string;
  toAddr: string;
  subject: string;
  body: string;
  isRead: number;
  createdAt: string;
}

export interface EmailAuditLog {
  id: number;
  operation: AuditOperation;
  emailId: string | null;
  sessionUserId: string;
  recipient: string | null;
  detail: string;
  executedAt: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolCallRecord {
  name: string;
  arguments: string;
  result: string;
}

export interface ChatResult {
  response: string;
  modelInvoked: boolean;
  postProcessed: boolean;
  blockReason?: string | null;
  postReason?: string | null;
  toolCalls?: ToolCallRecord[];
}

export interface ChatRequest {
  message: string;
  userId: string;
  history?: ChatMessage[];
}

export interface LlmMessage {
  role: string;
  content?: string | null;
  tool_calls?: LlmToolCall[];
  tool_call_id?: string;
}

export interface LlmToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}
