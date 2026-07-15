import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import { AnimatePresence, MotionConfig } from "motion/react";
import * as motion from "motion/react-client";
import confetti from "canvas-confetti";
import {
  AlertCircle,
  ArrowLeft,
  Building2,
  Calendar,
  Check,
  ChevronRight,
  Clipboard,
  Clock,
  Download,
  FileText,
  Hash,
  LoaderCircle,
  MapPin,
  RotateCcw,
  Search,
  ShieldCheck,
  Stethoscope,
  Upload,
  Users,
  X,
} from "lucide-react";
import {
  connectBackend,
  sendDesktopCommand,
  type BackendApi,
  type BackendState,
  type DocumentMetadata,
  type EvidenceRecord,
  type ProcessingStage,
  type SearchResultPayload,
  type ValidationPayload,
} from "../bridge";
import {
  ASSIGNED_REVEAL_DELAYS,
  EASE_STANDARD,
  PREPARATION_MINIMUM_MS,
} from "./animation";

type Screen =
  | "welcome"
  | "upload"
  | "identification"
  | "preparation"
  | "result-assigned"
  | "result-exempt"
  | "result-not-selected"
  | "result-not-found"
  | "result-ambiguous"
  | "result-error";

const EMPTY_STATE: BackendState = {
  documents: [null, null, null],
  can_continue: false,
  allocation_round: "",
  sound_enabled: true,
  reduced_animation: false,
};

const FILE_SLOTS = [
  {
    label: "Plazas asignadas",
    hint: "Reporte que relaciona la plaza con la identificación profesional",
  },
  {
    label: "Plazas vacantes",
    hint: "Reporte de posiciones que permanecieron sin asignar",
  },
  {
    label: "Profesionales sin plaza",
    hint: "Reporte explícito de profesionales sin plaza asignada",
  },
];

const STAGE_ORDER: ProcessingStage[] = [
  "VALIDATING_DOCUMENTS",
  "EXTRACTING_TEXT",
  "IDENTIFYING_DOCUMENT_TYPES",
  "SEARCHING_IDENTIFICATION",
  "VERIFYING_EVIDENCE",
  "CLASSIFYING_RESULT",
  "READY_TO_REVEAL",
];

const STAGE_LABELS: Record<ProcessingStage, string> = {
  VALIDATING_DOCUMENTS: "Validando los documentos oficiales…",
  EXTRACTING_TEXT: "Extrayendo el contenido y reconstruyendo las tablas…",
  IDENTIFYING_DOCUMENT_TYPES: "Confirmando la ronda y cada tipo de reporte…",
  SEARCHING_IDENTIFICATION: "Buscando su identificación exacta…",
  VERIFYING_EVIDENCE: "Verificando las filas y sus fuentes…",
  CLASSIFYING_RESULT: "Clasificando el resultado con reglas deterministas…",
  READY_TO_REVEAL: "Su resultado está listo para ser revelado…",
};

const OrchidMotif = ({
  className = "",
  opacity = 1,
}: {
  className?: string;
  opacity?: number;
}) => (
  <svg viewBox="0 0 120 120" fill="none" className={className} style={{ opacity }} aria-hidden="true">
    {[0, 72, 144, 216, 288].map((rotation) => (
      <ellipse
        key={rotation}
        cx="60"
        cy="28"
        rx="10"
        ry="22"
        fill="currentColor"
        opacity="0.18"
        transform={`rotate(${rotation} 60 60)`}
      />
    ))}
    <circle cx="60" cy="60" r="11" fill="currentColor" opacity="0.32" />
    <circle cx="60" cy="60" r="5" fill="currentColor" opacity="0.55" />
  </svg>
);

const TricolorStrip = ({ className = "" }: { className?: string }) => (
  <div className={`flex ${className}`} aria-hidden="true">
    <div className="flex-[2] bg-[#FCD116]" />
    <div className="flex-1 bg-[#003087]" />
    <div className="flex-1 bg-[#CE1126]" />
  </div>
);

const OrnamentalRule = ({ className = "" }: { className?: string }) => (
  <div className={`flex items-center gap-3 ${className}`} aria-hidden="true">
    <div className="flex-1 h-px bg-current opacity-15" />
    <div className="w-1 h-1 rounded-full bg-current opacity-30" />
    <div className="w-1.5 h-1.5 rounded-full bg-current opacity-50" />
    <div className="w-1 h-1 rounded-full bg-current opacity-30" />
    <div className="flex-1 h-px bg-current opacity-15" />
  </div>
);

const PaperGrain = () => (
  <div className="paper-grain absolute inset-0 pointer-events-none" aria-hidden="true" />
);

const Shell = ({ children, className = "" }: { children: ReactNode; className?: string }) => (
  <div className={`relative min-h-screen w-full overflow-x-hidden bg-background text-foreground ${className}`}>
    <PaperGrain />
    {children}
  </div>
);

const RoundLabel = ({ round }: { round: string }) => (
  <span className="font-mono text-caption text-muted-foreground">
    {round ? `Ronda ${round}` : "Ronda definida por los PDF"}
  </span>
);

const TopBar = ({
  onBack,
  step,
  totalSteps,
  round,
}: {
  onBack?: () => void;
  step?: number;
  totalSteps?: number;
  round: string;
}) => (
  <header className="relative z-20 flex items-center justify-between px-10 max-sm:px-5 py-5 border-b border-border">
    <div className="flex items-center gap-3">
      {onBack ? (
        <button onClick={onBack} className="group flex items-center gap-2 text-muted-foreground hover:text-foreground transition-colors text-sm">
          <ArrowLeft size={15} className="group-hover:-translate-x-0.5 transition-transform" />
          Volver
        </button>
      ) : (
        <div className="flex items-center gap-2.5">
          <OrchidMotif className="w-6 h-6 text-accent" />
          <span className="font-mono text-caption font-semibold tracking-[0.18em] uppercase text-muted-foreground">
            SSO · Consulta local
          </span>
        </div>
      )}
    </div>
    <div className="flex items-center gap-6">
      {step !== undefined && totalSteps !== undefined && (
        <div className="flex items-center gap-1.5" aria-label={`Paso ${step + 1} de ${totalSteps}`}>
          {Array.from({ length: totalSteps }).map((_, index) => (
            <div
              key={index}
              className={`rounded-full transition-all duration-500 ${
                index < step ? "w-4 h-1.5 bg-primary" : index === step ? "w-6 h-1.5 bg-accent" : "w-4 h-1.5 bg-border"
              }`}
            />
          ))}
        </div>
      )}
      <RoundLabel round={round} />
    </div>
  </header>
);

const formatBytes = (bytes: number) =>
  bytes >= 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${(bytes / 1024).toFixed(1)} KB`;

const documentRowStateClass = (document: DocumentMetadata | null) => {
  if (!document) return "border-border bg-card hover:border-primary/20 hover:bg-card/60";
  return document.valid
    ? "border-primary/25 bg-primary/[0.04]"
    : "border-destructive/30 bg-destructive/[0.03]";
};

const DocumentRow = ({
  label,
  hint,
  document,
  index,
}: {
  label: string;
  hint: string;
  document: DocumentMetadata | null;
  index: number;
}) => (
  <motion.div
    initial={{ opacity: 0, y: 20 }}
    animate={{ opacity: 1, y: 0 }}
    transition={{ delay: index * 0.12, duration: 0.5, ease: EASE_STANDARD }}
  >
    <div
      className={`w-full text-left rounded-xl border transition-all duration-300 relative overflow-hidden ${documentRowStateClass(document)}`}
    >
      <div className="flex items-start gap-4 p-5">
        <div className={`w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0 ${document?.valid ? "bg-primary text-primary-foreground" : "bg-secondary text-muted-foreground"}`}>
          {document?.valid ? <Check size={16} strokeWidth={2.5} /> : <FileText size={16} />}
        </div>
        <div className="flex-1 min-w-0 pt-0.5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-semibold text-foreground leading-tight">{label}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{hint}</p>
            </div>
            <span className="flex items-center gap-1 text-caption text-muted-foreground/70 bg-secondary rounded-md px-2 py-1 flex-shrink-0">
              {document?.valid ? <Check size={10} /> : <FileText size={10} />} {document ? document.validation_state : "Pendiente"}
            </span>
          </div>
          {document && (
            <motion.div
              initial={{ opacity: 0, scaleY: 0 }}
              animate={{ opacity: 1, scaleY: 1 }}
              className="mt-3 origin-top"
            >
              <p className="font-mono text-caption text-primary font-medium truncate">
                {document.filename}
              </p>
              <div className="flex flex-wrap gap-x-3 gap-y-1 mt-1 text-micro text-muted-foreground">
                <span>{formatBytes(document.size_bytes)}</span>
                <span>{document.page_count} pág.</span>
                <span>{document.category_label}</span>
                {document.allocation_round && <span>Ronda {document.allocation_round}</span>}
              </div>
              {(document.errors.length > 0 || document.warnings.length > 0) && (
                <p className={`text-caption mt-1.5 ${document.errors.length ? "text-destructive" : "text-accent"}`}>
                  {[...document.errors, ...document.warnings][0]}
                </p>
              )}
            </motion.div>
          )}
        </div>
      </div>
    </div>
  </motion.div>
);

const WelcomeScreen = ({
  onStart,
  connected,
  connectionError,
  soundEnabled,
  reducedAnimation,
  onPreferences,
}: {
  onStart: () => void;
  connected: boolean;
  connectionError: string;
  soundEnabled: boolean;
  reducedAnimation: boolean;
  onPreferences: (sound: boolean, reduced: boolean) => void;
}) => (
  <div className="min-h-screen w-full grid grid-cols-2 max-lg:grid-cols-1 relative overflow-hidden">
    <div className="relative bg-primary flex flex-col justify-between p-14 overflow-hidden min-h-[680px]">
      <PaperGrain />
      <div className="absolute -bottom-24 -left-24 w-[500px] h-[500px] pointer-events-none">
        <OrchidMotif className="w-full h-full text-primary-foreground" opacity={0.055} />
      </div>
      <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="flex items-center gap-3 relative z-10">
        <OrchidMotif className="w-7 h-7 text-accent" />
        <div>
          <p className="font-mono text-micro font-semibold tracking-[0.22em] uppercase text-primary-foreground/50">
            RuralFindMe · Consulta no oficial
          </p>
          <p className="font-mono text-micro font-semibold tracking-[0.22em] uppercase text-primary-foreground/50">
            Procesamiento privado y local
          </p>
        </div>
      </motion.div>
      <div className="relative z-10">
        <motion.div initial={{ opacity: 0, y: 32 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.9, delay: 0.2, ease: EASE_STANDARD }}>
          <p className="font-mono text-caption tracking-[0.3em] uppercase text-accent mb-6 font-medium">
            Servicio Social Obligatorio
          </p>
          <h1 className="font-serif text-display-xl leading-[1.0] text-primary-foreground mb-8">
            Su resultado<br />de asignación<br /><span className="italic text-accent">le aguarda.</span>
          </h1>
          <p className="text-primary-foreground/55 text-body leading-relaxed max-w-prose-narrow">
            Consulte tres reportes de una misma ronda. La aplicación no sube los PDF ni la identificación a internet.
          </p>
        </motion.div>
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.55, duration: 0.7 }} className="mt-10">
          <button
            onClick={onStart}
            disabled={!connected}
            className="group inline-flex items-center gap-3 bg-accent text-accent-foreground rounded-xl px-8 py-4 text-sm font-semibold hover:bg-accent/90 disabled:opacity-40 disabled:cursor-not-allowed active:scale-[0.98] transition-all"
          >
            Consultar mi resultado
            <ChevronRight size={16} className="group-hover:translate-x-0.5 transition-transform" />
          </button>
          <p className="text-primary-foreground/35 text-xs mt-3 pl-1">
            {connected ? "Todo se procesa en este computador" : connectionError || "Conectando con el motor local…"}
          </p>
        </motion.div>
      </div>
      <TricolorStrip className="h-1 rounded-full relative z-10" />
    </div>

    <div className="relative bg-background flex flex-col items-center justify-center p-14 overflow-hidden min-h-[680px]">
      <PaperGrain />
      <div className="absolute top-0 right-0 w-64 h-64 pointer-events-none">
        <OrchidMotif className="w-full h-full text-foreground" opacity={0.04} />
      </div>
      <motion.div initial={{ opacity: 0, scale: 0.94, y: 24 }} animate={{ opacity: 1, scale: 1, y: 0 }} transition={{ duration: 1, delay: 0.35, ease: EASE_STANDARD }} className="w-full max-w-card relative z-10">
        <div className="bg-card rounded-2xl border border-border shadow-[0_2px_24px_rgba(0,0,0,0.07)] overflow-hidden">
          <TricolorStrip className="h-[3px]" />
          <div className="p-8">
            <div className="flex items-start justify-between mb-7">
              <div>
                <p className="font-mono text-micro tracking-[0.2em] uppercase text-muted-foreground font-medium mb-1">
                  Resumen de consulta
                </p>
                <p className="font-mono text-micro text-muted-foreground/70">
                  Basado exclusivamente en sus PDF
                </p>
              </div>
              <ShieldCheck className="w-9 h-9 text-primary" strokeWidth={1.4} />
            </div>
            <div className="space-y-5">
              {["Identificación enmascarada", "Estado oficial detectado", "Fuente y página"].map((label, index) => (
                <div key={label}>
                  <p className="font-mono text-micro tracking-[0.15em] uppercase text-muted-foreground mb-2 font-medium">
                    {label}
                  </p>
                  <div className={`${index === 1 ? "h-14" : "h-8"} rounded-lg bg-secondary/60 border border-border/50`} />
                </div>
              ))}
            </div>
            <div className="mt-7 rounded-xl bg-primary/[0.05] p-4 text-caption text-muted-foreground leading-relaxed">
              Esta herramienta no sustituye la publicación oficial ni certifica una exoneración.
            </div>
          </div>
        </div>
        <div className="mt-5 flex items-center justify-between gap-4 text-xs text-muted-foreground">
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={soundEnabled} onChange={(event) => onPreferences(event.target.checked, reducedAnimation)} />
            Sonido
          </label>
          <label className="flex items-center gap-2 cursor-pointer">
            <input type="checkbox" checked={reducedAnimation} onChange={(event) => onPreferences(soundEnabled, event.target.checked)} />
            Reducir animaciones
          </label>
        </div>
      </motion.div>
    </div>
  </div>
);

const UploadScreen = ({
  documents,
  round,
  validation,
  selecting,
  selectionMessage,
  onSelectAll,
  onClear,
  onValidate,
  onBack,
}: {
  documents: Array<DocumentMetadata | null>;
  round: string;
  validation: ValidationPayload | null;
  selecting: boolean;
  selectionMessage: string;
  onSelectAll: () => void;
  onClear: () => void;
  onValidate: (allowMismatch: boolean) => void;
  onBack: () => void;
}) => {
  const count = documents.filter((item) => item?.valid).length;
  const hasDocuments = documents.some(Boolean);
  return (
    <Shell>
      <TopBar onBack={onBack} step={0} totalSteps={3} round={round} />
      <div className="flex-1 flex items-start justify-center pt-10 pb-16 px-8">
        <div className="w-full max-w-content">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="mb-8">
            <p className="font-mono text-micro tracking-[0.25em] uppercase text-accent font-medium mb-3">Paso 1 de 3</p>
            <h1 className="font-serif text-display-md text-foreground mb-3">Los tres reportes</h1>
            <p className="text-muted-foreground text-body leading-relaxed">
              Seleccione los tres PDF a la vez. Python los reconocerá y los ordenará por su contenido; el nombre del archivo por sí solo nunca cuenta como validación.
            </p>
          </motion.div>
          <button
            type="button"
            onClick={onSelectAll}
            disabled={selecting}
            className="w-full min-h-[190px] mb-5 rounded-2xl border-2 border-dashed border-primary/25 bg-card hover:border-primary/45 hover:bg-primary/[0.025] disabled:cursor-wait disabled:opacity-70 transition-all flex flex-col items-center justify-center px-8 text-center"
          >
            <span className="w-14 h-14 rounded-2xl bg-primary text-primary-foreground flex items-center justify-center shadow-sm mb-4">
              {selecting ? <LoaderCircle size={24} className="animate-spin" /> : <Upload size={24} />}
            </span>
            <span className="text-base font-semibold text-foreground">
              {selecting ? "Validando los tres PDF…" : hasDocuments ? "Cambiar los tres PDF" : "Seleccionar los tres PDF"}
            </span>
            <span className="text-xs text-muted-foreground mt-2 max-w-prose">
              {selecting ? selectionMessage || "Todo ocurre localmente y puede tardar unos segundos." : "En el explorador, marque los tres archivos al mismo tiempo y pulse Abrir."}
            </span>
          </button>
          {hasDocuments && (
            <div className="space-y-2.5 mb-6">
              <div className="flex items-center justify-between px-1 pb-1">
                <p className="font-mono text-micro tracking-[0.18em] uppercase text-muted-foreground">Archivos reconocidos</p>
                <button type="button" onClick={onClear} disabled={selecting} className="text-xs text-muted-foreground hover:text-destructive disabled:opacity-40">Quitar todos</button>
              </div>
              {FILE_SLOTS.map((slot, index) => (
                <DocumentRow
                  key={slot.label}
                  {...slot}
                  index={index}
                  document={documents[index] ?? null}
                />
              ))}
            </div>
          )}
          {validation && !validation.valid && (
            <div className="bg-accent/8 border border-accent/20 rounded-xl p-4 mb-5">
              <div className="flex items-start gap-3">
                <AlertCircle size={16} className="text-accent mt-0.5 flex-shrink-0" />
                <div className="flex-1">
                  <p className="text-sm font-semibold">Los documentos requieren atención</p>
                  {validation.warnings.map((warning) => <p key={warning} className="text-xs text-muted-foreground mt-1">{warning}</p>)}
                  {validation.requires_confirmation && (
                    <button onClick={() => onValidate(true)} className="mt-3 text-xs font-semibold text-accent hover:underline">
                      Entiendo el riesgo y deseo continuar
                    </button>
                  )}
                </div>
              </div>
            </div>
          )}
          <div className="space-y-4">
            <div className="flex items-center gap-3">
              <div
                className="flex-1 h-1 bg-secondary rounded-full overflow-hidden"
                role="progressbar"
                aria-label="Documentos válidos"
                aria-valuemin={0}
                aria-valuemax={3}
                aria-valuenow={count}
              >
                <motion.div
                  className="h-full w-full origin-left bg-accent rounded-full"
                  initial={false}
                  animate={{ scaleX: count / 3 }}
                />
              </div>
              <span className="font-mono text-xs text-muted-foreground min-w-[60px]">{count}/3 válidos</span>
            </div>
            <button
              onClick={() => onValidate(false)}
              disabled={count !== 3 || selecting}
              className="group w-full flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-xl py-4 text-sm font-semibold hover:bg-primary/90 disabled:opacity-35 disabled:cursor-not-allowed active:scale-[0.99] transition-all"
            >
              {count === 3 ? "Validar la ronda y continuar" : `Faltan ${3 - count} PDF válidos`}
              {count === 3 && <ChevronRight size={15} />}
            </button>
          </div>
        </div>
      </div>
    </Shell>
  );
};

interface DoctorInput {
  idNumber: string;
}

const IdentificationScreen = ({ onNext, onBack, round }: { onNext: (input: DoctorInput) => void; onBack: () => void; round: string }) => {
  const [idNumber, setIdNumber] = useState("");
  const digits = idNumber.replace(/\D/g, "");
  const valid = digits.length >= 5 && digits.length <= 15;
  return (
    <Shell>
      <TopBar onBack={onBack} step={1} totalSteps={3} round={round} />
      <div className="flex-1 flex items-start justify-center pt-12 pb-20 px-8">
        <div className="w-full max-w-form">
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="mb-9">
            <p className="font-mono text-micro tracking-[0.25em] uppercase text-accent font-medium mb-3">Paso 2 de 3</p>
            <h1 className="font-serif text-display-md text-foreground mb-3">Su identificación</h1>
            <p className="text-muted-foreground text-body leading-relaxed">Ingrese únicamente su número de identificación, tal como aparece en los documentos de la ronda.</p>
          </motion.div>
          <div className="mb-7">
            <label htmlFor="identification-number" className="block text-xs font-semibold text-muted-foreground uppercase tracking-widest mb-2">Número de identificación</label>
            <input
              id="identification-number"
              autoFocus
              inputMode="numeric"
              autoComplete="off"
              value={idNumber}
              onChange={(event) => setIdNumber(event.target.value)}
              onKeyDown={(event) => event.key === "Enter" && valid && onNext({ idNumber: digits })}
              placeholder="p. ej. 1.032.487.221"
              className="font-serif w-full bg-card border border-border rounded-xl px-5 py-4 text-xl placeholder:text-muted-foreground/35 focus:outline-none focus:ring-2 focus:ring-ring/25"
            />
          </div>
          <div className="bg-secondary/50 border border-border rounded-xl p-4 mb-6 flex gap-3">
            <ShieldCheck size={16} className="text-primary flex-shrink-0 mt-0.5" />
            <p className="text-xs text-muted-foreground leading-relaxed">La identificación no se escribe en registros de diagnóstico y se enmascara antes de copiar o exportar.</p>
          </div>
          <button onClick={() => onNext({ idNumber: digits })} disabled={!valid} className="group w-full flex items-center justify-center gap-2.5 bg-primary text-primary-foreground rounded-xl py-4 text-sm font-semibold hover:bg-primary/90 disabled:opacity-35 disabled:cursor-not-allowed">
            Consultar resultado <ChevronRight size={15} />
          </button>
        </div>
      </div>
    </Shell>
  );
};

const PreparationScreen = ({
  stageQueue,
  resultReady,
  onComplete,
  reducedAnimation,
}: {
  stageQueue: ProcessingStage[];
  resultReady: boolean;
  onComplete: () => void;
  reducedAnimation: boolean;
}) => {
  const [visibleIndex, setVisibleIndex] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const startedAt = useRef(Date.now());
  const completed = useRef(false);
  const activeStage = stageQueue[Math.min(visibleIndex, stageQueue.length - 1)] ?? "VALIDATING_DOCUMENTS";

  useEffect(() => {
    if (visibleIndex >= stageQueue.length - 1) return;
    const timer = window.setTimeout(() => setVisibleIndex((value) => value + 1), reducedAnimation ? 80 : 620);
    return () => window.clearTimeout(timer);
  }, [visibleIndex, stageQueue.length, reducedAnimation]);

  useEffect(() => {
    if (!resultReady || activeStage !== "READY_TO_REVEAL" || completed.current) return;
    const remaining = skipped || reducedAnimation ? 0 : Math.max(0, PREPARATION_MINIMUM_MS - (Date.now() - startedAt.current));
    const timer = window.setTimeout(() => {
      completed.current = true;
      onComplete();
    }, remaining);
    return () => window.clearTimeout(timer);
  }, [resultReady, activeStage, skipped, reducedAnimation, onComplete]);

  const stageIndex = Math.max(0, STAGE_ORDER.indexOf(activeStage));
  const sealBroken = stageIndex >= 4;
  const flapOpen = stageIndex >= 5;
  const letterUp = activeStage === "READY_TO_REVEAL";
  return (
    <div className="min-h-screen bg-primary flex flex-col items-center justify-center relative overflow-hidden">
      <PaperGrain />
      {[{ size: 420, top: "8%", left: "3%", rotate: 15 }, { size: 320, top: "55%", left: "78%", rotate: -30 }].map((item, index) => (
        <div key={index} className="absolute pointer-events-none" style={{ width: item.size, height: item.size, top: item.top, left: item.left, transform: `rotate(${item.rotate}deg)` }}>
          <OrchidMotif className="w-full h-full text-primary-foreground" opacity={0.04} />
        </div>
      ))}
      <div className="relative" style={{ perspective: "900px" }}>
        <motion.div className="relative w-80 h-52 rounded-2xl overflow-hidden" style={{ background: "rgba(251,248,243,0.12)", border: "1px solid rgba(251,248,243,0.16)" }} animate={!reducedAnimation && !sealBroken ? { scale: [1, 1.015, 1], transition: { repeat: Infinity, duration: 2.4 } } : {}}>
          <div className="absolute inset-0" style={{ background: "linear-gradient(135deg,rgba(251,248,243,.06) 50%,transparent 50%),linear-gradient(225deg,rgba(251,248,243,.06) 50%,transparent 50%)" }} />
          <motion.div className="absolute top-0 left-0 right-0 origin-top" animate={{ rotateX: flapOpen ? -178 : 0, opacity: flapOpen ? 0 : 1 }} transition={{ duration: reducedAnimation ? 0 : 0.9 }}>
            <div style={{ width: 0, height: 0, borderLeft: "160px solid transparent", borderRight: "160px solid transparent", borderTop: "110px solid rgba(251,248,243,0.13)" }} />
          </motion.div>
          <motion.div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 z-10" animate={sealBroken ? { scale: 0.4, opacity: 0, rotate: 12 } : { scale: 1, opacity: 1 }}>
            <div className="w-16 h-16 rounded-full bg-accent flex items-center justify-center shadow-lg"><OrchidMotif className="w-10 h-10 text-accent-foreground" /></div>
          </motion.div>
          {letterUp && (
            <motion.div initial={{ y: 60, opacity: 0 }} animate={{ y: -72, opacity: 1 }} className="absolute left-4 right-4 bottom-4 bg-card rounded-xl p-5 shadow-2xl z-20">
              <div className="space-y-2">{["w-3/4", "w-full", "w-5/6", "w-2/3"].map((width) => <div key={width} className={`h-1.5 bg-foreground/10 rounded-full ${width}`} />)}</div>
            </motion.div>
          )}
        </motion.div>
      </div>
      <div className="mt-16 h-6 flex items-center" aria-live="polite" aria-atomic="true">
        <AnimatePresence mode="wait">
          <motion.p key={activeStage} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="font-mono text-primary-foreground/55 text-sm">
            {STAGE_LABELS[activeStage]}
          </motion.p>
        </AnimatePresence>
      </div>
      <div className="mt-7 flex items-center gap-2">
        {STAGE_ORDER.map((stage, index) => (
          <div key={stage} className={`h-1.5 rounded-full transition-all ${index <= stageIndex ? "w-7 bg-accent" : "w-4 bg-primary-foreground/12"}`} />
        ))}
      </div>
      <button onClick={() => setSkipped(true)} disabled={skipped} className="mt-8 text-xs text-primary-foreground/45 hover:text-primary-foreground/75 disabled:opacity-40">
        {skipped && !resultReady ? "Esperando que finalice el análisis…" : "Saltar animación"}
      </button>
    </div>
  );
};

const ResultHeader = ({ round, label = "Resultado basado en documentos" }: { round: string; label?: string }) => (
  <header className="relative z-20 flex items-center justify-between px-10 max-sm:px-5 py-5 border-b border-border">
    <div className="flex items-center gap-2.5">
      <OrchidMotif className="w-6 h-6 text-accent" />
      <span className="font-mono text-caption font-semibold tracking-[0.18em] uppercase text-muted-foreground">SSO · Colombia</span>
    </div>
    <div className="flex items-center gap-3">
      <span className="flex items-center gap-1.5 text-caption font-medium text-success-foreground bg-success px-3 py-1 rounded-full"><Check size={11} />{label}</span>
      <RoundLabel round={round} />
    </div>
  </header>
);

const ResultActions = ({ onExport, onCopy, onAgain }: { onExport: () => void; onCopy: () => void; onAgain: () => void }) => (
  <div className="flex max-sm:flex-col gap-3 mt-5">
    <button onClick={onExport} className="flex-1 flex items-center justify-center gap-2 bg-primary text-primary-foreground rounded-xl py-3.5 text-sm font-semibold hover:bg-primary/90"><Download size={15} />Exportar resumen</button>
    <button onClick={onCopy} className="flex items-center gap-2 bg-secondary rounded-xl px-5 py-3.5 text-sm font-semibold hover:bg-secondary/70"><Clipboard size={14} />Copiar</button>
    <button onClick={onAgain} className="flex items-center gap-2 bg-secondary rounded-xl px-5 py-3.5 text-sm font-semibold hover:bg-secondary/70"><RotateCcw size={14} />Otra consulta</button>
  </div>
);

const EvidenceDetails = ({ evidence }: { evidence: EvidenceRecord[] }) => {
  if (!evidence.length) return null;
  return (
    <details className="mt-5 bg-secondary/30 border border-border rounded-xl p-4">
      <summary className="cursor-pointer text-xs font-semibold text-muted-foreground">Ver evidencia extraída</summary>
      <div className="mt-3 space-y-3">
        {evidence.map((record, index) => (
          <div key={`${record.source_file}-${record.source_page}-${index}`} className="text-caption text-muted-foreground">
            <p className="font-semibold text-foreground">{record.source_file} · página {record.source_page}</p>
            {record.raw_text && <p className="mt-1 font-mono whitespace-pre-wrap break-words">{record.raw_text}</p>}
          </div>
        ))}
      </div>
    </details>
  );
};

const AssignedScreen = ({ result, onExport, onCopy, onAgain, reducedAnimation }: { result: SearchResultPayload; onExport: () => void; onCopy: () => void; onAgain: () => void; reducedAnimation: boolean }) => {
  const record = result.record;
  const [stage, setStage] = useState(reducedAnimation ? 4 : 0);
  useEffect(() => {
    if (reducedAnimation) return;
    const timers = ASSIGNED_REVEAL_DELAYS.map((delay, index) => window.setTimeout(() => setStage(index + 1), delay));
    return () => timers.forEach(window.clearTimeout);
  }, [reducedAnimation]);
  useEffect(() => {
    if (stage !== 4 || reducedAnimation) return;
    confetti({ particleCount: 90, spread: 70, origin: { y: 0.65 }, colors: ["#FCD116", "#003087", "#CE1126", "#B55524"] });
  }, [stage, reducedAnimation]);
  if (!record) return null;
  const optionalMeta = [
    ["Inicio", record.start_date, Calendar],
    ["Duración", record.duration, Clock],
    ["Modalidad", record.modality, Stethoscope],
    ["Fecha de asignación", record.assignment_date, Calendar],
  ].filter(([, value]) => Boolean(value)) as Array<[string, string, typeof Calendar]>;
  return (
    <Shell>
      <ResultHeader round={result.allocation_round} />
      <div className="flex-1 flex flex-col items-center justify-center px-8 py-10">
        <motion.div initial={{ opacity: 0, y: -16 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-8">
          <p className="font-mono text-micro tracking-[0.3em] uppercase text-accent font-medium mb-3">Resultado de asignación</p>
          <h1 className="font-serif text-display-lg text-foreground leading-tight">Encontramos tu asignación</h1>
        </motion.div>
        <div className="w-full max-w-result">
          <div className="bg-card rounded-2xl border border-border shadow-[0_4px_32px_rgba(0,0,0,0.08)] overflow-hidden">
            <TricolorStrip className="h-[3px]" />
            <div className="p-9">
              <div className="flex items-start justify-between mb-7">
                <div>
                  <p className="font-mono text-micro tracking-[0.22em] uppercase text-muted-foreground font-medium">Registro reconstruido</p>
                  <p className="font-mono text-caption text-muted-foreground/70 mt-1">{record.vacancy_code || record.official_status}</p>
                </div>
                <OrchidMotif className="w-12 h-12 text-primary" />
              </div>
              {record.institution && (
                <div className="mb-7">
                  <p className="font-mono flex items-center gap-2 text-micro tracking-[0.2em] uppercase text-muted-foreground font-medium mb-3"><Building2 size={11} className="text-accent" />Debe dirigirse a</p>
                  <AnimatePresence>{stage >= 1 && <motion.p initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="font-serif text-3xl leading-tight">{record.institution}</motion.p>}</AnimatePresence>
                </div>
              )}
              {record.municipality && (
                <div className="rounded-xl border border-border bg-secondary/35 p-5">
                  <p className="font-mono flex items-center gap-2 text-micro tracking-[0.2em] uppercase text-muted-foreground font-medium mb-3"><MapPin size={11} className="text-accent" />Ubicación</p>
                  <AnimatePresence>{stage >= 2 && <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}><p className="font-serif text-display-md leading-none">{record.municipality}</p>{record.department && <p className="font-serif text-lg italic text-muted-foreground mt-1">{record.department}</p>}</motion.div>}</AnimatePresence>
                </div>
              )}
              {stage >= 3 && optionalMeta.length > 0 && <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className="grid grid-cols-2 max-sm:grid-cols-1 gap-3 mt-5">{optionalMeta.map(([label, value, Icon]) => <div key={label} className="bg-secondary/50 rounded-xl p-4 flex gap-3"><Icon size={18} className="text-accent" /><div><p className="text-micro uppercase tracking-widest text-muted-foreground">{label}</p><p className="text-sm font-semibold">{value}</p></div></div>)}</motion.div>}
            </div>
            <div className="font-mono border-t border-border px-9 py-4 bg-secondary/30 flex flex-wrap items-center justify-between gap-2 text-micro text-muted-foreground">
              <span>{record.source_file} · pág. {record.source_page}</span><span>{record.confidence_label} · {Math.round(record.confidence * 100)}% · {result.masked_id}</span>
            </div>
          </div>
          <EvidenceDetails evidence={result.evidence} />
          {stage >= 4 && <ResultActions onExport={onExport} onCopy={onCopy} onAgain={onAgain} />}
        </div>
      </div>
    </Shell>
  );
};

const StatusScreen = ({ result, exempt, onExport, onCopy, onAgain }: { result: SearchResultPayload; exempt: boolean; onExport: () => void; onCopy: () => void; onAgain: () => void }) => {
  const record = result.record;
  return (
    <Shell>
      <ResultHeader round={result.allocation_round} />
      <div className="flex-1 grid grid-cols-2 max-lg:grid-cols-1 min-h-0">
        <div className="flex flex-col justify-center p-16 max-lg:p-10 max-sm:p-7 border-r max-lg:border-r-0 max-lg:border-b border-border">
          <motion.div initial={{ opacity: 0, y: 28 }} animate={{ opacity: 1, y: 0 }}>
            <p className="font-mono text-micro tracking-[0.3em] uppercase text-muted-foreground font-medium mb-6">Resultado · {record?.official_status || "Estado explícito"}</p>
            <h1 className="font-serif text-display-lg leading-[1.05] text-foreground mb-6">
              {exempt ? "El documento registra" : "El documento registra que"}<br />
              <span className="italic text-accent">{exempt ? record?.official_status || "una exoneración" : "no fuiste seleccionado/a."}</span>
            </h1>
            <OrnamentalRule className="text-foreground mb-6" />
            <p className="text-muted-foreground text-body leading-relaxed max-w-prose">
              Esta clasificación utiliza la terminología publicada en la evidencia. No se transforma automáticamente en otra condición jurídica.
            </p>
            <div className="mt-8"><ResultActions onExport={onExport} onCopy={onCopy} onAgain={onAgain} /></div>
          </motion.div>
        </div>
        <div className="flex flex-col justify-center p-16 max-lg:p-10 max-sm:p-7 bg-secondary/20">
          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} className="space-y-4">
            <p className="font-mono text-micro tracking-[0.2em] uppercase text-muted-foreground font-medium mb-5">Evidencia del resultado</p>
            {[record?.official_status && ["Estado oficial", record.official_status], ["Identificación", result.masked_id], record && ["Fuente", `${record.source_file} · página ${record.source_page}`], record && ["Confianza", `${record.confidence_label} · ${Math.round(record.confidence * 100)}%`]].filter(Boolean).map((item, index) => {
              const [label, value] = item as [string, string];
              return <motion.div key={label} initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 + index * 0.1 }} className="p-5 bg-card rounded-xl border border-border"><p className="text-micro uppercase tracking-widest text-muted-foreground mb-1">{label}</p><p className="text-sm font-semibold">{value}</p></motion.div>;
            })}
            <EvidenceDetails evidence={result.evidence} />
          </motion.div>
        </div>
      </div>
    </Shell>
  );
};

const NotFoundScreen = ({ result, onRetry, onRestart }: { result: SearchResultPayload; onRetry: () => void; onRestart: () => void }) => (
  <Shell>
    <ResultHeader round={result.allocation_round} label="Búsqueda terminada" />
    <div className="flex-1 flex flex-col items-center justify-center px-8 py-12">
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-reading">
        <div className="w-14 h-14 rounded-2xl bg-secondary border border-border flex items-center justify-center mb-8"><Search size={22} className="text-muted-foreground" /></div>
        <p className="font-mono text-micro tracking-[0.25em] uppercase text-muted-foreground font-medium mb-4">Resultado · {result.masked_id}</p>
        <h1 className="font-serif text-display-md text-foreground mb-4 leading-tight">No encontramos tu identificación en los documentos cargados</h1>
        <p className="text-muted-foreground text-body leading-relaxed mb-7">Esto no prueba una exoneración ni permite establecer por sí solo una situación legal.</p>
        <div className="bg-card border border-border rounded-xl p-6 mb-7">
          <p className="font-mono text-micro tracking-[0.2em] uppercase text-muted-foreground font-medium mb-4">Posibles causas</p>
          <ul className="space-y-3">{result.reasons.map((reason, index) => <li key={reason} className="flex items-start gap-3 text-small"><span className="w-5 h-5 rounded-full bg-secondary flex items-center justify-center text-micro text-muted-foreground font-bold flex-shrink-0">{index + 1}</span>{reason}</li>)}</ul>
        </div>
        <div className="flex max-sm:flex-col gap-3">
          <button onClick={onRetry} className="flex-1 bg-primary text-primary-foreground rounded-xl py-3.5 text-sm font-semibold">Corregir identificación</button>
          <button onClick={onRestart} className="flex items-center gap-2 bg-secondary rounded-xl px-5 py-3.5 text-sm font-semibold"><RotateCcw size={14} />Cambiar PDF</button>
        </div>
      </motion.div>
    </div>
  </Shell>
);

const AmbiguousScreen = ({ result, onRestart }: { result: SearchResultPayload; onRestart: () => void }) => (
  <Shell>
    <ResultHeader round={result.allocation_round} label="Verificación manual requerida" />
    <div className="flex-1 flex flex-col items-center justify-center px-8 py-10">
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} className="w-full max-w-content">
        <div className="w-14 h-14 rounded-2xl bg-accent/10 border border-accent/20 flex items-center justify-center mb-6"><Users size={22} className="text-accent" /></div>
        <p className="font-mono text-micro tracking-[0.25em] uppercase text-muted-foreground font-medium mb-4">Aclaración requerida</p>
        <h1 className="font-serif text-display-md text-foreground mb-4 leading-tight">Encontramos información que requiere verificación</h1>
        <div className="bg-accent/8 border border-accent/20 rounded-xl p-4 mb-5">{result.reasons.map((reason) => <p key={reason} className="text-xs text-muted-foreground mt-1">• {reason}</p>)}</div>
        <div className="space-y-2.5 max-h-[330px] overflow-auto pr-1">
          {result.evidence.map((record, index) => (
            <motion.div key={`${record.source_file}-${record.source_page}-${index}`} initial={{ opacity: 0, x: -16 }} animate={{ opacity: 1, x: 0 }} transition={{ delay: index * 0.1 }} className="bg-card border border-border rounded-xl p-5">
              <div className="flex items-start justify-between gap-4"><div className="min-w-0"><p className="text-sm font-semibold break-words">{record.full_name || record.official_status || `Evidencia ${index + 1}`}</p><p className="font-mono text-caption text-muted-foreground mt-1 break-words">{record.source_file} · página {record.source_page}</p>{record.institution && <p className="text-xs text-muted-foreground mt-1 break-words">{record.institution}</p>}</div><span className="text-micro bg-secondary px-2 py-1 rounded-md flex-shrink-0">{record.confidence_label}</span></div>
            </motion.div>
          ))}
        </div>
        <button onClick={onRestart} className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mt-6"><X size={13} />Cambiar documentos y empezar de nuevo</button>
      </motion.div>
    </div>
  </Shell>
);

const ErrorScreen = ({ message, onRestart }: { message: string; onRestart: () => void }) => (
  <Shell>
    <div className="min-h-screen flex items-center justify-center p-8">
      <div className="w-full max-w-reading bg-card border border-border rounded-2xl p-8">
        <div className="w-12 h-12 bg-destructive/10 text-destructive rounded-xl flex items-center justify-center mb-6"><AlertCircle /></div>
        <h1 className="font-serif text-display-md mb-4">No fue posible completar la consulta</h1>
        <p className="text-sm text-muted-foreground leading-relaxed">{message}</p>
        <button onClick={onRestart} className="mt-7 flex items-center gap-2 bg-primary text-primary-foreground rounded-xl px-6 py-3.5 text-sm font-semibold"><RotateCcw size={14} />Volver a los documentos</button>
      </div>
    </div>
  </Shell>
);

export default function App() {
  const [screen, setScreen] = useState<Screen>("welcome");
  const [backend, setBackend] = useState<BackendApi | null>(null);
  const [backendState, setBackendState] = useState<BackendState>(EMPTY_STATE);
  const [connectionError, setConnectionError] = useState("");
  const [validation, setValidation] = useState<ValidationPayload | null>(null);
  const [documentBatchBusy, setDocumentBatchBusy] = useState(false);
  const [documentBatchMessage, setDocumentBatchMessage] = useState("");
  const [stageQueue, setStageQueue] = useState<ProcessingStage[]>([]);
  const [result, setResult] = useState<SearchResultPayload | null>(null);
  const [resultReady, setResultReady] = useState(false);
  const [processingError, setProcessingError] = useState("");
  const [toast, setToast] = useState("");

  useEffect(() => {
    connectBackend({
      onState: setBackendState,
      onDocument: (slot, document) => setBackendState((state) => {
        const documents = [...state.documents];
        documents[slot] = document;
        return { ...state, documents };
      }),
      onDocumentBatchState: (busy, message) => {
        setDocumentBatchBusy(busy);
        setDocumentBatchMessage(message);
        if (busy) setValidation(null);
      },
      onValidation: (payload) => {
        setValidation(payload);
        if (payload.valid) setScreen("identification");
      },
      onStage: (stage) => setStageQueue((queue) => queue.includes(stage) ? queue : [...queue, stage]),
      onResult: (payload) => {
        setResult(payload);
        setResultReady(true);
      },
      onFailure: (message) => {
        setProcessingError(message);
        setResultReady(true);
        setScreen("result-error");
      },
      onExport: (message) => {
        setToast(message);
        window.setTimeout(() => setToast(""), 3000);
      },
    }).then(setBackend).catch((error: Error) => setConnectionError(error.message));
  }, []);

  const allocationRound = backendState.allocation_round;
  const startSearch = (input: DoctorInput) => {
    if (!backend) return;
    setStageQueue(["VALIDATING_DOCUMENTS"]);
    setResult(null);
    setResultReady(false);
    setProcessingError("");
    setScreen("preparation");
    sendDesktopCommand({ name: "searchDoctor", args: ["", input.idNumber, ""] });
  };

  const revealResult = useCallback(() => {
    if (!result) return;
    const destination: Record<SearchResultPayload["result_type"], Screen> = {
      ASSIGNED: "result-assigned",
      EXEMPT: "result-exempt",
      NOT_SELECTED: "result-not-selected",
      NOT_FOUND: "result-not-found",
      AMBIGUOUS: "result-ambiguous",
      ERROR: "result-error",
    };
    setScreen(destination[result.result_type]);
    sendDesktopCommand({ name: "notifyReveal", args: [] });
  }, [result]);

  const reset = () => {
    sendDesktopCommand({ name: "resetApplication", args: [] });
    setBackendState(EMPTY_STATE);
    setValidation(null);
    setDocumentBatchBusy(false);
    setDocumentBatchMessage("");
    setResult(null);
    setStageQueue([]);
    setScreen("welcome");
  };
  const again = () => {
    setResult(null);
    setScreen("identification");
  };
  const actions = useMemo(() => ({
    onExport: () => sendDesktopCommand({ name: "exportResult", args: [] }),
    onCopy: () => sendDesktopCommand({ name: "copyResult", args: [] }),
    onAgain: again,
  }), []);

  return (
    <MotionConfig reducedMotion={backendState.reduced_animation ? "always" : "user"}>
      <div className="w-full min-h-screen overflow-x-hidden">
        <style>{`::-webkit-scrollbar{width:8px}::-webkit-scrollbar-thumb{background:rgba(110,95,80,.22);border-radius:8px}`}</style>
        <AnimatePresence mode="wait">
          <motion.div key={screen} initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} transition={{ duration: backendState.reduced_animation ? 0 : 0.28 }} className="w-full">
          {screen === "welcome" && <WelcomeScreen onStart={() => setScreen("upload")} connected={Boolean(backend)} connectionError={connectionError} soundEnabled={backendState.sound_enabled} reducedAnimation={backendState.reduced_animation} onPreferences={(sound, reduced) => { setBackendState((state) => ({ ...state, sound_enabled: sound, reduced_animation: reduced })); sendDesktopCommand({ name: "updatePreferences", args: [sound, reduced] }); }} />}
          {screen === "upload" && <UploadScreen documents={backendState.documents} round={allocationRound} validation={validation} selecting={documentBatchBusy} selectionMessage={documentBatchMessage} onSelectAll={() => { setValidation(null); setDocumentBatchBusy(true); setDocumentBatchMessage("Preparando el selector seguro…"); sendDesktopCommand({ name: "selectPdfs", args: [] }); }} onClear={() => { setValidation(null); sendDesktopCommand({ name: "resetApplication", args: [] }); }} onValidate={(allow) => sendDesktopCommand({ name: "validateDocuments", args: [allow] })} onBack={() => setScreen("welcome")} />}
          {screen === "identification" && <IdentificationScreen round={allocationRound} onBack={() => setScreen("upload")} onNext={startSearch} />}
          {screen === "preparation" && <PreparationScreen stageQueue={stageQueue} resultReady={resultReady} onComplete={revealResult} reducedAnimation={backendState.reduced_animation} />}
          {screen === "result-assigned" && result && <AssignedScreen result={result} {...actions} reducedAnimation={backendState.reduced_animation} />}
          {screen === "result-exempt" && result && <StatusScreen result={result} exempt {...actions} />}
          {screen === "result-not-selected" && result && <StatusScreen result={result} exempt={false} {...actions} />}
          {screen === "result-not-found" && result && <NotFoundScreen result={result} onRetry={again} onRestart={() => setScreen("upload")} />}
          {screen === "result-ambiguous" && result && <AmbiguousScreen result={result} onRestart={() => setScreen("upload")} />}
          {screen === "result-error" && <ErrorScreen message={processingError || result?.reasons.join(" ") || "Error de procesamiento."} onRestart={() => setScreen("upload")} />}
          </motion.div>
        </AnimatePresence>
        <AnimatePresence>{toast && <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="fixed right-6 bottom-6 bg-foreground text-background rounded-xl px-5 py-3 text-sm shadow-xl z-50">{toast}</motion.div>}</AnimatePresence>
      </div>
    </MotionConfig>
  );
}
