// Shapes mirrored from the agent's LiveKit Text Stream payloads.
// Keep this in sync with agent/src/agent.py's send_text() calls.

export interface TranscriptEvent {
  type: 'transcript';
  role: 'agent' | 'user';
  text: string;
  final: boolean;
  timestamp: number;
}

export interface AgentStateEvent {
  type: 'agent_state';
  state: 'awaiting_document';
  timestamp: number;
}

export interface CapturedPhotoEvent {
  type: 'captured_photo';
  image_base64: string;
  captured_at: number;
}

export interface VerdictEvent {
  type: 'verdict';
  status: 'validated' | 'needs_review';
  customer_name: string;
  document_name: string;
  document_number: string;
  reason: string;
  confidence_note: string;
  timestamp: number;
}

export interface ContractReadyEvent {
  type: 'contract_ready';
  contract_number: string;
  vehicle: string;
  amount_financed: string;
  paragraphs: string[];
  timestamp: number;
}

export interface SignatureSubmission {
  type: 'signature';
  typed_name: string;
  signature_image_base64: string;
  signed_at: number;
}

export interface ContractSignedEvent {
  type: 'contract_signed';
  contract_sent: boolean;
  contract_email: string;
  timestamp: number;
}

export interface TokenResponse {
  token: string;
  url: string;
  room: string;
}
