export type OpportunityLevel = "excluded" | "low" | "review" | "high";
export type ReviewStatus = "pending_review" | "relevant" | "invalid" | "viewed";

export interface CountItem {
  [key: string]: string | number | null;
  count: number;
}

export interface Dashboard {
  total_count: number;
  platform_count: number;
  latest_publish_time: string | null;
  latest_created_at: string | null;
  assessed_count: number;
  spring_demand_count: number;
  latest_assessed_at: string | null;
  pending_review_count: number;
  by_platform: Array<{ source_platform: string; count: number }>;
  by_level: Array<{ opportunity_level: OpportunityLevel; count: number }>;
  by_stage: Array<{ procurement_stage: string; count: number }>;
  by_review_status: Array<{ review_status: ReviewStatus; count: number }>;
}

export interface SpringAssessment {
  notice_id: string;
  is_procurement_notice?: boolean;
  procurement_stage: string;
  has_spring_demand: boolean;
  demand_type: string | null;
  procurement_subject: string | null;
  product_category: string | null;
  industry_category: string | null;
  opportunity_level: OpportunityLevel;
  relevance_score: number;
  matched_terms: string[];
  negative_terms: string[];
  evidence: string[];
  reason: string;
  assessed_at: string;
}

export interface Review {
  notice_id: string;
  review_status: ReviewStatus;
  review_note: string;
  reviewed_at: string | null;
}

export interface AttachmentDocument {
  notice_id: string;
  attachment_url: string;
  attachment_name: string;
  file_path: string | null;
  file_ext: string | null;
  status: "parsed" | "empty" | "unsupported" | "missing_tool" | "failed" | "skipped" | string;
  content_text: string;
  content_hash: string | null;
  error: string | null;
  fetched_at: string | null;
  parsed_at: string;
}

export interface OpportunitySummary {
  id: string;
  title: string;
  source_platform: string;
  notice_type: string | null;
  publish_time: string | null;
  region: string | null;
  buyer: string | null;
  platform_url: string;
  original_url: string | null;
  spring_demand_assessment: SpringAssessment;
  review: Review;
}

export interface OpportunityDetail extends OpportunitySummary {
  source_channel: string;
  agency: string | null;
  deadline: string | null;
  bid_open_time: string | null;
  industry: string | null;
  attachments: Array<{ name: string; url: string }>;
  attachment_documents: AttachmentDocument[];
  content_text: string;
  raw_fields: Record<string, unknown>;
  content_hash: string;
  fetched_at: string;
}

export interface OpportunityListResponse {
  total: number;
  limit: number;
  offset: number;
  items: OpportunitySummary[];
}

export interface Filters {
  min_level: OpportunityLevel;
  opportunity_level: "" | OpportunityLevel;
  review_status: "" | ReviewStatus;
  platform: string;
  procurement_stage: string;
  q: string;
}
