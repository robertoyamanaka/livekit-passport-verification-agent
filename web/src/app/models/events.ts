// Shapes mirrored from the agent's LiveKit Text Stream payloads.
// Keep this in sync with agent/src/agent.py's send_text() calls.

/** Mirrors agent/src/topics.py — must stay in exact string sync with it (and
 * with each interface's own `type` field below), since both sides key off
 * these same string literals with no shared, statically-checked contract. */
export const TOPICS = {
  transcript: 'transcript',
  agentState: 'agent_state',
  capturedPhoto: 'captured_photo',
  verdict: 'verdict',
  contractReady: 'contract_ready',
  contractSigned: 'contract_signed',
  signature: 'signature',
} as const;

export interface TranscriptEvent {
  type: typeof TOPICS.transcript;
  role: 'agent' | 'user';
  text: string;
  final: boolean;
  timestamp: number;
}

export interface AgentStateEvent {
  type: typeof TOPICS.agentState;
  state: 'awaiting_document';
  timestamp: number;
}

export interface CapturedPhotoEvent {
  type: typeof TOPICS.capturedPhoto;
  image_base64: string;
  captured_at: number;
}

export interface VerdictEvent {
  type: typeof TOPICS.verdict;
  status: 'validated' | 'needs_review';
  customer_name: string;
  document_name: string;
  document_number: string;
  reason: string;
  confidence_note: string;
  timestamp: number;
}

export interface ContractReadyEvent {
  type: typeof TOPICS.contractReady;
  contract_number: string;
  vehicle: string;
  amount_financed: string;
  paragraphs: string[];
  timestamp: number;
}

export interface SignatureSubmission {
  type: typeof TOPICS.signature;
  typed_name: string;
  signature_image_base64: string;
  signed_at: number;
}

export interface ContractSignedEvent {
  type: typeof TOPICS.contractSigned;
  contract_sent: boolean;
  contract_email: string;
  timestamp: number;
}

export interface TokenResponse {
  token: string;
  url: string;
  room: string;
}
