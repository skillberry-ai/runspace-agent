import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';

export default function Layout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-body">
      <header className="border-b border-border bg-surface px-6 py-3 flex items-center justify-between">
        <Link to="/ui" className="flex items-center gap-2 text-text-primary no-underline hover:text-accent transition-colors">
          <span className="text-2xl">🚀</span>
          <span className="text-xl font-semibold">Runspace</span>
        </Link>
        <span className="text-text-muted text-sm">v0.1.0</span>
      </header>
      <main className="max-w-[1400px] mx-auto px-6 py-6">
        {children}
      </main>
    </div>
  );
}
