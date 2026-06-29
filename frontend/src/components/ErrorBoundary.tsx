import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Operational log only; never surfaces internals to the user.
    console.error("UI error boundary", error, info.componentStack);
  }

  render(): ReactNode {
    if (this.state.error) {
      return (
        <div className="state" role="alert">
          <div className="glyph" aria-hidden="true">⚠</div>
          <h3>This screen crashed</h3>
          <p>Try reloading the page. If it persists, contact an administrator.</p>
          <button type="button" onClick={() => this.setState({ error: null })}>
            Dismiss
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
