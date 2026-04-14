import type { SessionStatus } from '../api/types';

const styles: Record<SessionStatus, string> = {
  pending: 'bg-warning/20 text-warning',
  running: 'bg-accent/20 text-accent animate-pulse',
  completed: 'bg-success/20 text-success',
  failed: 'bg-error/20 text-error',
};

export default function StatusBadge({ status }: { status: SessionStatus }) {
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${styles[status]}`}>
      {status}
    </span>
  );
}
