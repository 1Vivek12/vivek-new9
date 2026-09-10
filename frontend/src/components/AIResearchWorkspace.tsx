import { useState, useEffect } from 'react';

interface Story {
  id: string;
  title: string;
  slug: string;
  summary: string | null;
  status: string;
}

interface ResearchBrief {
  what_happened: string;
  who_involved: string[];
  when_timeline: Array<{ timestamp_or_period: string; description: string }>;
  where_locations: string[];
  why_causes: string | null;
  confirmed_facts: string[];
  disputed_facts: string[];
  unknowns: string[];
  key_entities: string[];
  source_confidence: number;
  editorial_warnings: string[];
  suggested_angles: string[];
}

interface ResearchEvidence {
  id: string;
  publisher: string | null;
  title: string;
  canonical_url: string;
  evidence_snippet: string;
  normalized_claim_summary: string;
  source_reliability: number | null;
  confidence_score: number;
  rights_metadata: Record<string, unknown>;
  adversarial_instruction_flag: boolean;
}

interface ResearchClaim {
  id: string;
  claim_text: string;
  claim_type: string;
  confidence_score: number;
  status: string;
  verification_notes: string | null;
}

interface AIOutput {
  id: string;
  output_type: string;
  version_number: number;
  content: Record<string, unknown>;
  status: string;
  rejection_reason: string | null;
  created_at: string;
}

export const AIResearchWorkspace = () => {
  const [stories, setStories] = useState<Story[]>([]);
  const [selectedStoryId, setSelectedStoryId] = useState<string>('');
  const [loading, setLoading] = useState(false);
  const [researchJobId, setResearchJobId] = useState<string | null>(null);

  const [brief, setBrief] = useState<ResearchBrief | null>(null);
  const [evidenceList, setEvidenceList] = useState<ResearchEvidence[]>([]);
  const [claimsList, setClaimsList] = useState<ResearchClaim[]>([]);
  const [aiOutputs, setAiOutputs] = useState<AIOutput[]>([]);

  const [activeGenTab, setActiveGenTab] = useState<'plan' | 'headlines' | 'script' | 'seo' | 'visual'>('plan');
  const [rejectionModalOutputId, setRejectionModalOutputId] = useState<string | null>(null);
  const [rejectionReason, setRejectionReason] = useState('');
  const [editingOutputId, setEditingOutputId] = useState<string | null>(null);
  const [editedJson, setEditedJson] = useState('');

  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Headers for News 9 tenant
  const tenantHeaders = {
    'X-Tenant-ID': 'tenant-news9',
    'X-User-Role': 'EDITOR',
    'X-User-ID': 'user-news9-editor',
    'Content-Type': 'application/json',
  };

  const fetchStories = async () => {
    try {
      const res = await fetch('/api/v1/stories', { headers: tenantHeaders });
      if (res.ok) {
        const data = await res.json();
        setStories(data);
        if (data.length > 0 && !selectedStoryId) {
          setSelectedStoryId(data[0].id);
        }
      }
    } catch {
      // Offline fallback
    }
  };

  useEffect(() => {
    fetchStories();
  }, []);

  const loadStoryResearch = async (storyId: string) => {
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      // 1. Check existing research jobs
      const jobsRes = await fetch(`/api/v1/stories/${storyId}/research`, { headers: tenantHeaders });
      if (jobsRes.ok) {
        const jobs = await jobsRes.json();
        if (jobs.length > 0) {
          const latestJob = jobs[0];
          setResearchJobId(latestJob.id);

          // Fetch brief
          const briefRes = await fetch(`/api/v1/research/${latestJob.id}/brief`, { headers: tenantHeaders });
          if (briefRes.ok) setBrief(await briefRes.json());
          else setBrief(null);

          // Fetch evidence
          const evRes = await fetch(`/api/v1/research/${latestJob.id}/evidence`, { headers: tenantHeaders });
          if (evRes.ok) setEvidenceList(await evRes.json());

          // Fetch claims
          const clRes = await fetch(`/api/v1/research/${latestJob.id}/claims`, { headers: tenantHeaders });
          if (clRes.ok) setClaimsList(await clRes.json());
        } else {
          setResearchJobId(null);
          setBrief(null);
          setEvidenceList([]);
          setClaimsList([]);
        }
      }

      // 2. Fetch AI Outputs
      const outRes = await fetch(`/api/v1/stories/${storyId}/ai-outputs`, { headers: tenantHeaders });
      if (outRes.ok) {
        setAiOutputs(await outRes.json());
      }
    } catch (err) {
      setErrorMsg(`Failed loading research: ${err}`);
    }
  };

  useEffect(() => {
    if (selectedStoryId) {
      loadStoryResearch(selectedStoryId);
    }
  }, [selectedStoryId]);

  const handleTriggerResearch = async () => {
    if (!selectedStoryId) return;
    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`/api/v1/stories/${selectedStoryId}/research`, {
        method: 'POST',
        headers: tenantHeaders,
        body: JSON.stringify({}),
      });
      if (res.ok) {
        setSuccessMsg('Research synthesis completed successfully.');
        await loadStoryResearch(selectedStoryId);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Research job failed');
      }
    } catch (e) {
      setErrorMsg(`Error triggering research: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (endpoint: string, bodyPayload: Record<string, unknown> = {}) => {
    if (!selectedStoryId) return;
    setLoading(true);
    setErrorMsg(null);
    setSuccessMsg(null);
    try {
      const res = await fetch(`/api/v1/stories/${selectedStoryId}/${endpoint}`, {
        method: 'POST',
        headers: tenantHeaders,
        body: JSON.stringify(bodyPayload),
      });
      if (res.ok) {
        setSuccessMsg(`AI Output generated for review.`);
        await loadStoryResearch(selectedStoryId);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Generation failed');
      }
    } catch (e) {
      setErrorMsg(`Error generating output: ${e}`);
    } finally {
      setLoading(false);
    }
  };

  const handleAccept = async (outputId: string) => {
    try {
      const res = await fetch(`/api/v1/ai-outputs/${outputId}/accept`, {
        method: 'POST',
        headers: tenantHeaders,
      });
      if (res.ok) {
        setSuccessMsg('AI Output accepted by human editor.');
        await loadStoryResearch(selectedStoryId);
      }
    } catch (e) {
      setErrorMsg(`Failed accepting output: ${e}`);
    }
  };

  const handleRejectSubmit = async () => {
    if (!rejectionModalOutputId || !rejectionReason.trim()) return;
    try {
      const res = await fetch(`/api/v1/ai-outputs/${rejectionModalOutputId}/reject`, {
        method: 'POST',
        headers: tenantHeaders,
        body: JSON.stringify({ action: 'REJECT', rejection_reason: rejectionReason }),
      });
      if (res.ok) {
        setSuccessMsg('AI Output rejected with recorded reason.');
        setRejectionModalOutputId(null);
        setRejectionReason('');
        await loadStoryResearch(selectedStoryId);
      } else {
        const err = await res.json();
        setErrorMsg(err.detail || 'Rejection failed');
      }
    } catch (e) {
      setErrorMsg(`Failed rejecting output: ${e}`);
    }
  };

  const handleEditSave = async (outputId: string) => {
    try {
      const parsed = JSON.parse(editedJson);
      const res = await fetch(`/api/v1/ai-outputs/${outputId}/edit`, {
        method: 'POST',
        headers: tenantHeaders,
        body: JSON.stringify({ content: parsed }),
      });
      if (res.ok) {
        setSuccessMsg('AI Output edited and updated.');
        setEditingOutputId(null);
        await loadStoryResearch(selectedStoryId);
      }
    } catch (e) {
      setErrorMsg(`Invalid JSON or update error: ${e}`);
    }
  };

  const filteredOutputs = aiOutputs.filter((o) => {
    if (activeGenTab === 'plan') return o.output_type === 'CONTENT_PLAN';
    if (activeGenTab === 'headlines') return o.output_type === 'HEADLINE';
    if (activeGenTab === 'script') return o.output_type === 'SCRIPT';
    if (activeGenTab === 'seo') return o.output_type === 'SEO';
    if (activeGenTab === 'visual') return o.output_type === 'VISUAL_PLAN';
    return true;
  });

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Top Banner: Security & Editorial Gate Invariants */}
      <div
        style={{
          backgroundColor: 'rgba(239, 68, 68, 0.08)',
          border: '1px solid rgba(239, 68, 68, 0.3)',
          borderRadius: '8px',
          padding: '1rem 1.25rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
        }}
      >
        <div>
          <span style={{ fontWeight: 700, color: 'var(--accent-red)' }}>
            🛡️ Phase 4 AI Research &amp; Content Intelligence Guard
          </span>
          <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
            All source material is quarantined as untrusted passive data inside explicit XML boundaries with zero tool permissions.
            Capped evidence excerpts (max 750 chars) prevent full copyrighted article storage. All AI outputs require human editorial review.
          </p>
        </div>
        <span className="badge badge-green">Inference Sandboxed</span>
      </div>

      {errorMsg && (
        <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', color: '#fca5a5', padding: '0.75rem', borderRadius: '6px' }}>
          {errorMsg}
        </div>
      )}
      {successMsg && (
        <div style={{ backgroundColor: 'rgba(34, 197, 94, 0.15)', color: '#86efac', padding: '0.75rem', borderRadius: '6px' }}>
          {successMsg}
        </div>
      )}

      {/* Story Selector & Action Bar */}
      <div className="card" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '1rem', flexWrap: 'wrap' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem', flex: 1, minWidth: '300px' }}>
          <label style={{ fontWeight: 600, fontSize: '0.9rem' }}>Editorial Story:</label>
          <select
            value={selectedStoryId}
            onChange={(e) => setSelectedStoryId(e.target.value)}
            style={{
              flex: 1,
              padding: '0.5rem',
              backgroundColor: 'var(--bg-card)',
              color: 'var(--text-primary)',
              border: '1px solid var(--border-subtle)',
              borderRadius: '6px',
            }}
          >
            {stories.length === 0 && <option value="">No stories available</option>}
            {stories.map((s) => (
              <option key={s.id} value={s.id}>
                [{s.status}] {s.title}
              </option>
            ))}
          </select>
        </div>

        <button
          onClick={handleTriggerResearch}
          disabled={loading || !selectedStoryId}
          style={{
            backgroundColor: 'var(--accent-red)',
            color: '#fff',
            border: 'none',
            padding: '0.6rem 1.25rem',
            borderRadius: '6px',
            fontWeight: 600,
            cursor: loading ? 'not-allowed' : 'pointer',
          }}
        >
          {loading ? 'Synthesizing Evidence...' : '⚡ Run AI Research & Fact Synthesis'}
        </button>
      </div>

      {/* 5W1H Structured Research Brief */}
      {brief ? (
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem' }}>
            <h2 style={{ fontSize: '1.15rem', margin: 0 }}>📋 5W1H Journalistic Research Brief</h2>
            <div style={{ display: 'flex', gap: '0.5rem' }}>
              {researchJobId && <span className="badge">Job: {researchJobId.slice(0, 8)}</span>}
              <span className="badge badge-blue">Confidence: {(brief.source_confidence * 100).toFixed(0)}%</span>
              <span className="badge badge-green">Facts Confirmed: {brief.confirmed_facts.length}</span>
            </div>
          </div>


          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem', marginBottom: '1rem' }}>
            <div style={{ padding: '0.75rem', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>What Happened</span>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.9rem', lineHeight: '1.5' }}>{brief.what_happened}</p>
            </div>
            <div style={{ padding: '0.75rem', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>Who Involved</span>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.9rem' }}>{brief.who_involved.join(', ') || 'Under investigation'}</p>
            </div>
            <div style={{ padding: '0.75rem', backgroundColor: 'rgba(255,255,255,0.02)', borderRadius: '6px' }}>
              <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', textTransform: 'uppercase', fontWeight: 700 }}>Where Locations</span>
              <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.9rem' }}>{brief.where_locations.join(', ') || 'Not specified'}</p>
            </div>
          </div>

          {/* Confirmed vs Disputed vs Unknowns */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1rem' }}>
            <div style={{ borderLeft: '3px solid #22c55e', paddingLeft: '0.75rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#86efac' }}>Confirmed Facts</span>
              <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {brief.confirmed_facts.map((f, i) => (
                  <li key={i}>{f}</li>
                ))}
              </ul>
            </div>
            <div style={{ borderLeft: '3px solid #f59e0b', paddingLeft: '0.75rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#fde047' }}>Disputed / Conflicting</span>
              <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {brief.disputed_facts.length === 0 && <li>No conflicting reports recorded</li>}
                {brief.disputed_facts.map((d, i) => (
                  <li key={i}>{d}</li>
                ))}
              </ul>
            </div>
            <div style={{ borderLeft: '3px solid #38bdf8', paddingLeft: '0.75rem' }}>
              <span style={{ fontWeight: 600, fontSize: '0.85rem', color: '#7dd3fc' }}>Unknowns &amp; Pending Verification</span>
              <ul style={{ margin: '0.25rem 0 0 0', paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-secondary)' }}>
                {brief.unknowns.map((u, i) => (
                  <li key={i}>{u}</li>
                ))}
              </ul>
            </div>
          </div>
        </div>
      ) : (
        <div className="card" style={{ textAlign: 'center', padding: '2rem', color: 'var(--text-secondary)' }}>
          No research brief synthesized for this story yet. Click &quot;Run AI Research &amp; Fact Synthesis&quot; to begin.
        </div>
      )}

      {/* Bounded Evidence & Claims Matrix */}
      <div className="grid">
        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '1rem', margin: 0 }}>📑 Bounded Source Evidence ({evidenceList.length})</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Snippet capped: &le;750 chars</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
            {evidenceList.length === 0 && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No evidence items collected.</p>
            )}
            {evidenceList.map((ev) => (
              <div key={ev.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{ev.publisher || 'Unknown Wire'}</span>
                  <div style={{ display: 'flex', gap: '0.35rem' }}>
                    {ev.adversarial_instruction_flag && (
                      <span className="badge" style={{ backgroundColor: '#7f1d1d', color: '#fca5a5' }}>Adversarial Pattern Flagged</span>
                    )}
                    <span className="badge badge-blue">Quote Limit Enforced</span>
                  </div>
                </div>
                <a href={ev.canonical_url} target="_blank" rel="noopener noreferrer" style={{ fontSize: '0.8rem', color: '#38bdf8', textDecoration: 'none' }}>
                  {ev.title}
                </a>
                <p style={{ margin: '0.35rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)', fontStyle: 'italic' }}>
                  &ldquo;{ev.evidence_snippet}&rdquo;
                </p>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem' }}>
            <h3 style={{ fontSize: '1rem', margin: 0 }}>🔍 Extracted Claims Matrix ({claimsList.length})</h3>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>Fact Verification</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', maxHeight: '350px', overflowY: 'auto' }}>
            {claimsList.length === 0 && (
              <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No claims extracted.</p>
            )}
            {claimsList.map((c) => (
              <div key={c.id} style={{ border: '1px solid var(--border-subtle)', borderRadius: '6px', padding: '0.6rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                  <span style={{ fontWeight: 600, fontSize: '0.85rem' }}>{c.claim_type}</span>
                  <span
                    className="badge"
                    style={{
                      backgroundColor:
                        c.status === 'SUPPORTED'
                          ? '#14532d'
                          : c.status === 'CONFLICTING'
                          ? '#78350f'
                          : '#1e293b',
                      color:
                        c.status === 'SUPPORTED'
                          ? '#86efac'
                          : c.status === 'CONFLICTING'
                          ? '#fde047'
                          : '#94a3b8',
                    }}
                  >
                    {c.status}
                  </span>
                </div>
                <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.85rem' }}>{c.claim_text}</p>
                {c.verification_notes && (
                  <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                    Notes: {c.verification_notes}
                  </p>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* AI Content Generation Modules */}
      <div className="card">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1rem', flexWrap: 'wrap', gap: '0.5rem' }}>
          <div>
            <h2 style={{ fontSize: '1.15rem', margin: 0 }}>✍️ AI Advisory Generation &amp; Human Editorial Gate</h2>
            <p style={{ margin: '0.25rem 0 0 0', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              Outputs remain in GENERATED / REVIEW_REQUIRED until approved by an Editor.
            </p>
          </div>

          <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
            <button
              onClick={() => handleGenerate('content-plan')}
              disabled={loading}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              + Generate Content Plan
            </button>
            <button
              onClick={() => handleGenerate('headlines')}
              disabled={loading}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              + Generate Headlines
            </button>
            <button
              onClick={() => handleGenerate('script')}
              disabled={loading}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              + Generate Script
            </button>
            <button
              onClick={() => handleGenerate('seo')}
              disabled={loading}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              + Generate SEO
            </button>
            <button
              onClick={() => handleGenerate('visual-plan')}
              disabled={loading}
              style={{ padding: '0.4rem 0.8rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', background: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '0.8rem' }}
            >
              + Generate Visual Plan
            </button>
          </div>
        </div>

        {/* Tab Selection */}
        <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem', marginBottom: '1rem' }}>
          {(['plan', 'headlines', 'script', 'seo', 'visual'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveGenTab(tab)}
              style={{
                background: 'none',
                border: 'none',
                color: activeGenTab === tab ? 'var(--text-primary)' : 'var(--text-secondary)',
                fontWeight: activeGenTab === tab ? 700 : 500,
                borderBottom: activeGenTab === tab ? '2px solid var(--accent-red)' : 'none',
                paddingBottom: '0.4rem',
                cursor: 'pointer',
                fontSize: '0.9rem',
                textTransform: 'capitalize',
              }}
            >
              {tab === 'plan' ? 'Content Plan' : tab === 'headlines' ? 'Headlines' : tab === 'script' ? 'News Script' : tab === 'seo' ? 'SEO Metadata' : 'Visual Plan'}
            </button>
          ))}
        </div>

        {/* Output List & Review Controls */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          {filteredOutputs.length === 0 && (
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>
              No outputs generated for this tab yet. Click the buttons above to request generation.
            </p>
          )}

          {filteredOutputs.map((out) => (
            <div
              key={out.id}
              style={{
                border: '1px solid var(--border-subtle)',
                borderRadius: '8px',
                padding: '1rem',
                backgroundColor: 'rgba(255, 255, 255, 0.01)',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.75rem', flexWrap: 'wrap', gap: '0.5rem' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                  <span style={{ fontWeight: 700, fontSize: '0.95rem' }}>
                    {out.output_type} &middot; Version {out.version_number}
                  </span>
                  <span
                    className="badge"
                    style={{
                      backgroundColor:
                        out.status === 'ACCEPTED'
                          ? '#14532d'
                          : out.status === 'REJECTED'
                          ? '#7f1d1d'
                          : out.status === 'EDITED'
                          ? '#1e3a8a'
                          : '#78350f',
                      color:
                        out.status === 'ACCEPTED'
                          ? '#86efac'
                          : out.status === 'REJECTED'
                          ? '#fca5a5'
                          : out.status === 'EDITED'
                          ? '#93c5fd'
                          : '#fde047',
                    }}
                  >
                    {out.status}
                  </span>
                </div>

                {/* Human Review Gate Actions */}
                <div style={{ display: 'flex', gap: '0.5rem' }}>
                  {out.status !== 'ACCEPTED' && (
                    <button
                      onClick={() => handleAccept(out.id)}
                      style={{
                        backgroundColor: '#16a34a',
                        color: '#fff',
                        border: 'none',
                        padding: '0.35rem 0.75rem',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      ✓ Accept
                    </button>
                  )}
                  {out.status !== 'REJECTED' && (
                    <button
                      onClick={() => {
                        setRejectionModalOutputId(out.id);
                        setRejectionReason('');
                      }}
                      style={{
                        backgroundColor: '#dc2626',
                        color: '#fff',
                        border: 'none',
                        padding: '0.35rem 0.75rem',
                        borderRadius: '4px',
                        fontSize: '0.8rem',
                        fontWeight: 600,
                        cursor: 'pointer',
                      }}
                    >
                      ✗ Reject
                    </button>
                  )}
                  <button
                    onClick={() => {
                      setEditingOutputId(out.id);
                      setEditedJson(JSON.stringify(out.content, null, 2));
                    }}
                    style={{
                      backgroundColor: '#3b82f6',
                      color: '#fff',
                      border: 'none',
                      padding: '0.35rem 0.75rem',
                      borderRadius: '4px',
                      fontSize: '0.8rem',
                      fontWeight: 600,
                      cursor: 'pointer',
                    }}
                  >
                    ✎ Edit
                  </button>
                </div>
              </div>

              {out.rejection_reason && (
                <div style={{ backgroundColor: 'rgba(239, 68, 68, 0.1)', color: '#fca5a5', padding: '0.5rem', borderRadius: '4px', marginBottom: '0.5rem', fontSize: '0.85rem' }}>
                  <strong>Rejection Reason:</strong> {out.rejection_reason}
                </div>
              )}

              {editingOutputId === out.id ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                  <textarea
                    value={editedJson}
                    onChange={(e) => setEditedJson(e.target.value)}
                    rows={12}
                    style={{
                      width: '100%',
                      fontFamily: 'monospace',
                      fontSize: '0.85rem',
                      padding: '0.5rem',
                      backgroundColor: 'var(--bg-card)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '4px',
                    }}
                  />
                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    <button
                      onClick={() => handleEditSave(out.id)}
                      style={{ backgroundColor: '#22c55e', color: '#fff', border: 'none', padding: '0.35rem 0.75rem', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem' }}
                    >
                      Save Revision
                    </button>
                    <button
                      onClick={() => setEditingOutputId(null)}
                      style={{ background: 'none', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)', padding: '0.35rem 0.75rem', borderRadius: '4px', cursor: 'pointer', fontSize: '0.85rem' }}
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : (
                <pre
                  style={{
                    backgroundColor: 'rgba(0,0,0,0.2)',
                    padding: '0.75rem',
                    borderRadius: '4px',
                    fontSize: '0.85rem',
                    overflowX: 'auto',
                    whiteSpace: 'pre-wrap',
                    color: 'var(--text-primary)',
                    margin: 0,
                  }}
                >
                  {JSON.stringify(out.content, null, 2)}
                </pre>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Mandatory Rejection Reason Modal */}
      {rejectionModalOutputId && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            backgroundColor: 'rgba(0, 0, 0, 0.75)',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            zIndex: 1000,
          }}
        >
          <div className="card" style={{ width: '450px', maxWidth: '90%' }}>
            <h3 style={{ margin: '0 0 0.5rem 0' }}>Mandatory Editorial Rejection Reason</h3>
            <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: '0 0 1rem 0' }}>
              All rejections of AI-generated content must record an explicit reason for newsroom accountability and audit tracking.
            </p>
            <textarea
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              placeholder="e.g. Fails attribution standard; tone is overly sensationalist; inaccurate timeline..."
              rows={4}
              style={{
                width: '100%',
                padding: '0.5rem',
                backgroundColor: 'var(--bg-card)',
                color: 'var(--text-primary)',
                border: '1px solid var(--border-subtle)',
                borderRadius: '6px',
                marginBottom: '1rem',
                fontSize: '0.85rem',
              }}
            />
            <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '0.5rem' }}>
              <button
                onClick={() => setRejectionModalOutputId(null)}
                style={{ background: 'none', border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)', padding: '0.4rem 0.8rem', borderRadius: '4px', cursor: 'pointer' }}
              >
                Cancel
              </button>
              <button
                onClick={handleRejectSubmit}
                disabled={!rejectionReason.trim()}
                style={{
                  backgroundColor: '#dc2626',
                  color: '#fff',
                  border: 'none',
                  padding: '0.4rem 0.8rem',
                  borderRadius: '4px',
                  cursor: rejectionReason.trim() ? 'pointer' : 'not-allowed',
                  fontWeight: 600,
                }}
              >
                Confirm Rejection
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
