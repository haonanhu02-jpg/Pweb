import type {
  Dashboard,
  Filters,
  OpportunityDetail,
  OpportunityListResponse,
  Review,
  ReviewStatus
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    ...init
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function getDashboard(): Promise<Dashboard> {
  return request<Dashboard>("/api/dashboard");
}

export function getOpportunities(filters: Filters): Promise<OpportunityListResponse> {
  const params = new URLSearchParams();
  params.set("min_level", filters.min_level);
  if (filters.opportunity_level) params.set("opportunity_level", filters.opportunity_level);
  if (filters.review_status) params.set("review_status", filters.review_status);
  if (filters.platform) params.set("platform", filters.platform);
  if (filters.procurement_stage) params.set("procurement_stage", filters.procurement_stage);
  if (filters.q.trim()) params.set("q", filters.q.trim());
  params.set("limit", "100");
  return request<OpportunityListResponse>(`/api/opportunities?${params.toString()}`);
}

export function getOpportunity(id: string): Promise<OpportunityDetail> {
  return request<OpportunityDetail>(`/api/opportunities/${id}`);
}

export function updateReview(id: string, review_status: ReviewStatus, review_note: string): Promise<Review> {
  return request<Review>(`/api/opportunities/${id}/review`, {
    method: "PATCH",
    body: JSON.stringify({ review_status, review_note })
  });
}

export function runSpringScreen(): Promise<{ screened_count: number; failed_count: number }> {
  return request<{ screened_count: number; failed_count: number }>("/api/screen/spring", {
    method: "POST"
  });
}
