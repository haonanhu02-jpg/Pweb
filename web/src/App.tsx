import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  ExternalLink,
  Eye,
  Filter,
  RefreshCcw,
  Search,
  XCircle
} from "lucide-react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  getDashboard,
  getOpportunities,
  getOpportunity,
  runSpringScreen,
  updateReview
} from "./api";
import type {
  Dashboard,
  Filters,
  OpportunityDetail,
  OpportunityLevel,
  OpportunitySummary,
  ReviewStatus
} from "./types";

const levelLabels: Record<OpportunityLevel, string> = {
  high: "高价值",
  review: "待复核",
  low: "低相关",
  excluded: "已排除"
};

const reviewLabels: Record<ReviewStatus, string> = {
  pending_review: "待复核",
  relevant: "相关",
  invalid: "无效",
  viewed: "已查看"
};

const attachmentStatusLabels: Record<string, string> = {
  parsed: "已解析",
  empty: "无文本",
  unsupported: "不支持",
  missing_tool: "缺工具",
  failed: "失败",
  skipped: "已跳过"
};

const defaultFilters: Filters = {
  min_level: "review",
  opportunity_level: "",
  review_status: "",
  platform: "",
  procurement_stage: "",
  q: ""
};

function App() {
  const [dashboard, setDashboard] = useState<Dashboard | null>(null);
  const [filters, setFilters] = useState<Filters>(defaultFilters);
  const [items, setItems] = useState<OpportunitySummary[]>([]);
  const [total, setTotal] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [detail, setDetail] = useState<OpportunityDetail | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const platformOptions = useMemo(
    () => dashboard?.by_platform.map((item) => item.source_platform).filter(Boolean) || [],
    [dashboard]
  );
  const stageOptions = useMemo(
    () => dashboard?.by_stage.map((item) => item.procurement_stage).filter(Boolean) || [],
    [dashboard]
  );

  async function loadDashboard() {
    setDashboard(await getDashboard());
  }

  async function loadOpportunities(nextFilters = filters) {
    setLoading(true);
    setError(null);
    try {
      const response = await getOpportunities(nextFilters);
      setItems(response.items);
      setTotal(response.total);
      if (response.items.length > 0 && !response.items.some((item) => item.id === selectedId)) {
        setSelectedId(response.items[0].id);
      }
      if (response.items.length === 0) {
        setSelectedId(null);
        setDetail(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载商机失败");
    } finally {
      setLoading(false);
    }
  }

  async function refreshAll() {
    await Promise.all([loadDashboard(), loadOpportunities(filters)]);
  }

  useEffect(() => {
    refreshAll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadOpportunities(filters);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters.min_level, filters.opportunity_level, filters.review_status, filters.platform, filters.procurement_stage]);

  useEffect(() => {
    if (!selectedId) return;
    setDetailLoading(true);
    getOpportunity(selectedId)
      .then((payload) => {
        setDetail(payload);
        setReviewNote(payload.review.review_note || "");
      })
      .catch((err) => setError(err instanceof Error ? err.message : "加载详情失败"))
      .finally(() => setDetailLoading(false));
  }, [selectedId]);

  async function applySearch() {
    await loadOpportunities(filters);
  }

  async function handleScreen() {
    setLoading(true);
    try {
      await runSpringScreen();
      await refreshAll();
    } catch (err) {
      setError(err instanceof Error ? err.message : "重跑筛选失败");
    } finally {
      setLoading(false);
    }
  }

  async function handleReview(status: ReviewStatus) {
    if (!selectedId) return;
    const updated = await updateReview(selectedId, status, reviewNote);
    setDetail((current) => (current ? { ...current, review: updated } : current));
    setItems((current) => current.map((item) => (item.id === selectedId ? { ...item, review: updated } : item)));
    await loadDashboard();
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div>
          <h1>弹簧招标商机工作台</h1>
          <p>采集公告、识别弹簧需求、查看附件证据、人工复核</p>
        </div>
        <div className="topbar-actions">
          <button className="icon-button" onClick={refreshAll} title="刷新">
            <RefreshCcw size={18} />
          </button>
          <button className="primary-button" onClick={handleScreen}>
            <RefreshCcw size={16} />
            重跑筛选
          </button>
        </div>
      </header>

      <section className="metrics-grid">
        <Metric label="公告总数" value={dashboard?.total_count ?? 0} />
        <Metric label="已筛选" value={dashboard?.assessed_count ?? 0} />
        <Metric label="弹簧需求" value={dashboard?.spring_demand_count ?? 0} />
        <Metric label="待复核" value={dashboard?.pending_review_count ?? 0} />
        <Metric label="平台数" value={dashboard?.platform_count ?? 0} />
      </section>

      <main className="workspace">
        <aside className="filters-panel">
          <div className="panel-heading">
            <Filter size={18} />
            <span>筛选</span>
          </div>
          <label>
            最低等级
            <select value={filters.min_level} onChange={(event) => setFilters({ ...filters, min_level: event.target.value as OpportunityLevel })}>
              <option value="review">待复核及以上</option>
              <option value="high">仅高价值</option>
              <option value="low">低相关及以上</option>
              <option value="excluded">全部</option>
            </select>
          </label>
          <label>
            机会等级
            <select value={filters.opportunity_level} onChange={(event) => setFilters({ ...filters, opportunity_level: event.target.value as Filters["opportunity_level"] })}>
              <option value="">全部</option>
              <option value="high">高价值</option>
              <option value="review">待复核</option>
              <option value="low">低相关</option>
              <option value="excluded">已排除</option>
            </select>
          </label>
          <label>
            复核状态
            <select value={filters.review_status} onChange={(event) => setFilters({ ...filters, review_status: event.target.value as Filters["review_status"] })}>
              <option value="">全部</option>
              <option value="pending_review">待复核</option>
              <option value="relevant">相关</option>
              <option value="invalid">无效</option>
              <option value="viewed">已查看</option>
            </select>
          </label>
          <label>
            来源平台
            <select value={filters.platform} onChange={(event) => setFilters({ ...filters, platform: event.target.value })}>
              <option value="">全部</option>
              {platformOptions.map((platform) => (
                <option key={platform} value={platform}>{platform}</option>
              ))}
            </select>
          </label>
          <label>
            公告阶段
            <select value={filters.procurement_stage} onChange={(event) => setFilters({ ...filters, procurement_stage: event.target.value })}>
              <option value="">全部</option>
              {stageOptions.map((stage) => (
                <option key={stage} value={stage}>{stage}</option>
              ))}
            </select>
          </label>
          <label>
            关键词
            <div className="search-row">
              <input value={filters.q} onChange={(event) => setFilters({ ...filters, q: event.target.value })} onKeyDown={(event) => event.key === "Enter" && applySearch()} />
              <button className="icon-button" onClick={applySearch} title="搜索">
                <Search size={17} />
              </button>
            </div>
          </label>

          <div className="chart-block">
            <h2>等级分布</h2>
            <ResponsiveContainer width="100%" height={180}>
              <BarChart data={dashboard?.by_level || []}>
                <CartesianGrid vertical={false} stroke="#e5e7eb" />
                <XAxis dataKey="opportunity_level" tickFormatter={(value) => levelLabels[value as OpportunityLevel] || value} />
                <YAxis allowDecimals={false} />
                <Tooltip formatter={(value, _name, props) => [value, levelLabels[props.payload.opportunity_level as OpportunityLevel]]} />
                <Bar dataKey="count" fill="#2563eb" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </aside>

        <section className="table-panel">
          <div className="table-header">
            <div>
              <h2>商机列表</h2>
              <p>{loading ? "加载中" : `共 ${total} 条`}</p>
            </div>
          </div>
          {error && <div className="error-box">{error}</div>}
          {items.length === 0 ? (
            <div className="empty-state">
              <AlertCircle size={22} />
              <strong>当前筛选条件下没有商机</strong>
              <span>可以把最低等级切换为“全部”，检查已排除公告和规则命中原因。</span>
            </div>
          ) : (
            <table>
              <thead>
                <tr>
                  <th>等级</th>
                  <th>标题</th>
                  <th>平台</th>
                  <th>阶段</th>
                  <th>分数</th>
                  <th>复核</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className={item.id === selectedId ? "selected-row" : ""} onClick={() => setSelectedId(item.id)}>
                    <td><LevelBadge level={item.spring_demand_assessment.opportunity_level} /></td>
                    <td className="title-cell">
                      <strong>{item.title}</strong>
                      <span>{item.publish_time || "无发布时间"}</span>
                    </td>
                    <td>{item.source_platform}</td>
                    <td>{item.spring_demand_assessment.procurement_stage}</td>
                    <td>{item.spring_demand_assessment.relevance_score}</td>
                    <td><ReviewBadge status={item.review.review_status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>

        <aside className="detail-panel">
          {!selectedId ? (
            <div className="empty-detail">选择一条公告查看详情</div>
          ) : detailLoading || !detail ? (
            <div className="empty-detail">详情加载中</div>
          ) : (
            <DetailView detail={detail} reviewNote={reviewNote} setReviewNote={setReviewNote} onReview={handleReview} />
          )}
        </aside>
      </main>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="metric-card">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function LevelBadge({ level }: { level: OpportunityLevel }) {
  return <span className={`level-badge level-${level}`}>{levelLabels[level]}</span>;
}

function ReviewBadge({ status }: { status: ReviewStatus }) {
  return <span className={`review-badge review-${status}`}>{reviewLabels[status]}</span>;
}

function DetailView({
  detail,
  reviewNote,
  setReviewNote,
  onReview
}: {
  detail: OpportunityDetail;
  reviewNote: string;
  setReviewNote: (value: string) => void;
  onReview: (status: ReviewStatus) => Promise<void>;
}) {
  const assessment = detail.spring_demand_assessment;
  const attachmentDocuments = detail.attachment_documents || [];
  return (
    <div className="detail-content">
      <div className="detail-title">
        <LevelBadge level={assessment.opportunity_level} />
        <h2>{detail.title}</h2>
        <a href={detail.original_url || detail.platform_url} target="_blank" rel="noreferrer">
          <ExternalLink size={16} />
          原文
        </a>
      </div>

      <dl className="detail-grid">
        <div><dt>来源</dt><dd>{detail.source_platform}</dd></div>
        <div><dt>发布时间</dt><dd>{detail.publish_time || "-"}</dd></div>
        <div><dt>采购方</dt><dd>{detail.buyer || "-"}</dd></div>
        <div><dt>阶段</dt><dd>{assessment.procurement_stage}</dd></div>
        <div><dt>产品分类</dt><dd>{assessment.product_category || "-"}</dd></div>
        <div><dt>行业分类</dt><dd>{assessment.industry_category || "-"}</dd></div>
      </dl>

      <section className="detail-section">
        <h3>识别原因</h3>
        <p>{assessment.reason}</p>
        <div className="score-line">
          <span>相关分 {assessment.relevance_score}</span>
          <span>{assessment.demand_type || "未识别到直接需求"}</span>
        </div>
      </section>

      <section className="detail-section">
        <h3>证据</h3>
        <ul className="evidence-list">
          {assessment.evidence.map((item) => <li key={item}>{item}</li>)}
        </ul>
        <div className="tags-row">
          {assessment.matched_terms.map((term) => <span key={term}>{term}</span>)}
        </div>
      </section>

      <section className="detail-section">
        <h3>附件解析</h3>
        {attachmentDocuments.length === 0 ? (
          <p>暂无附件解析结果</p>
        ) : (
          <div className="attachment-list">
            {attachmentDocuments.map((doc) => (
              <div className="attachment-card" key={`${doc.notice_id}-${doc.attachment_url}`}>
                <div className="attachment-card-header">
                  <a href={doc.attachment_url} target="_blank" rel="noreferrer">{doc.attachment_name}</a>
                  <span className={`attachment-status attachment-${doc.status}`}>
                    {attachmentStatusLabels[doc.status] || doc.status}
                  </span>
                </div>
                {doc.error && <p className="attachment-error">{doc.error}</p>}
                {doc.content_text ? <pre>{doc.content_text.slice(0, 3000)}</pre> : null}
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="detail-section">
        <h3>人工复核</h3>
        <textarea value={reviewNote} onChange={(event) => setReviewNote(event.target.value)} placeholder="填写复核备注" />
        <div className="review-actions">
          <button onClick={() => onReview("relevant")}><CheckCircle2 size={16} />相关</button>
          <button onClick={() => onReview("invalid")}><XCircle size={16} />无效</button>
          <button onClick={() => onReview("viewed")}><Eye size={16} />已查看</button>
          <button onClick={() => onReview("pending_review")}>待复核</button>
        </div>
        <p className="review-current">当前状态：{reviewLabels[detail.review.review_status]}</p>
      </section>

      <section className="detail-section">
        <h3>公告正文</h3>
        <pre>{detail.content_text || "无正文"}</pre>
      </section>

      <section className="detail-section">
        <h3>结构化字段</h3>
        <pre>{JSON.stringify(detail.raw_fields, null, 2)}</pre>
      </section>
    </div>
  );
}

export default App;
