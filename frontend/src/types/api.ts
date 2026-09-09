/** Shared API types aligned with backend schemas */
export interface DashboardOverview {
  counters: {
    persons: number;
    high_risk: number;
    admin_cases: number;
    preventive: number;
    suspects: number;
    should_be_registered: number;
    repeat_on_register: number;
    escalation_during_register: number;
  };
  district_risk: { district: string; total: number; high: number; critical: number }[];
  top_persons: { id: number; fio: string; district: string | null; risk_score: number; risk_level: string }[];
  signals: { type: string; level: string; count: number }[];
  articles: { article: string; count: number }[];
}

export interface TimeseriesPoint {
  month: string;
  count: number;
}

export interface DistrictBreakdown {
  by_district: { district: string; count: number }[];
}

export interface OrganBreakdown {
  breakdown: {
    series: { name: string; data: number[] }[];
    labels: string[];
  };
}

export interface ProceedingsData {
  cases: {
    id: number;
    material_no: string | null;
    district: string | null;
    qualification: string | null;
    decision: string | null;
    measure: string | null;
  }[];
}

export interface PersonDetail {
  id: number;
  fio: string;
  iin_masked: string;
  birth_date: string | null;
  gender: string | null;
  district: string | null;
  locality: string | null;
  risk_score: number;
  risk_level: string;
  factors: { factor: string; points: number }[];
  signals: { type: string; level: string; message: string }[];
  admin_cases: AdminCase[];
  preventive_records: PreventiveRecord[];
  suspects: Suspect[];
  timeline: TimelineEvent[];
}

export interface AdminCase {
  id: number;
  material_no: string | null;
  case_date: string | null;
  district: string | null;
  qualification: string | null;
  fabula: string | null;
  decision: string | null;
  measure: string | null;
  intoxication: string | null;
  source: string;
}

export interface PreventiveRecord {
  id: number;
  form: string | null;
  category: string | null;
  status: string | null;
  date_post: string | null;
  date_removed: string | null;
  district: string | null;
  has_special_req: boolean;
}

export interface Suspect {
  id: number;
  erdr_no: string | null;
  erdr_year: number | null;
  qualification: string | null;
  gravity: string | null;
  region: string | null;
}

export interface TimelineEvent {
  date: string | null;
  type: string;
  title: string;
  detail: string | null;
}

export interface Measure {
  type: string;
  title: string;
  reason: string;
  applicable: boolean;
  legal_basis: string[];
}

export interface DataQualityReport {
  persons: { total: number; missing_iin: number; missing_iin_pct: number; missing_district: number };
  admin_cases: {
    total: number;
    missing_date: number;
    missing_date_pct: number;
    missing_qualification: number;
    missing_decision: number;
    missing_measure: number;
    imposed_without_measure: number;
  };
  preventive: { total: number; missing_date_post: number };
  suspects: { total: number; unlinked_to_person: number };
}

export interface AuditEvent {
  id: number;
  ts: string;
  username: string;
  action: string;
  entity_type: string | null;
  entity_id: number | null;
  ip: string | null;
  export_id: string | null;
  details: Record<string, unknown> | null;
}

export interface DlpExport {
  username: string;
  exports: number;
  threshold: number;
}

export interface AnalyticsRepeat {
  person_id: number;
  fio: string;
  district: string | null;
  cases: number;
  on_register: boolean;
  risk_level: string;
}

export interface AnalyticsEscalation {
  person_id: number;
  fio: string;
  district: string | null;
  date_post: string | null;
  erdr_no: string | null;
  qualification: string | null;
}

export interface AnalyticsArticle {
  article: string;
  count: number;
}

export interface DistrictDetail {
  district: string;
  counters: { total: number; high: number; critical: number };
  top_persons: { id: number; fio: string; risk_score: number; risk_level: string }[];
  articles: { article: string; count: number }[];
}

export interface IngestionLog {
  id: number;
  ts: string;
  file: string;
  total: number;
  accepted: number;
  rejected: number;
}

export interface UploadPreview {
  filename: string;
  columns: string[];
  suggested_map: Record<string, string>;
  preview_rows: Record<string, unknown>[];
}

export interface UploadResult {
  accepted: number;
  rejected: number;
  quality?: DataQualityReport;
}

export interface AiStatus {
  provider: string;
  model: string;
  available: boolean;
}

export interface ChartClickPayload {
  activePayload?: { payload: { district?: string } }[];
}

export interface MatchedNorm {
  norm_id: number;
  ref: string;
  act: string;
  article: string | null;
  point: string | null;
  status: string;
  source_url: string | null;
  similarity: number | null;
}

export interface LegalAssignmentCheck {
  text: string;
  responsible: string | null;
  deadline: string | null;
  execution_status: string | null;
  compliance: "ok" | "warning" | "violation";
  matched_norms: MatchedNorm[];
  issues: string[];
  recommendation: string;
}

export interface LegalComplianceAnalysis {
  assignments: LegalAssignmentCheck[];
  overall: string;
  compliance_score: number | null;
  violations_count: number;
  warnings?: string[];
}

export interface CommissionDocument {
  id: number;
  doc_type: string;
  title: string | null;
  district: string;
  period: string;
  session_date: string | null;
  original_filename: string;
  mime_type: string;
  uploaded_by: string | null;
  uploaded_at: string;
  status: string;
  error_message?: string | null;
  quality_score: number | null;
  legal_compliance_score: number | null;
  effectiveness_score: number | null;
  include_recommendation: string | null;
}

export interface CommissionDocumentDetail extends CommissionDocument {
  extracted_text: string | null;
  analysis_document: Record<string, unknown> | null;
  analysis_execution: Record<string, unknown> | null;
  analysis_legal: LegalComplianceAnalysis | null;
}

export interface CommissionSummary {
  district: string | null;
  total: number;
  analyzed: number;
  avg_quality: number | null;
  avg_effectiveness: number | null;
  include_yes: number;
  include_revise: number;
  include_no: number;
  documents: CommissionDocument[];
}

export interface LocalityProfile {
  settlement_type?: "city" | "village";
  admin_unit?: string;
  region?: string;
  population?: {
    total?: number;
    year?: number;
    internal_migrants_note?: string;
  };
  ethnic_composition?: { group: string; share_pct: number }[];
  economy?: { primary_activity?: string[] };
  highlights?: string[];
  sources?: { title: string; url?: string; as_of?: string }[];
}

export interface LegalTopicAct {
  doc_id: string;
  title: string;
  number: string;
  adilet_url: string;
  key_articles: string[];
  note?: string;
}

export interface LegalTopicBundle {
  title: string;
  acts: LegalTopicAct[];
}

export interface EntitlementItem {
  id: number;
  slug: string;
  title: string;
  category: string;
  beneficiary: string;
  condition_text: string;
  amount_note?: string | null;
  administering_body: string;
  legal_act: string;
  legal_article: string;
  adilet_url: string;
  prevention_relevance?: string | null;
}

export interface IcdCodeItem {
  code: string;
  title_ru: string;
  chapter?: string | null;
  prevention_note?: string | null;
}

export interface PersonIcdItem {
  code: string;
  title_ru: string;
  chapter?: string | null;
  source: string;
  note?: string | null;
  prevention_note?: string | null;
}

export interface PersonSupportPayload {
  person_id: number;
  icd_codes: PersonIcdItem[];
  entitlements: EntitlementItem[];
  gaps: string[];
  subordinate_acts: { title: string; adilet_url: string }[];
}

export interface LocalityOverview {
  id: string;
  name: string;
  district?: string;
  passport_status?: "full" | "profile_only";
  summary?: { population?: number; description?: string; district?: string };
  locality_profile?: LocalityProfile;
  data_quality?: { completeness?: number; as_of?: string; verified_by?: string };
}
