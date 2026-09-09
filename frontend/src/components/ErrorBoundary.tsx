import { Component, ErrorInfo, ReactNode } from 'react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false,
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    console.error('ErrorBoundary caught error:', error, errorInfo);
  }

  public render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '2rem', textAlign: 'center', color: '#f85149' }}>
          <h2>Application Boundary Exception</h2>
          <p>{this.state.error?.message || 'An unexpected rendering error occurred.'}</p>
          <button
            style={{
              marginTop: '1rem',
              padding: '0.5rem 1rem',
              backgroundColor: '#21262d',
              color: '#f0f6fc',
              border: '1px solid #30363d',
              borderRadius: '6px',
              cursor: 'pointer',
            }}
            onClick={() => window.location.reload()}
          >
            Reload Foundation Shell
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
