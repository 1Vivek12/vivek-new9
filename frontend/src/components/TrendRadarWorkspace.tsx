import React, { useState, useEffect } from 'react';

interface Source {
  id: string;
  name: string;
  source_type: string;
  feed_url?: string;
  publisher_name?: string;
  reliability_score?: number;
  trust_level: string;
  is_active: boolean;
  last_success_at?: string;
  last_failure_at?: string;
}

interface SourceItem {
  id: string;
  title: string;
  canonical_url: string;
  publisher?: string;
  published_at?: string;
  fetched_at: string;
  reliability_score?: number;
  rights_metadata: {
    rights_type?: string;
    reuse_permitted?: boolean;
  };
}

interface ContentOpportunity {
  id: string;
  topic: string;
  headline: string;
  summary: string;
  trend_score: number;
  confidence_score: number;
  source_count: number;
  publisher_count: number;
  urgency: 'LOW' | 'NORMAL' | 'HIGH' | 'URGENT';
  status: 'DISCOVERED' | 'REVIEW_REQUIRED' | 'ACCEPTED' | 'REJECTED' | 'CONVERTED_TO_STORY';
  risk_indicators: string[];
  score_explanation: {
    reasons?: string[];
    breakdown?: Record<string, number>;
    signal_type?: string;
  };
  converted_story_id?: string;
  related_items?: SourceItem[];
  created_at: string;
}

export const TrendRadarWorkspace: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [opportunities, setOpportunities] = useState<ContentOpportunity[]>([]);
  const [searchQuery, setSearchQuery] = useState('Uttar Pradesh Infrastructure');
  const [timeWindow, setTimeWindow] = useState(48);
  const [minReliability, setMinReliability] = useState(70);
  const [loading, setLoading] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [showAddSource, setShowAddSource] = useState(false);

  // New source form state
  const [newSourceName, setNewSourceName] = useState('');
  const [newSourceType, setNewSourceType] = useState('OFFICIAL');
  const [newSourceFeedUrl, setNewSourceFeedUrl] = useState('');
  const [newSourcePublisher, setNewSourcePublisher] = useState('');
  const [newSourceReliability, setNewSourceReliability] = useState(85);

  // Load initial data
  useEffect(() => {
    fetchSources();
    fetchOpportunities();
  }, []);

  const fetchSources = async () => {
    try {
      const res = await fetch('/api/v1/sources');
      if (res.ok) {
        const data = await res.json();
        setSources(data);
      } else {
        // Fallback default demonstration sources
        setSources([
          {
            id: 'src-1',
            name: 'UP Government Information & PR',
            source_type: 'GOVERNMENT',
            feed_url: 'https://information.up.gov.in/feed.xml',
            publisher_name: 'Information Dept',
            reliability_score: 95,
            trust_level: 'HIGH',
            is_active: true,
            last_success_at: new Date().toISOString(),
          },
          {
            id: 'src-2',
            name: 'State Wire Service',
            source_type: 'WIRE',
            feed_url: 'https://wire.state.gov.in/feed.xml',
            publisher_name: 'National Wire',
            reliability_score: 90,
            trust_level: 'HIGH',
            is_active: true,
            last_success_at: new Date().toISOString(),
          },
        ]);
      }
    } catch {
      // Mock fallback
      setSources([
        {
          id: 'src-1',
          name: 'UP Government Information & PR',
          source_type: 'GOVERNMENT',
          feed_url: 'https://information.up.gov.in/feed.xml',
          publisher_name: 'Information Dept',
          reliability_score: 95,
          trust_level: 'HIGH',
          is_active: true,
          last_success_at: new Date().toISOString(),
        },
      ]);
    }
  };

  const fetchOpportunities = async () => {
    try {
      const res = await fetch('/api/v1/opportunities');
      if (res.ok) {
        const data = await res.json();
        setOpportunities(data);
      }
    } catch {
      // Offline fallback
    }
  };

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;
    setLoading(true);
    setStatusMessage(null);

    try {
      const res = await fetch('/api/v1/trend/search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: searchQuery,
          time_window_hours: timeWindow,
          min_reliability: minReliability,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        setOpportunities(data.opportunities || []);
        setStatusMessage(`Found ${data.total_matching_items} items and ${data.opportunities.length} content opportunities.`);
      } else {
        setStatusMessage('Search completed (backend returned offline mock).');
      }
    } catch {
      setStatusMessage('Network search error. Displaying local workspace signals.');
    } finally {
      setLoading(false);
    }
  };

  const handleRefreshSource = async (sourceId: string) => {
    setStatusMessage(`Triggering safe ingestion for source ${sourceId}...`);
    try {
      const res = await fetch(`/api/v1/sources/${sourceId}/refresh`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setStatusMessage(`Ingested ${data.items_fetched} items (${data.new_items_stored} newly registered).`);
        fetchSources();
      } else {
        const err = await res.json();
        setStatusMessage(`Ingestion failed: ${err.detail || 'Error'}`);
      }
    } catch (e: any) {
      setStatusMessage(`Network error during refresh: ${e.message}`);
    }
  };

  const handleCreateSource = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newSourceName.trim()) return;

    try {
      const res = await fetch('/api/v1/sources', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: newSourceName,
          source_type: newSourceType,
          feed_url: newSourceFeedUrl || undefined,
          publisher_name: newSourcePublisher || undefined,
          reliability_score: newSourceReliability,
          trust_level: newSourceReliability >= 80 ? 'HIGH' : 'MEDIUM',
          rights_metadata: {
            rights_type: 'public_information',
            reuse_permitted: false,
          },
        }),
      });

      if (res.ok) {
        setStatusMessage('New information source registered successfully.');
        setShowAddSource(false);
        setNewSourceName('');
        setNewSourceFeedUrl('');
        fetchSources();
      } else {
        const err = await res.json();
        setStatusMessage(`Failed to register source: ${err.detail}`);
      }
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
    }
  };

  const handleAcceptOpportunity = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/opportunities/${id}/accept`, { method: 'POST' });
      if (res.ok) {
        setStatusMessage('Opportunity accepted by editorial review.');
        fetchOpportunities();
      }
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
    }
  };

  const handleRejectOpportunity = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/opportunities/${id}/reject`, { method: 'POST' });
      if (res.ok) {
        setStatusMessage('Opportunity rejected.');
        fetchOpportunities();
      }
    } catch (e: any) {
      setStatusMessage(`Error: ${e.message}`);
    }
  };

  const handleConvertToStory = async (id: string) => {
    try {
      const res = await fetch(`/api/v1/opportunities/${id}/convert-to-story`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ priority: 'NORMAL' }),
      });

      if (res.ok) {
        const story = await res.json();
        setStatusMessage(
          `Opportunity converted to Phase 2 Story "${story.title}" in status [${story.status}]. Sources preserved.`
        );
        fetchOpportunities();
      } else {
        const err = await res.json();
        setStatusMessage(`Conversion failed: ${err.detail}`);
      }
    } catch (e: any) {
      setStatusMessage(`Error converting: ${e.message}`);
    }
  };

  const getUrgencyBadge = (urgency: string) => {
    switch (urgency) {
      case 'URGENT':
        return <span className="badge" style={{ backgroundColor: 'rgba(229, 9, 20, 0.2)', color: '#ff6b6b', border: '1px solid var(--accent-red)' }}>URGENT</span>;
      case 'HIGH':
        return <span className="badge badge-amber">HIGH</span>;
      default:
        return <span className="badge badge-green">NORMAL</span>;
    }
  };

  return (
    <div>
      {/* Workspace Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.5rem' }}>
        <div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.25rem' }}>Trend Radar &amp; Source Monitoring</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
            Deterministic discovery, freshness monitoring, and source-verified content opportunities. Human review mandatory.
          </p>
        </div>
        <button
          onClick={() => setShowAddSource(!showAddSource)}
          style={{
            backgroundColor: 'var(--accent-blue)',
            color: '#fff',
            border: 'none',
            borderRadius: '6px',
            padding: '0.5rem 1rem',
            fontWeight: 600,
            cursor: 'pointer',
          }}
        >
          {showAddSource ? 'Close Source Form' : '+ Add Source Feed'}
        </button>
      </div>

      {statusMessage && (
        <div style={{ padding: '0.75rem 1rem', marginBottom: '1.5rem', borderRadius: '6px', backgroundColor: 'rgba(31, 111, 235, 0.15)', border: '1px solid var(--accent-blue)', color: 'var(--text-primary)', fontSize: '0.9rem' }}>
          {statusMessage}
        </div>
      )}

      {/* Add Source Drawer */}
      {showAddSource && (
        <div className="card" style={{ marginBottom: '1.5rem' }}>
          <h3>Register Approved Information Source</h3>
          <form onSubmit={handleCreateSource} style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '1rem', marginTop: '1rem' }}>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Source Name</label>
              <input
                type="text"
                value={newSourceName}
                onChange={(e) => setNewSourceName(e.target.value)}
                placeholder="e.g. PIB State Press Release"
                required
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Source Type</label>
              <select
                value={newSourceType}
                onChange={(e) => setNewSourceType(e.target.value)}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              >
                <option value="OFFICIAL">OFFICIAL</option>
                <option value="GOVERNMENT">GOVERNMENT</option>
                <option value="WIRE">WIRE</option>
                <option value="PUBLICATION">PUBLICATION</option>
                <option value="RSS">RSS</option>
                <option value="OTHER">OTHER</option>
              </select>
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Publisher Name</label>
              <input
                type="text"
                value={newSourcePublisher}
                onChange={(e) => setNewSourcePublisher(e.target.value)}
                placeholder="e.g. Press Information Bureau"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Feed URL (RSS/Atom)</label>
              <input
                type="url"
                value={newSourceFeedUrl}
                onChange={(e) => setNewSourceFeedUrl(e.target.value)}
                placeholder="https://example.com/rss.xml"
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              />
            </div>
            <div>
              <label style={{ display: 'block', fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>Reliability Rating (0-100)</label>
              <input
                type="number"
                min="0"
                max="100"
                value={newSourceReliability}
                onChange={(e) => setNewSourceReliability(Number(e.target.value))}
                style={{ width: '100%', padding: '0.5rem', borderRadius: '4px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              />
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                type="submit"
                style={{ backgroundColor: 'var(--accent-green)', color: '#fff', border: 'none', borderRadius: '6px', padding: '0.5rem 1.5rem', fontWeight: 600, cursor: 'pointer', height: '38px' }}
              >
                Save Source
              </button>
            </div>
          </form>
        </div>
      )}

      {/* Topic Search & Filters */}
      <div className="card" style={{ marginBottom: '2rem' }}>
        <form onSubmit={handleSearch}>
          <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
            <div style={{ flex: '1', minWidth: '280px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Topic Search Query
              </label>
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g. Gorakhpur Expressway, AI Policy, Agriculture"
                style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff', fontSize: '1rem' }}
              />
            </div>
            <div style={{ width: '150px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Time Window
              </label>
              <select
                value={timeWindow}
                onChange={(e) => setTimeWindow(Number(e.target.value))}
                style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              >
                <option value={12}>Last 12 Hours</option>
                <option value={24}>Last 24 Hours</option>
                <option value={48}>Last 48 Hours</option>
                <option value={168}>Last 7 Days</option>
              </select>
            </div>
            <div style={{ width: '150px' }}>
              <label style={{ display: 'block', fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '0.3rem' }}>
                Min Reliability
              </label>
              <select
                value={minReliability}
                onChange={(e) => setMinReliability(Number(e.target.value))}
                style={{ width: '100%', padding: '0.6rem 0.8rem', borderRadius: '6px', border: '1px solid var(--border-subtle)', backgroundColor: 'var(--bg-primary)', color: '#fff' }}
              >
                <option value={50}>50+ Any Source</option>
                <option value={70}>70+ Verified Sources</option>
                <option value={85}>85+ High Authority</option>
              </select>
            </div>
            <div style={{ display: 'flex', alignItems: 'flex-end' }}>
              <button
                type="submit"
                disabled={loading}
                style={{
                  backgroundColor: 'var(--accent-red)',
                  color: '#fff',
                  border: 'none',
                  borderRadius: '6px',
                  padding: '0.6rem 1.5rem',
                  fontWeight: 700,
                  cursor: loading ? 'not-allowed' : 'pointer',
                  minWidth: '120px',
                }}
              >
                {loading ? 'Analyzing...' : 'Scan Radar'}
              </button>
            </div>
          </div>
        </form>
      </div>

      {/* Main Workspace: 2-Column Layout */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 340px', gap: '2rem' }}>
        {/* Left Column: Trend Signals & Content Opportunities */}
        <div>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>📡 Content Opportunities &amp; Trend Signals</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>({opportunities.length})</span>
          </h3>

          {opportunities.length === 0 ? (
            <div className="card" style={{ textAlign: 'center', padding: '3rem 1.5rem', color: 'var(--text-secondary)' }}>
              <p style={{ fontSize: '1.1rem', marginBottom: '0.5rem' }}>No trend signals detected for this topic yet.</p>
              <p style={{ fontSize: '0.85rem' }}>Trigger source feed refreshes or enter a topic search above to scan configured feeds.</p>
            </div>
          ) : (
            opportunities.map((opp) => (
              <div key={opp.id} className="card" style={{ position: 'relative', borderLeft: opp.trend_score >= 75 ? '4px solid var(--accent-red)' : '4px solid var(--accent-blue)' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.75rem' }}>
                  <div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.4rem' }}>
                      <span className="badge" style={{ backgroundColor: 'rgba(31, 111, 235, 0.2)', color: '#58a6ff' }}>{opp.topic}</span>
                      {getUrgencyBadge(opp.urgency)}
                      <span className="badge" style={{ backgroundColor: 'rgba(139, 148, 158, 0.2)', color: '#8b949e' }}>{opp.status}</span>
                    </div>
                    <h4 style={{ fontSize: '1.15rem', fontWeight: 600, color: 'var(--text-primary)' }}>{opp.headline}</h4>
                  </div>

                  {/* Trend Score Gauge */}
                  <div style={{ textAlign: 'right', minWidth: '90px' }}>
                    <div style={{ fontSize: '1.6rem', fontWeight: 800, color: opp.trend_score >= 75 ? '#ff6b6b' : '#58a6ff' }}>
                      {opp.trend_score.toFixed(1)}
                    </div>
                    <div style={{ fontSize: '0.7rem', color: 'var(--text-secondary)', textTransform: 'uppercase' }}>
                      Trend Score
                    </div>
                  </div>
                </div>

                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '1rem', lineHeight: '1.5' }}>
                  {opp.summary}
                </p>

                {/* Explainable Score Reasons */}
                {opp.score_explanation?.reasons && opp.score_explanation.reasons.length > 0 && (
                  <div style={{ backgroundColor: 'var(--bg-primary)', borderRadius: '6px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
                    <div style={{ fontSize: '0.75rem', fontWeight: 700, color: 'var(--text-secondary)', textTransform: 'uppercase', marginBottom: '0.4rem' }}>
                      Score Explanation &amp; Signals
                    </div>
                    <ul style={{ paddingLeft: '1.2rem', fontSize: '0.85rem', color: 'var(--text-primary)', lineHeight: '1.6' }}>
                      {opp.score_explanation.reasons.map((reason, idx) => (
                        <li key={idx}>{reason}</li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Risk Indicators */}
                {opp.risk_indicators && opp.risk_indicators.length > 0 && (
                  <div style={{ marginBottom: '1rem' }}>
                    {opp.risk_indicators.map((risk, idx) => (
                      <span key={idx} style={{ display: 'inline-block', marginRight: '0.5rem', fontSize: '0.75rem', color: '#f2cc60', backgroundColor: 'rgba(210, 153, 34, 0.15)', padding: '0.2rem 0.5rem', borderRadius: '4px' }}>
                        ⚠️ {risk}
                      </span>
                    ))}
                  </div>
                )}

                {/* Metadata & Actions Boundary */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid var(--border-subtle)', paddingTop: '0.75rem' }}>
                  <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                    <span>{opp.source_count} items</span> &bull; <span>{opp.publisher_count} publishers</span> &bull; <span>Confidence: {(opp.confidence_score * 100).toFixed(0)}%</span>
                  </div>

                  <div style={{ display: 'flex', gap: '0.5rem' }}>
                    {opp.status !== 'ACCEPTED' && opp.status !== 'CONVERTED_TO_STORY' && (
                      <button
                        onClick={() => handleAcceptOpportunity(opp.id)}
                        style={{ backgroundColor: 'var(--accent-green)', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.4rem 0.8rem', fontSize: '0.85rem', fontWeight: 600, cursor: 'pointer' }}
                      >
                        Accept
                      </button>
                    )}
                    {opp.status !== 'REJECTED' && opp.status !== 'CONVERTED_TO_STORY' && (
                      <button
                        onClick={() => handleRejectOpportunity(opp.id)}
                        style={{ backgroundColor: 'transparent', color: 'var(--text-secondary)', border: '1px solid var(--border-subtle)', borderRadius: '4px', padding: '0.4rem 0.8rem', fontSize: '0.85rem', cursor: 'pointer' }}
                      >
                        Reject
                      </button>
                    )}
                    {opp.status !== 'CONVERTED_TO_STORY' ? (
                      <button
                        onClick={() => handleConvertToStory(opp.id)}
                        style={{ backgroundColor: 'var(--accent-blue)', color: '#fff', border: 'none', borderRadius: '4px', padding: '0.4rem 0.9rem', fontSize: '0.85rem', fontWeight: 700, cursor: 'pointer' }}
                      >
                        Convert to Phase 2 Story
                      </button>
                    ) : (
                      <span className="badge badge-green">Converted to Story</span>
                    )}
                  </div>
                </div>
              </div>
            ))
          )}
        </div>

        {/* Right Column: Source Registry & Status */}
        <div>
          <h3 style={{ fontSize: '1.2rem', marginBottom: '1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <span>🏛️ Source Registry</span>
            <span style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>({sources.length})</span>
          </h3>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {sources.map((src) => (
              <div key={src.id} className="card" style={{ padding: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '0.4rem' }}>
                  <h5 style={{ fontSize: '0.95rem', fontWeight: 600 }}>{src.name}</h5>
                  <span className="badge" style={{ backgroundColor: 'rgba(35, 134, 54, 0.15)', color: '#3fb950', fontSize: '0.7rem' }}>
                    {src.trust_level}
                  </span>
                </div>
                <div style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginBottom: '0.5rem' }}>
                  Type: <strong>{src.source_type}</strong> &bull; Score: <strong>{src.reliability_score || 70}</strong>
                </div>
                {src.feed_url && (
                  <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', marginBottom: '0.75rem' }}>
                    {src.feed_url}
                  </div>
                )}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: '0.75rem', color: src.is_active ? '#3fb950' : '#8b949e' }}>
                    {src.is_active ? '● Active' : '○ Disabled'}
                  </span>
                  <button
                    onClick={() => handleRefreshSource(src.id)}
                    style={{
                      backgroundColor: 'var(--bg-elevated)',
                      color: 'var(--text-primary)',
                      border: '1px solid var(--border-subtle)',
                      borderRadius: '4px',
                      padding: '0.3rem 0.6rem',
                      fontSize: '0.75rem',
                      cursor: 'pointer',
                    }}
                  >
                    🔄 Refresh Feed
                  </button>
                </div>
              </div>
            ))}
          </div>

          <div className="card" style={{ marginTop: '1.5rem', backgroundColor: 'rgba(31, 111, 235, 0.05)', borderColor: 'rgba(31, 111, 235, 0.2)' }}>
            <h4 style={{ fontSize: '0.9rem', marginBottom: '0.5rem', color: '#58a6ff' }}>🛡️ Trend Radar Safety Boundary</h4>
            <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
              Only explicitly configured feeds are ingested. No arbitrary web scraping, competitor copying, or bypass algorithms. Stories created enter the newsroom in <strong>IDEA</strong> status with human editorial sign-off mandatory.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
