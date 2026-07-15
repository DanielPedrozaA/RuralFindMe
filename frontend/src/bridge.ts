export type ResultType =
  | "ASSIGNED"
  | "EXEMPT"
  | "NOT_SELECTED"
  | "NOT_FOUND"
  | "AMBIGUOUS"
  | "ERROR";

export type ProcessingStage =
  | "VALIDATING_DOCUMENTS"
  | "EXTRACTING_TEXT"
  | "IDENTIFYING_DOCUMENT_TYPES"
  | "SEARCHING_IDENTIFICATION"
  | "VERIFYING_EVIDENCE"
  | "CLASSIFYING_RESULT"
  | "READY_TO_REVEAL";

export interface DocumentMetadata {
  slot: number;
  filename: string;
  size_bytes: number;
  page_count: number;
  valid: boolean;
  validation_state: "READY" | "WARNING" | "ERROR";
  category: string;
  category_label: string;
  allocation_round: string;
  record_count?: number;
  warnings: string[];
  errors: string[];
}

export interface EvidenceRecord {
  full_name?: string;
  masked_id?: string;
  id_type?: string;
  official_status?: string;
  institution?: string;
  municipality?: string;
  department?: string;
  vacancy_code?: string;
  profession?: string;
  reps_code?: string;
  reps_site?: string;
  modality?: string;
  assignment_date?: string;
  start_date?: string;
  duration?: string;
  contact?: string;
  observations?: string;
  source_file: string;
  source_page: number;
  confidence: number;
  confidence_label: string;
  raw_text?: string;
}

export interface SearchResultPayload {
  result_type: ResultType;
  masked_id: string;
  allocation_round: string;
  record?: EvidenceRecord;
  evidence: EvidenceRecord[];
  reasons: string[];
  document_summary: string[];
}

export interface BackendState {
  documents: Array<DocumentMetadata | null>;
  can_continue: boolean;
  allocation_round: string;
  sound_enabled: boolean;
  reduced_animation: boolean;
}

export interface ValidationPayload {
  valid: boolean;
  requires_confirmation: boolean;
  warnings: string[];
  allocation_round: string;
}

export interface BackendApi {
  readonly connected: true;
}

declare global {
  interface Window {
    qt?: { webChannelTransport: unknown };
    __ruralFindMeTakeDesktopCommands?: () => DesktopCommand[];
    __ruralFindMeReceiveDesktopEvents?: (events: DesktopEvent[]) => void;
  }
}

export type DesktopCommand =
  | { name: "selectPdfs"; args: [] }
  | { name: "validateDocuments"; args: [boolean] }
  | { name: "searchDoctor"; args: [string, string, string] }
  | { name: "resetApplication"; args: [] }
  | { name: "exportResult"; args: [] }
  | { name: "copyResult"; args: [] }
  | { name: "notifyReveal"; args: [] }
  | { name: "updatePreferences"; args: [boolean, boolean] };

let desktopCommands: DesktopCommand[] = [];

export function sendDesktopCommand(command: DesktopCommand): void {
  desktopCommands.push(command);
}

window.__ruralFindMeTakeDesktopCommands = () => {
  const commands = desktopCommands;
  desktopCommands = [];
  return commands;
};

export interface BridgeHandlers {
  onState(state: BackendState): void;
  onDocument(slot: number, document: DocumentMetadata | null): void;
  onDocumentBatchState(busy: boolean, message: string): void;
  onValidation(payload: ValidationPayload): void;
  onStage(stage: ProcessingStage, message: string): void;
  onResult(result: SearchResultPayload): void;
  onFailure(message: string): void;
  onExport(message: string): void;
}

interface DesktopEvent {
  name: string;
  args: unknown[];
}

const parse = <T,>(value: string): T => JSON.parse(value) as T;
let activeHandlers: BridgeHandlers | null = null;

window.__ruralFindMeReceiveDesktopEvents = (events) => {
  const handlers = activeHandlers;
  if (!handlers) return;
  for (const event of events) {
    try {
      switch (event.name) {
        case "stateSnapshot":
          handlers.onState(parse(event.args[0] as string));
          break;
        case "documentSelected":
          handlers.onDocument(event.args[0] as number, parse(event.args[1] as string));
          break;
        case "documentBatchStateChanged":
          handlers.onDocumentBatchState(event.args[0] as boolean, event.args[1] as string);
          break;
        case "documentValidationUpdated":
          handlers.onValidation(parse(event.args[0] as string));
          break;
        case "processingStageChanged":
          handlers.onStage(event.args[0] as ProcessingStage, event.args[1] as string);
          break;
        case "searchCompleted":
          handlers.onResult(parse(event.args[0] as string));
          break;
        case "processingFailed":
          handlers.onFailure(event.args[0] as string);
          break;
        case "exportCompleted":
          handlers.onExport(event.args[0] as string);
          break;
      }
    } catch {
      handlers.onFailure("El contenedor local devolvió un mensaje no válido.");
    }
  }
};

export function connectBackend(handlers: BridgeHandlers): Promise<BackendApi> {
  return new Promise((resolve, reject) => {
    if (!window.qt?.webChannelTransport) {
      reject(new Error("El contenedor de escritorio no está disponible. Abra la interfaz desde RuralFindMe."));
      return;
    }
    activeHandlers = handlers;
    resolve({ connected: true });
  });
}
