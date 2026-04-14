import { useState } from 'react';
import { useSessionFiles } from '../api/hooks';
import { formatSize } from '../utils/formatters';
import type { FileEntry } from '../api/types';

interface FileTreeProps {
  sessionId: string;
  onFileSelect: (path: string) => void;
  selectedPath?: string;
}

export default function FileTree({ sessionId, onFileSelect, selectedPath }: FileTreeProps) {
  const { data: rootFiles, isLoading } = useSessionFiles(sessionId);

  if (isLoading) return <div className="text-text-muted text-sm p-3">Loading files...</div>;
  if (!rootFiles?.length) return <div className="text-text-muted text-sm p-3">No files</div>;

  return (
    <div className="text-sm">
      {rootFiles.map((entry) => (
        <TreeNode
          key={entry.path}
          entry={entry}
          sessionId={sessionId}
          depth={0}
          onFileSelect={onFileSelect}
          selectedPath={selectedPath}
        />
      ))}
    </div>
  );
}

function TreeNode({
  entry,
  sessionId,
  depth,
  onFileSelect,
  selectedPath,
}: {
  entry: FileEntry;
  sessionId: string;
  depth: number;
  onFileSelect: (path: string) => void;
  selectedPath?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const { data: children } = useSessionFiles(
    sessionId,
    entry.is_dir && expanded ? entry.path : undefined
  );

  const isSelected = selectedPath === entry.path;

  if (entry.is_dir) {
    return (
      <div>
        <button
          onClick={() => setExpanded(!expanded)}
          className={`w-full text-left px-2 py-1 flex items-center gap-1.5 hover:bg-surface-light/50 transition-colors rounded cursor-pointer ${
            isSelected ? 'bg-surface-light' : ''
          }`}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          <span className="text-text-muted text-xs">{expanded ? '▼' : '▶'}</span>
          <span>📁</span>
          <span className="text-text-primary truncate">{entry.name}</span>
        </button>
        {expanded && children?.map((child) => (
          <TreeNode
            key={child.path}
            entry={child}
            sessionId={sessionId}
            depth={depth + 1}
            onFileSelect={onFileSelect}
            selectedPath={selectedPath}
          />
        ))}
      </div>
    );
  }

  return (
    <button
      onClick={() => onFileSelect(entry.path)}
      className={`w-full text-left px-2 py-1 flex items-center gap-1.5 hover:bg-surface-light/50 transition-colors rounded cursor-pointer ${
        isSelected ? 'bg-accent/10 text-accent' : ''
      }`}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
    >
      <span className="text-xs opacity-0">▶</span>
      <span>📄</span>
      <span className="truncate flex-1">{entry.name}</span>
      <span className="text-text-muted text-xs flex-shrink-0">{formatSize(entry.size)}</span>
    </button>
  );
}
