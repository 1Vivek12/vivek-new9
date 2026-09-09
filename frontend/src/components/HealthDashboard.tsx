import { useEffect, useState } from 'react';

interface ReadinessState {
  status: string;
  database?: { connected: boolean; driver: string };
  redis?: { connected: boolean };
  ai_provider?: { type: string; connected: boolean; target: string };
  agent_runtime?: {
    status: string;
    executable: boolean;
    runtime_type: string;
    security_sandbox: string;
  };
}

export const HealthDashboard = () => {
  const [readiness, setReadiness] = useState<ReadinessState | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchHealth = async () => {
    try {
      setLoading(true);
      const res = await fetch('/ready');
      const data = await res.json();
      setReadiness(data);
      setError(null);
    } catch (err: any) {
      setError('Backend API unreachable. Ensure FastAPI is running on port 8000.');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHealth();
    const interval = setInterval(fetchHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="card">
      <h2>System & Architecture Diagnostics</h2>
      {loading && !readiness && <p style={{ color: 'var(--text-secondary)' }}>Checking services...</p>}
      {error && <p style={{ color: '#f85149' }}>{error}</p>}

      {readiness && (
        <div className="grid">
          <div>
            <div className="metric-row">
              <span className="metric-label">Platform Readiness</span>
              <span className={`badge ${readiness.status === 'READY' ? 'badge-green' : 'badge-amber'}`}>
                {readiness.status}
              </span>
            </div>
            <div className="metric-row">
              <span className="metric-label">Database Connection</span>
              <span className="metric-value">
                {readiness.database?.connected ? 'Connected' : 'Offline'} ({readiness.database?.driver})
              </span>
            </div>
            <div className="metric-row">
              <span className="metric-label">Redis Task Broker</span>
              <span className="metric-value">
                {readiness.redis?.connected ? 'Connected' : 'Standby / Offline'}
              </span>
            </div>
          </div>

          <div>
            <div className="metric-row">
              <span className="metric-label">AI Inference Provider</span>
              <span className="metric-value">
                {readiness.ai_provider?.type} (Local Target: {readiness.ai_provider?.target})
              </span>
            </div>
            <div className="metric-row">
              <span className="metric-label">Agent Runtime Engine</span>
              <span className="metric-value">{readiness.agent_runtime?.runtime_type}</span>
            </div>
            <div className="metric-row">
              <span className="metric-label">Agent Execution Posture</span>
              <span className="badge badge-amber">
                {readiness.agent_runtime?.status} (Execution Disabled)
              </span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
