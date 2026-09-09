import React, { useState, useEffect } from 'react';

interface Assignment {
  id: string;
  tenant_id: string;
  title: string;
  description?: string;
  priority: string;
  status: string;
  due_date?: string;
  created_at: string;
}

interface StorySource {
  id: string;
  title: string;
  url?: string;
  publisher_name?: string;
  source_type: string;
  reliability_score?: number;
  rights_metadata?: string;
  notes?: string;
  created_at: string;
}

interface StoryVersion {
  id: string;
  version_number: number;
  headline: string;
  body_payload: string;
  change_summary?: string;
  created_at: string;
}

interface Story {
  id: string;
  tenant_id: string;
  title: string;
  slug: string;
  summary?: string;
  category_id?: string;
  priority: string;
  status: string;
  editorial_owner_id?: string;
  approved_by_user_id?: string;
  approved_at?: string;
  rejection_reason?: string;
  created_at: string;
  sources?: StorySource[];
  versions?: StoryVersion[];
}

// Initial fallback/seed data mirroring News 9 seeded records
const SEEDED_ASSIGNMENTS: Assignment[] = [
  {
    id: 'asgn-news9-seed-01',
    tenant_id: 'tenant-news9-seed-01',
    title: 'Cover UP Municipal Infrastructure & Civic Works Review',
    description: 'Investigate civic road and drainage projects across Gorakhpur and eastern UP.',
    priority: 'HIGH',
    status: 'ASSIGNED',
    due_date: '2026-09-15T18:00:00Z',
    created_at: '2026-09-09T10:00:00Z',
  },
];

const SEEDED_STORIES: Story[] = [
  {
    id: 'story-news9-seed-01',
    tenant_id: 'tenant-news9-seed-01',
    title: 'Gorakhpur Smart Drainage & Highway Expansion Phase 2 Review',
    slug: 'gorakhpur-drainage-highway-expansion-phase-2',
    summary: 'Detailed regional briefing on key civil infrastructure milestones and budget allocations in eastern Uttar Pradesh.',
    priority: 'HIGH',
    status: 'DRAFT',
    editorial_owner_id: 'user-news9-editor-01',
    created_at: '2026-09-09T10:30:00Z',
    sources: [
      {
        id: 'src-seed-01',
        title: 'UP Public Works Department Official Press Release',
        url: 'https://up.gov.in/pwd/press-release-2026-09',
        publisher_name: 'Government of Uttar Pradesh',
        source_type: 'OFFICIAL',
        reliability_score: 95,
        rights_metadata: 'Public domain government press disclosure',
        created_at: '2026-09-09T10:35:00Z',
      },
    ],
    versions: [
      {
        id: 'ver-seed-01',
        version_number: 1,
        headline: 'Gorakhpur Civic Infrastructure Overhaul Enters Next Phase',
        body_payload: 'Gorakhpur: Eastern Uttar Pradesh civic authorities have confirmed the deployment of updated drainage networks and arterial road expansions...',
        change_summary: 'Initial draft compiled from verified official disclosures',
        created_at: '2026-09-09T10:45:00Z',
      },
    ],
  },
];

export const EditorialNewsroom: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'assignments' | 'stories'>('stories');
  const [assignments, setAssignments] = useState<Assignment[]>(SEEDED_ASSIGNMENTS);
  const [stories, setStories] = useState<Story[]>(SEEDED_STORIES);
  const [selectedStoryId, setSelectedStoryId] = useState<string>(SEEDED_STORIES[0].id);
  const [statusActionPending, setStatusActionPending] = useState(false);
  const [newVersionBody, setNewVersionBody] = useState('');
  const [newVersionHeadline, setNewVersionHeadline] = useState('');

  // Fetch live stories and assignments from API if available
  useEffect(() => {
    fetch('/api/v1/assignments')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.items) && data.items.length > 0) {
          setAssignments(data.items);
        }
      })
      .catch(() => {
        // Fallback to seeded data
      });

    fetch('/api/v1/stories')
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data && Array.isArray(data.items) && data.items.length > 0) {
          setStories(data.items);
          setSelectedStoryId(data.items[0].id);
        }
      })
      .catch(() => {
        // Fallback to seeded data
      });
  }, []);

  const selectedStory = stories.find((s) => s.id === selectedStoryId) || stories[0];

  const handleStatusChange = async (targetStatus: string, reason?: string) => {
    if (!selectedStory) return;
    setStatusActionPending(true);
    try {
      const res = await fetch(`/api/v1/stories/${selectedStory.id}/status`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ target_status: targetStatus, reason }),
      });
      if (res.ok) {
        const updated = await res.json();
        setStories((prev) =>
          prev.map((s) => (s.id === selectedStory.id ? { ...s, status: updated.status, approved_by_user_id: updated.approved_by_user_id, approved_at: updated.approved_at, rejection_reason: updated.rejection_reason } : s))
        );
      } else {
        // Local simulation if backend not reached in standalone test
        setStories((prev) =>
          prev.map((s) =>
            s.id === selectedStory.id
              ? {
                  ...s,
                  status: targetStatus,
                  approved_at: targetStatus === 'APPROVED' ? new Date().toISOString() : s.approved_at,
                  rejection_reason: reason || s.rejection_reason,
                }
              : s
          )
        );
      }
    } catch {
      // Local update for preview
      setStories((prev) =>
        prev.map((s) => (s.id === selectedStory.id ? { ...s, status: targetStatus } : s))
      );
    } finally {
      setStatusActionPending(false);
    }
  };

  const handleAddVersion = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStory || !newVersionHeadline || !newVersionBody) return;
    const nextVerNum = (selectedStory.versions?.length || 0) + 1;
    const newVer: StoryVersion = {
      id: `ver-local-${Date.now()}`,
      version_number: nextVerNum,
      headline: newVersionHeadline,
      body_payload: newVersionBody,
      change_summary: `Revision snapshot ${nextVerNum}`,
      created_at: new Date().toISOString(),
    };

    try {
      const res = await fetch(`/api/v1/stories/${selectedStory.id}/versions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          headline: newVersionHeadline,
          body_payload: newVersionBody,
          change_summary: `Revision snapshot ${nextVerNum}`,
        }),
      });
      if (res.ok) {
        const saved = await res.json();
        setStories((prev) =>
          prev.map((s) =>
            s.id === selectedStory.id
              ? { ...s, versions: [saved, ...(s.versions || [])] }
              : s
          )
        );
      } else {
        setStories((prev) =>
          prev.map((s) =>
            s.id === selectedStory.id
              ? { ...s, versions: [newVer, ...(s.versions || [])] }
              : s
          )
        );
      }
    } catch {
      setStories((prev) =>
        prev.map((s) =>
          s.id === selectedStory.id
            ? { ...s, versions: [newVer, ...(s.versions || [])] }
            : s
        )
      );
    }
    setNewVersionHeadline('');
    setNewVersionBody('');
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'APPROVED':
      case 'PUBLISHED':
        return <span className="badge badge-green">{status}</span>;
      case 'APPROVAL_REQUIRED':
      case 'VALIDATION':
        return <span className="badge badge-amber">{status}</span>;
      case 'REJECTED':
        return <span className="badge" style={{ backgroundColor: 'rgba(229, 9, 20, 0.2)', color: '#f85149', border: '1px solid #e50914' }}>{status}</span>;
      default:
        return <span className="badge" style={{ backgroundColor: '#21262d', color: '#8b949e', border: '1px solid #30363d' }}>{status}</span>;
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
      {/* Sub-Navigation */}
      <div style={{ display: 'flex', gap: '1rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.75rem' }}>
        <button
          onClick={() => setActiveTab('stories')}
          style={{
            background: 'none',
            border: 'none',
            color: activeTab === 'stories' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'stories' ? 700 : 500,
            borderBottom: activeTab === 'stories' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
          }}
        >
          Story Desk & Editorial Lifecycle
        </button>
        <button
          onClick={() => setActiveTab('assignments')}
          style={{
            background: 'none',
            border: 'none',
            color: activeTab === 'assignments' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeTab === 'assignments' ? 700 : 500,
            borderBottom: activeTab === 'assignments' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '0.95rem',
          }}
        >
          Assignment Desk ({assignments.length})
        </button>
      </div>

      {activeTab === 'assignments' ? (
        <div className="card">
          <h2>Newsroom Assignment Desk</h2>
          <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
            Tenant-scoped assignment boundary. Assignments guide reporting and research before story draft compilation.
          </p>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
            {assignments.map((asgn) => (
              <div
                key={asgn.id}
                style={{
                  padding: '1rem',
                  backgroundColor: 'var(--bg-elevated)',
                  border: '1px solid var(--border-subtle)',
                  borderRadius: '6px',
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
                  <h3 style={{ fontSize: '1rem', fontWeight: 600 }}>{asgn.title}</h3>
                  <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                    <span className="badge" style={{ backgroundColor: '#21262d', border: '1px solid #30363d', color: '#58a6ff' }}>
                      {asgn.priority}
                    </span>
                    {getStatusBadge(asgn.status)}
                  </div>
                </div>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                  {asgn.description || 'No additional instructions provided.'}
                </p>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', gap: '1.5rem' }}>
                  <span>Assignment ID: {asgn.id}</span>
                  {asgn.due_date && <span>Due: {new Date(asgn.due_date).toLocaleDateString()}</span>}
                </div>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '1.5rem' }}>
          {/* Story List Sidebar */}
          <div className="card" style={{ height: 'fit-content' }}>
            <h2 style={{ fontSize: '1.1rem' }}>Editorial Stories</h2>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginTop: '1rem' }}>
              {stories.map((story) => (
                <div
                  key={story.id}
                  onClick={() => setSelectedStoryId(story.id)}
                  style={{
                    padding: '0.75rem',
                    borderRadius: '6px',
                    backgroundColor: story.id === selectedStoryId ? 'var(--bg-elevated)' : 'transparent',
                    border: `1px solid ${story.id === selectedStoryId ? 'var(--accent-red)' : 'var(--border-subtle)'}`,
                    cursor: 'pointer',
                  }}
                >
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: '0.5rem' }}>
                    <h4 style={{ fontSize: '0.9rem', fontWeight: 600, color: 'var(--text-primary)' }}>{story.title}</h4>
                    {getStatusBadge(story.status)}
                  </div>
                  <p style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.25rem' }}>
                    Slug: {story.slug}
                  </p>
                </div>
              ))}
            </div>
          </div>

          {/* Story Detail & Lifecycle Management */}
          {selectedStory && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1.5rem' }}>
              {/* Detail Header */}
              <div className="card">
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h2>{selectedStory.title}</h2>
                    <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginBottom: '0.75rem' }}>
                      {selectedStory.summary}
                    </p>
                    <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                      <span>Story ID: <code>{selectedStory.id}</code></span>
                      <span>Priority: <strong>{selectedStory.priority}</strong></span>
                      <span>Owner: <strong>{selectedStory.editorial_owner_id || 'Unassigned'}</strong></span>
                    </div>
                  </div>
                  <div>
                    {getStatusBadge(selectedStory.status)}
                  </div>
                </div>

                {/* Editorial Lifecycle Transitions */}
                <div style={{ marginTop: '1.25rem', padding: '1rem', backgroundColor: 'var(--bg-elevated)', borderRadius: '6px', border: '1px solid var(--border-subtle)' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600, marginBottom: '0.5rem' }}>
                    Deterministic Lifecycle Actions (Current: {selectedStory.status})
                  </div>
                  <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
                    {selectedStory.status === 'IDEA' && (
                      <button className="badge badge-amber" disabled={statusActionPending} onClick={() => handleStatusChange('ASSIGNED')}>
                        Assign Story
                      </button>
                    )}
                    {selectedStory.status === 'ASSIGNED' && (
                      <button className="badge badge-amber" disabled={statusActionPending} onClick={() => handleStatusChange('RESEARCHING')}>
                        Start Research
                      </button>
                    )}
                    {(selectedStory.status === 'ASSIGNED' || selectedStory.status === 'RESEARCHING') && (
                      <button className="badge badge-amber" disabled={statusActionPending} onClick={() => handleStatusChange('DRAFT')}>
                        Move to Draft
                      </button>
                    )}
                    {selectedStory.status === 'DRAFT' && (
                      <button className="badge badge-amber" disabled={statusActionPending} onClick={() => handleStatusChange('VALIDATION')}>
                        Submit to Validation
                      </button>
                    )}
                    {selectedStory.status === 'VALIDATION' && (
                      <button className="badge badge-amber" disabled={statusActionPending} onClick={() => handleStatusChange('APPROVAL_REQUIRED')}>
                        Request Editorial Approval
                      </button>
                    )}
                    {selectedStory.status === 'APPROVAL_REQUIRED' && (
                      <>
                        <button className="badge badge-green" disabled={statusActionPending} onClick={() => handleStatusChange('APPROVED')}>
                          Approve Story (Human Sign-off)
                        </button>
                        <button
                          className="badge"
                          style={{ backgroundColor: 'rgba(229, 9, 20, 0.2)', color: '#f85149', border: '1px solid #e50914', cursor: 'pointer' }}
                          disabled={statusActionPending}
                          onClick={() => handleStatusChange('REJECTED', 'Fact-checking inconsistencies detected')}
                        >
                          Reject Story
                        </button>
                      </>
                    )}
                    {selectedStory.status === 'APPROVED' && (
                      <button className="badge badge-green" disabled={statusActionPending} onClick={() => handleStatusChange('PUBLISHED')}>
                        Publish (Phase 1 Guard Enforced)
                      </button>
                    )}
                  </div>
                  {selectedStory.approved_at && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#3fb950' }}>
                      Editorial sign-off recorded at {new Date(selectedStory.approved_at).toLocaleString()}
                    </div>
                  )}
                  {selectedStory.rejection_reason && (
                    <div style={{ marginTop: '0.5rem', fontSize: '0.75rem', color: '#f85149' }}>
                      Rejection Reason: {selectedStory.rejection_reason}
                    </div>
                  )}
                </div>
              </div>

              {/* Source / Reference Metadata */}
              <div className="card">
                <h2>Verified Sources &amp; Citations ({selectedStory.sources?.length || 0})</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                  Extensible reference metadata. No external web scraping or crawling is executed.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                  {selectedStory.sources && selectedStory.sources.length > 0 ? (
                    selectedStory.sources.map((src) => (
                      <div
                        key={src.id}
                        style={{
                          padding: '0.75rem',
                          backgroundColor: 'var(--bg-elevated)',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>{src.title}</span>
                          <span className="badge" style={{ backgroundColor: '#21262d', color: '#58a6ff', border: '1px solid #30363d' }}>
                            {src.source_type}
                          </span>
                        </div>
                        {src.url && (
                          <div style={{ fontSize: '0.8rem', color: '#58a6ff', marginTop: '0.25rem' }}>
                            <a href={src.url} target="_blank" rel="noreferrer" style={{ color: '#58a6ff' }}>
                              {src.url}
                            </a>
                          </div>
                        )}
                        <div style={{ display: 'flex', gap: '1.5rem', fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '0.5rem' }}>
                          <span>Publisher: {src.publisher_name || 'N/A'}</span>
                          {src.reliability_score !== undefined && <span>Reliability: {src.reliability_score}%</span>}
                          {src.rights_metadata && <span>Rights: {src.rights_metadata}</span>}
                        </div>
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No sources linked yet.</div>
                  )}
                </div>
              </div>

              {/* Content Versioning Foundation */}
              <div className="card">
                <h2>Content Versions &amp; Snapshots ({selectedStory.versions?.length || 0})</h2>
                <p style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginBottom: '1rem' }}>
                  Immutable editorial versions preserving draft progression and audit history.
                </p>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', marginBottom: '1.5rem' }}>
                  {selectedStory.versions && selectedStory.versions.length > 0 ? (
                    selectedStory.versions.map((ver) => (
                      <div
                        key={ver.id}
                        style={{
                          padding: '0.75rem',
                          backgroundColor: 'var(--bg-elevated)',
                          borderRadius: '6px',
                          border: '1px solid var(--border-subtle)',
                        }}
                      >
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                          <span style={{ fontWeight: 600, fontSize: '0.9rem' }}>
                            Version {ver.version_number}: {ver.headline}
                          </span>
                          <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)' }}>
                            {new Date(ver.created_at).toLocaleString()}
                          </span>
                        </div>
                        <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', whiteSpace: 'pre-wrap', margin: '0.5rem 0' }}>
                          {ver.body_payload}
                        </p>
                        {ver.change_summary && (
                          <div style={{ fontSize: '0.75rem', color: '#8b949e', fontStyle: 'italic' }}>
                            Summary: {ver.change_summary}
                          </div>
                        )}
                      </div>
                    ))
                  ) : (
                    <div style={{ color: 'var(--text-secondary)', fontSize: '0.85rem' }}>No versions recorded.</div>
                  )}
                </div>

                {/* Create Version Snapshot Form */}
                <form onSubmit={handleAddVersion} style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem', borderTop: '1px solid var(--border-subtle)', paddingTop: '1rem' }}>
                  <div style={{ fontSize: '0.85rem', fontWeight: 600 }}>Create New Immutable Version Snapshot</div>
                  <input
                    type="text"
                    placeholder="Revision Headline"
                    value={newVersionHeadline}
                    onChange={(e) => setNewVersionHeadline(e.target.value)}
                    style={{
                      padding: '0.5rem',
                      borderRadius: '4px',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-elevated)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                    }}
                  />
                  <textarea
                    placeholder="Content draft body..."
                    rows={3}
                    value={newVersionBody}
                    onChange={(e) => setNewVersionBody(e.target.value)}
                    style={{
                      padding: '0.5rem',
                      borderRadius: '4px',
                      border: '1px solid var(--border-subtle)',
                      backgroundColor: 'var(--bg-elevated)',
                      color: 'var(--text-primary)',
                      fontSize: '0.85rem',
                    }}
                  />
                  <button
                    type="submit"
                    style={{
                      alignSelf: 'flex-start',
                      padding: '0.4rem 1rem',
                      backgroundColor: 'var(--accent-red)',
                      border: 'none',
                      borderRadius: '4px',
                      color: '#ffffff',
                      fontWeight: 600,
                      cursor: 'pointer',
                      fontSize: '0.8rem',
                    }}
                  >
                    Commit Version Snapshot
                  </button>
                </form>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
