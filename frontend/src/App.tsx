import { useState } from 'react';
import { HealthDashboard } from './components/HealthDashboard';
import { EditorialNewsroom } from './components/EditorialNewsroom';
import { TrendRadarWorkspace } from './components/TrendRadarWorkspace';
import { AIResearchWorkspace } from './components/AIResearchWorkspace';
import { MediaProductionWorkspace } from './components/MediaProductionWorkspace';
import { PublishingCommandCenter } from './components/PublishingCommandCenter';

export const App = () => {
  const [activeView, setActiveView] = useState<'publishing' | 'media' | 'research' | 'radar' | 'editorial' | 'foundation'>('publishing');

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
                Publishing &amp; Distribution &middot; Phase 6 Workspace
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className="badge badge-green">Phase 6 Active</span>
        </div>
      </header>

      {/* Primary Workspace Navigation */}
      <nav
        style={{
          display: 'flex',
          gap: '1.5rem',
          marginBottom: '2rem',
          borderBottom: '1px solid var(--border-subtle)',
          paddingBottom: '0.5rem',
        }}
      >
        <button
          onClick={() => setActiveView('publishing')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'publishing' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'publishing' ? 700 : 500,
            borderBottom: activeView === 'publishing' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          🚀 Publishing &amp; Distribution
        </button>
        <button
          onClick={() => setActiveView('media')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'media' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'media' ? 700 : 500,
            borderBottom: activeView === 'media' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          🎬 Media &amp; Video Production
        </button>
        <button
          onClick={() => setActiveView('research')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'research' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'research' ? 700 : 500,
            borderBottom: activeView === 'research' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          🤖 AI Intelligence &amp; Research
        </button>
        <button
          onClick={() => setActiveView('radar')}
          style={{
            background: 'none',
            border: 'none',
            color: activeView === 'radar' ? 'var(--text-primary)' : 'var(--text-secondary)',
            fontWeight: activeView === 'radar' ? 700 : 500,
            borderBottom: activeView === 'radar' ? '2px solid var(--accent-red)' : 'none',
            paddingBottom: '0.5rem',
            cursor: 'pointer',
            fontSize: '1rem',
          }}
        >
          📡 Trend Radar
        </button>
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
          📰 Editorial Newsroom
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
          ⚙️ System Foundation &amp; Health
        </button>
      </nav>

      <main>
        {activeView === 'publishing' ? (
          <PublishingCommandCenter />
        ) : activeView === 'media' ? (
          <MediaProductionWorkspace />
        ) : activeView === 'research' ? (
          <AIResearchWorkspace />
        ) : activeView === 'radar' ? (
          <TrendRadarWorkspace />
        ) : activeView === 'editorial' ? (
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
              <h2>Phase 3 Architectural Invariants</h2>
              <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Deterministic Trend Scoring:</strong> Transparent formula combining freshness decay, mention velocity, publisher diversity, and source authority.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Bounded RSS/Atom Ingestion:</strong> Safe XML parsing with entity expansion disabled, payload byte capping, and non-crawling policy.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Strict SSRF &amp; Network Defense:</strong> Blocking private IPv4, IPv6 loopback, cloud metadata endpoints, and non-HTTP protocols.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Mandatory Human Editorial Review:</strong> Opportunities must be explicitly accepted or converted into Stories in IDEA status; no auto-publishing.
                </li>
                <li>
                  <strong style={{ color: 'var(--text-primary)' }}>Full Tenant &amp; Audit Isolation:</strong> All sources, items, groups, opportunities, and actions are tenant-scoped and audit-logged.
                </li>
              </ul>
            </div>
          </>
        )}
      </main>
    </div>
  );
};
