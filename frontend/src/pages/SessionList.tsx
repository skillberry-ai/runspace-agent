import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useSessions, useDeleteSession } from '../api/hooks';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import { formatDate, formatDuration } from '../utils/formatters';

export default function SessionList() {
  const { data: sessions, isLoading, error } = useSessions();
  const deleteSession = useDeleteSession();
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const handleDelete = () => {
    if (deleteTarget) {
      deleteSession.mutate(deleteTarget);
      setDeleteTarget(null);
    }
  };

  if (isLoading) {
    return (
      <div className="text-center py-12 text-text-muted">
        Loading sessions...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-center py-12 text-error">
        Failed to load sessions: {(error as Error).message}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-semibold text-text-primary">Sessions</h1>
      </div>

      {!sessions?.length ? (
        <div className="text-center py-16 bg-surface rounded-lg border border-border">
          <p className="text-text-muted text-lg mb-2">No sessions yet</p>
          <p className="text-text-muted text-sm">
            POST to <code className="text-accent bg-surface-light px-1.5 py-0.5 rounded text-xs font-mono">/run</code> to create one.
          </p>
        </div>
      ) : (
        <div className="bg-surface rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 text-text-muted font-medium">Session ID</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Status</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Created</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Duration</th>
                <th className="text-right px-4 py-3 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr
                  key={session.session_id}
                  className="border-b border-border last:border-b-0 hover:bg-surface-light/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/ui/sessions/${session.session_id}`}
                      className="font-mono text-accent hover:underline"
                    >
                      {session.session_id.length > 20
                        ? session.session_id.slice(0, 20) + '...'
                        : session.session_id}
                    </Link>
                  </td>
                  <td className="px-4 py-3">
                    <StatusBadge status={session.status} />
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {formatDate(session.created_at)}
                  </td>
                  <td className="px-4 py-3 text-text-muted">
                    {formatDuration(session.duration_seconds)}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-2">
                      <Link
                        to={`/ui/sessions/${session.session_id}`}
                        className="px-3 py-1.5 text-xs bg-surface-light hover:bg-border text-text-primary rounded transition-colors"
                        title="Browse"
                      >
                        Browse
                      </Link>
                      {session.status === 'completed' && (
                        <a
                          href={`/sessions/${session.session_id}/editable.zip`}
                          className="px-3 py-1.5 text-xs bg-surface-light hover:bg-border text-text-primary rounded transition-colors"
                          title="Download"
                        >
                          Download
                        </a>
                      )}
                      <button
                        onClick={() => setDeleteTarget(session.session_id)}
                        className="px-3 py-1.5 text-xs bg-error/10 hover:bg-error/20 text-error rounded transition-colors cursor-pointer"
                        title="Delete"
                      >
                        Delete
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete Session"
        message="Are you sure you want to delete this session? This will remove all associated files."
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />
    </div>
  );
}
