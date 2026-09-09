import { HealthDashboard } from './components/HealthDashboard';

export const App = () => {
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
                Multi-Tenant Production Foundation &middot; Phase 1
              </p>
            </div>
          </div>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <span className="badge badge-green">Production Foundation</span>
        </div>
      </header>

      <main>
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
          <h2>Phase 1 Architectural Invariants</h2>
          <ul style={{ paddingLeft: '1.5rem', color: 'var(--text-secondary)', lineHeight: '1.8' }}>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Strict Tenant Isolation:</strong> Access authorized strictly via authenticated identity and verified database memberships.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Deterministic Publishing Guard:</strong> AI generation cannot publish directly to external platforms without human sign-off.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Self-Hosted AI Inference:</strong> Ollama / local endpoints prioritized; zero core reliance on paid AI APIs.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Agent Runtime Sandbox:</strong> Prime Agent adapter in non-executing PENDING_VERIFICATION state; host execution disabled.
            </li>
            <li>
              <strong style={{ color: 'var(--text-primary)' }}>Brand Independent:</strong> News 9 is configured as a tenant entity, not hardcoded into system logic.
            </li>
          </ul>
        </div>
      </main>
    </div>
  );
};
