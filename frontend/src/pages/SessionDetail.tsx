import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useSession, useSessions, useSessionDiff, useSessionConversation, useSessionSummary, useRenameSession } from '../api/hooks';
import StatusBadge from '../components/StatusBadge';
import Tabs from '../components/Tabs';
import FileTree from '../components/FileTree';
import FileViewer from '../components/FileViewer';
import DiffView from '../components/DiffView';
import ConversationView from '../components/ConversationView';
import MarkdownContent from '../components/MarkdownContent';
import { formatDuration, formatTokens, formatDate, formatCost } from '../utils/formatters';

const TAB_LIST = ['Files', 'Diff', 'Summary', 'Conversation'];

export default function SessionDetail() {
  const { sessionId: rawId } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const [activeTab, setActiveTab] = useState('Files');
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  // Handle "pending" session ID
  const isPending = rawId === 'pending';
  const { data: sessions } = useSessions();

  useEffect(() => {
    if (isPending && sessions?.length) {
      const real = sessions.find((s) => s.status === 'running' || s.status === 'pending');
      if (real && real.session_id !== 'pending') {
        navigate(`/ui/sessions/${real.session_id}`, { replace: true });
      }
    }
  }, [isPending, sessions, navigate]);

  const sessionId = rawId || '';
  const { data: session, isLoading, error } = useSession(sessionId);
  const renameSession = useRenameSession();
  const [isEditing, setIsEditing] = useState(false);
  const [editName, setEditName] = useState('');

  // Lazy-load tab data
  const { data: diffs } = useSessionDiff(sessionId, activeTab === 'Diff');
  const { data: conversation } = useSessionConversation(sessionId, activeTab === 'Conversation');
  const { data: summary } = useSessionSummary(sessionId, activeTab === 'Summary');

  if (isPending) {
    return (
      <div className="text-center py-12 text-text-muted">
        Waiting for session to start...
      </div>
    );
  }

  if (isLoading) {
    return <div className="text-center py-12 text-text-muted">Loading session...</div>;
  }

  if (error) {
    return <div className="text-center py-12 text-error">Failed to load session: {(error as Error).message}</div>;
  }

  if (!session) {
    return <div className="text-center py-12 text-text-muted">Session not found.</div>;
  }

  return (
    <div>
      {/* Back link */}
      <Link to="/ui" className="text-accent hover:underline text-sm mb-4 inline-block">
        &larr; All Sessions
      </Link>

      {/* Header */}
      <div className="flex items-center gap-3 mb-4">
        {isEditing ? (
          <input
            autoFocus
            className="text-xl font-semibold text-text-primary bg-surface-light border border-border rounded px-2 py-1 focus:outline-none focus:border-accent"
            value={editName}
            onChange={(e) => setEditName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                const trimmed = editName.trim();
                if (trimmed) {
                  renameSession.mutate({ sessionId, name: trimmed });
                }
                setIsEditing(false);
              } else if (e.key === 'Escape') {
                setIsEditing(false);
              }
            }}
            onBlur={() => {
              const trimmed = editName.trim();
              if (trimmed) {
                renameSession.mutate({ sessionId, name: trimmed });
              }
              setIsEditing(false);
            }}
          />
        ) : (
          <div className="flex items-center gap-2 group">
            <h1 className={`text-xl text-text-primary ${session.name ? 'font-semibold' : 'font-mono'}`}>
              {session.name || session.session_id}
            </h1>
            <button
              onClick={() => { setEditName(session.name || ''); setIsEditing(true); }}
              className="text-text-muted hover:text-text-primary opacity-0 group-hover:opacity-100 transition-opacity cursor-pointer"
              title="Edit session name"
            >
              <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
                <path d="m15 5 4 4" />
              </svg>
            </button>
          </div>
        )}
        <StatusBadge status={session.status} />
      </div>
      {session.name && (
        <div className="font-mono text-xs text-text-muted mb-4 -mt-3">{session.session_id}</div>
      )}

      {/* Metadata grid */}
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3 mb-3">
        <MetaCard label="Status">
          <StatusBadge status={session.status} />
        </MetaCard>
        <MetaCard label="Duration" value={formatDuration(session.duration_seconds ?? (session.duration_ms / 1000))} />
        <MetaCard label="Tokens" value={formatTokens(session.total_tokens)} />
        <MetaCard label="Cost" value={formatCost(session.total_cost_usd)} />
        <MetaCard label="Created" value={formatDate(session.created_at)} />
      </div>
      <div className="mb-6">
        <MetaCard label="Workspace">
          <span className="font-mono text-xs block">
            {session.workspace_dir || '-'}
          </span>
        </MetaCard>
      </div>

      {/* Error display */}
      {session.error && (
        <div className="bg-error/10 border border-error/30 rounded-lg px-4 py-3 mb-4 text-error text-sm">
          {session.error}
        </div>
      )}

      {/* Download button */}
      {session.status === 'completed' && (
        <div className="mb-4">
          <a
            href={`/sessions/${session.session_id}/editable.zip`}
            className="inline-flex items-center gap-2 px-4 py-2 text-sm bg-accent/20 text-accent hover:bg-accent/30 rounded-lg transition-colors"
          >
            Download editable/
          </a>
        </div>
      )}

      {/* Tabs */}
      <Tabs tabs={TAB_LIST} active={activeTab} onChange={setActiveTab} />

      {/* Tab content */}
      {activeTab === 'Files' && (
        <div className="grid grid-cols-1 md:grid-cols-[280px_1fr] gap-0 bg-surface rounded-lg border border-border overflow-hidden min-h-[400px]">
          <div className="border-r border-border overflow-y-auto max-h-[600px] py-2">
            <FileTree
              sessionId={sessionId}
              onFileSelect={setSelectedFile}
              selectedPath={selectedFile ?? undefined}
            />
          </div>
          <div className="min-h-[400px]">
            {selectedFile ? (
              <FileViewer sessionId={sessionId} filePath={selectedFile} />
            ) : (
              <div className="flex items-center justify-center h-full text-text-muted text-sm">
                Select a file to view
              </div>
            )}
          </div>
        </div>
      )}

      {activeTab === 'Diff' && (
        <div>
          {!diffs ? (
            <div className="text-text-muted text-sm py-4">
              {session.status === 'running' || session.status === 'pending'
                ? 'Agent is running — diffs will be available once the session completes.'
                : 'Loading diffs...'}
            </div>
          ) : (
            <DiffView diffs={diffs} />
          )}
        </div>
      )}

      {activeTab === 'Summary' && (
        <div className="bg-surface rounded-lg border border-border p-6">
          {!summary ? (
            <div className="text-text-muted text-sm">
              {session.status === 'running' || session.status === 'pending'
                ? 'Agent is running — summary will be available once the session completes.'
                : 'Loading summary...'}
            </div>
          ) : summary.content ? (
            <MarkdownContent content={summary.content} />
          ) : (
            <div className="text-text-muted text-sm">No summary available.</div>
          )}
        </div>
      )}

      {activeTab === 'Conversation' && (
        <div>
          {!conversation ? (
            <div className="text-text-muted text-sm py-4">
              {session.status === 'running' || session.status === 'pending'
                ? 'Agent is running — conversation will be available once the session completes.'
                : 'Loading conversation...'}
            </div>
          ) : (
            <ConversationView messages={conversation} />
          )}
        </div>
      )}
    </div>
  );
}

function MetaCard({ label, value, children }: { label: string; value?: string; children?: React.ReactNode }) {
  return (
    <div className="bg-surface rounded-lg border border-border px-4 py-3">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      {children || <div className="text-sm font-medium text-text-primary">{value || '-'}</div>}
    </div>
  );
}
