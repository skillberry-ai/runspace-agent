import { useState, useMemo } from 'react';
import { Link } from 'react-router-dom';
import { useSessions, useDeleteSession, useDeleteAllSessions } from '../api/hooks';
import type { SessionInfo } from '../api/types';
import StatusBadge from '../components/StatusBadge';
import ConfirmDialog from '../components/ConfirmDialog';
import { formatDate, formatDuration } from '../utils/formatters';

type StatusFilter = 'all' | 'pending' | 'running' | 'completed' | 'failed';
type DateFilter = 'all' | 'today' | '7d' | '30d';

function matchesDateFilter(session: SessionInfo, filter: DateFilter): boolean {
  if (filter === 'all') return true;
  const created = new Date(session.created_at).getTime();
  const now = Date.now();
  const day = 86_400_000;
  if (filter === 'today') return now - created < day;
  if (filter === '7d') return now - created < 7 * day;
  return now - created < 30 * day;
}

export default function SessionList() {
  const { data: sessions, isLoading, error } = useSessions();
  const deleteSession = useDeleteSession();
  const deleteAll = useDeleteAllSessions();

  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [showDeleteAll, setShowDeleteAll] = useState(false);
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('all');
  const [dateFilter, setDateFilter] = useState<DateFilter>('all');

  const filteredSessions = useMemo(() => {
    if (!sessions) return [];
    return sessions.filter((s) => {
      if (statusFilter !== 'all' && s.status !== statusFilter) return false;
      if (!matchesDateFilter(s, dateFilter)) return false;
      return true;
    });
  }, [sessions, statusFilter, dateFilter]);

  const handleDelete = () => {
    if (deleteTarget) {
      deleteSession.mutate(deleteTarget);
      setDeleteTarget(null);
    }
  };

  const handleDeleteAll = () => {
    deleteAll.mutate();
    setShowDeleteAll(false);
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

  const selectClass =
    'bg-surface-light border border-border text-text-primary rounded px-3 py-1.5 text-sm focus:outline-none focus:border-accent';

  return (
    <div>
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-semibold text-text-primary">Sessions</h1>
        {sessions && sessions.length > 0 && (
          <button
            onClick={() => setShowDeleteAll(true)}
            className="px-4 py-2 text-sm rounded-md bg-error/10 hover:bg-error/20 text-error transition-colors cursor-pointer"
          >
            Delete All
          </button>
        )}
      </div>

      {/* Filters */}
      {sessions && sessions.length > 0 && (
        <div className="flex items-center gap-3 mb-4">
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value as StatusFilter)}
            className={selectClass}
          >
            <option value="all">All statuses</option>
            <option value="pending">Pending</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>

          <select
            value={dateFilter}
            onChange={(e) => setDateFilter(e.target.value as DateFilter)}
            className={selectClass}
          >
            <option value="all">All time</option>
            <option value="today">Today</option>
            <option value="7d">Last 7 days</option>
            <option value="30d">Last 30 days</option>
          </select>

          {(statusFilter !== 'all' || dateFilter !== 'all') && (
            <button
              onClick={() => { setStatusFilter('all'); setDateFilter('all'); }}
              className="text-xs text-text-muted hover:text-text-primary transition-colors cursor-pointer"
            >
              Clear filters
            </button>
          )}

          <span className="ml-auto text-xs text-text-muted">
            {filteredSessions.length} of {sessions.length} sessions
          </span>
        </div>
      )}

      {!sessions?.length ? (
        <div className="text-center py-16 bg-surface rounded-lg border border-border">
          <p className="text-text-muted text-lg mb-2">No sessions yet</p>
          <p className="text-text-muted text-sm">
            POST to <code className="text-accent bg-surface-light px-1.5 py-0.5 rounded text-xs font-mono">/run</code> to create one.
          </p>
        </div>
      ) : filteredSessions.length === 0 ? (
        <div className="text-center py-16 bg-surface rounded-lg border border-border">
          <p className="text-text-muted text-lg mb-2">No sessions match your filters</p>
          <button
            onClick={() => { setStatusFilter('all'); setDateFilter('all'); }}
            className="text-accent text-sm hover:underline cursor-pointer"
          >
            Clear filters
          </button>
        </div>
      ) : (
        <div className="bg-surface rounded-lg border border-border overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left px-4 py-3 text-text-muted font-medium">Session</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Status</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Created</th>
                <th className="text-left px-4 py-3 text-text-muted font-medium">Duration</th>
                <th className="text-right px-4 py-3 text-text-muted font-medium">Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredSessions.map((session) => (
                <tr
                  key={session.session_id}
                  className="border-b border-border last:border-b-0 hover:bg-surface-light/30 transition-colors"
                >
                  <td className="px-4 py-3">
                    <Link
                      to={`/ui/sessions/${session.session_id}`}
                      className="text-accent hover:underline"
                    >
                      {session.name ? (
                        <span>{session.name}</span>
                      ) : (
                        <span className="font-mono">
                          {session.session_id.length > 20
                            ? session.session_id.slice(0, 20) + '...'
                            : session.session_id}
                        </span>
                      )}
                    </Link>
                    {session.name && (
                      <div className="font-mono text-xs text-text-muted mt-0.5">
                        {session.session_id}
                      </div>
                    )}
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

      {/* Single delete confirmation */}
      <ConfirmDialog
        open={deleteTarget !== null}
        title="Delete Session"
        message="Are you sure you want to delete this session? This will remove all associated files."
        onConfirm={handleDelete}
        onCancel={() => setDeleteTarget(null)}
      />

      {/* Delete all confirmation */}
      <ConfirmDialog
        open={showDeleteAll}
        title="Delete All Sessions"
        message={`Are you sure you want to delete all ${sessions?.length ?? 0} sessions? This will remove all workspaces and cannot be undone.`}
        confirmLabel="Delete All"
        onConfirm={handleDeleteAll}
        onCancel={() => setShowDeleteAll(false)}
      />
    </div>
  );
}
