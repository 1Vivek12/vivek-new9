import { useState } from 'react';
import { HealthDashboard } from './components/HealthDashboard';
import { EditorialNewsroom } from './components/EditorialNewsroom';

export const App = () => {
  const [activeView, setActiveView] = useState<'editorial' | 'foundation'>('editorial');

  // First seeded tenant: News 9 workspace profile
  const tenantProfile = {
    name: 'News 9',
    slug: 'news9',
    status: 'ACTIVE',
    role: 'EDITOR',
    tone: 'Fast, authoritative, verified regional & national reporting',
    beats: ['Politics', 'Gorakhpur Region', 'Technology', 'Economy'],
  };

  return (
    <div className="container">
      <header className="header">
        <div className="header-brand">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <div
              style={{
                width: '36px',
                height: '36px',
                backgroundColor: 'var(--accent-red)',
                borderRadius: '6px',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 800,
                color: '#ffffff',
              }}
            >
              N9
            </div>
            <div>
              <h1 style={{ fontSize: '1.25rem', fontWeight: 700 }}>News 9 Automation Platform</h1>
              <p style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                Editorial Content Core &middot; Phase 2 Workspace
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className="badge badge-green">Phase 2 Core</span>
        </div>
      </header>

      {/* Primary Workspace Navigation */}
      <nav style={{ display: 'flex', gap: '1rem', marginBottom: '2rem', borderBottom: '1px solid var(--border-subtle)', paddingBottom: '0.5rem' }}>
        <button
          onClick={() => setActiveView('editorial')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'editorial' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'editorial' ? 700 : 500,
            borderBottom: activeView === 'editorial' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          Editorial Newsroom
        </button>
        <button
          onClick={() => setActiveView('foundation')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'foundation' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'foundation' ? 700 : 500,
            borderBottom: activeView === 'foundation' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          System Foundation &amp; Health
        </button>
      </nav>

      <main>
        {activeView === 'editorial' ? (
          <EditorialNewsroom />
        ) : (
          <>
            <div className="card">
              <h2>Active Workspace Profile (First Seeded Tenant)</h2>
              <div className="grid">
                <div>
                  <div className="metric-row">
                    <span className="metric-label">Tenant Name</span>
                    <span className="metric-value">{tenantProfile.name}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Workspace Identifier (Slug)</span>
                    <span className="metric-value">{tenantProfile.slug}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Status</span>
                    <span className="badge badge-green">{tenantProfile.status}</span>
                  </div>
                </div>

                <div>
                  <div className="metric-row">
                    <span className="metric-label">Editorial Tone</span>
                    <span className="metric-value">{tenantProfile.tone}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Assigned Role</span>
                    <span className="metric-value">{tenantProfile.role}</span>
                  </div>
                  <div className="metric-row">
                    <span className="metric-label">Coverage Beats</span>
                    <span className="metric-value">{tenantProfile.beats.join(', ')}</span>
                  </div>
                </div>
              </div>
            </div>

            <HealthDashboard />

            <div className="card">
              <h2>Phase 2 Architectural Invariants</h2>
              <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Strict Tenant Isolation:</strong> Every category, assignment, story, source, and version is bound to a verified <code>tenant_id</code>.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Deterministic Editorial Lifecycle:</strong> Strictly defined state machine (IDEA &rarr; ASSIGNED &rarr; RESEARCHING &rarr; DRAFT &rarr; VALIDATION &rarr; APPROVAL_REQUIRED &rarr; APPROVED &rarr; PUBLISHED).
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Human Editorial Publishing Guard:</strong> AI generation cannot bypass human editorial sign-off.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Immutable Story Versioning:</strong> Revision snapshots are immutable records of editorial draft progression.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Source Metadata Boundary:</strong> Extensible citation metadata without web scraping, crawling, or unverified automated URL fetching.
                </li>
              </ul>
            </div>
          </>
        )}
      </main>
    </div>
  );
};
