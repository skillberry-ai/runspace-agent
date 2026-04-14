import { useState } from 'react';
import type { DiffEntry } from '../api/types';

interface DiffViewProps {
  diffs: DiffEntry[];
}

export default function DiffView({ diffs }: DiffViewProps) {
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(
    new Set(diffs.map((d) => d.path))
  );
  const [allExpanded, setAllExpanded] = useState(true);

  const totalAdditions = diffs.reduce((sum, d) => sum + d.additions, 0);
  const totalDeletions = diffs.reduce((sum, d) => sum + d.deletions, 0);

  const toggleAll = () => {
    if (allExpanded) {
      setExpandedFiles(new Set());
    } else {
      setExpandedFiles(new Set(diffs.map((d) => d.path)));
    }
    setAllExpanded(!allExpanded);
  };

  const toggleFile = (path: string) => {
    const next = new Set(expandedFiles);
    if (next.has(path)) next.delete(path);
    else next.add(path);
    setExpandedFiles(next);
    setAllExpanded(next.size === diffs.length);
  };

  if (!diffs.length) {
    return <div className="text-text-muted text-sm py-4">No changes detected.</div>;
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-4 px-3 py-2 bg-surface rounded-lg border border-border">
        <div className="text-sm">
          <span className="text-text-muted">{diffs.length} file{diffs.length !== 1 ? 's' : ''} changed</span>
          {totalAdditions > 0 && <span className="text-success ml-3">+{totalAdditions}</span>}
          {totalDeletions > 0 && <span className="text-error ml-3">-{totalDeletions}</span>}
        </div>
        <button
          onClick={toggleAll}
          className="text-xs text-accent hover:text-accent/80 transition-colors cursor-pointer"
        >
          {allExpanded ? 'Collapse all' : 'Expand all'}
        </button>
      </div>

      <div className="space-y-3">
        {diffs.map((diff) => (
          <DiffFileCard
            key={diff.path}
            diff={diff}
            expanded={expandedFiles.has(diff.path)}
            onToggle={() => toggleFile(diff.path)}
          />
        ))}
      </div>
    </div>
  );
}

function DiffFileCard({
  diff,
  expanded,
  onToggle,
}: {
  diff: DiffEntry;
  expanded: boolean;
  onToggle: () => void;
}) {
  const statusColors = {
    added: 'bg-success/20 text-success',
    deleted: 'bg-error/20 text-error',
    modified: 'bg-accent/20 text-accent',
  };

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={onToggle}
        className="w-full flex items-center gap-3 px-4 py-2.5 bg-surface hover:bg-surface-light/50 transition-colors cursor-pointer"
      >
        <span className="text-text-muted text-xs">{expanded ? '▼' : '▶'}</span>
        <span className="font-mono text-sm text-text-primary flex-1 text-left">{diff.path}</span>
        <span className={`text-xs px-2 py-0.5 rounded-full ${statusColors[diff.status]}`}>
          {diff.status}
        </span>
        {diff.additions > 0 && <span className="text-success text-xs">+{diff.additions}</span>}
        {diff.deletions > 0 && <span className="text-error text-xs">-{diff.deletions}</span>}
      </button>

      {expanded && (
        <div className="border-t border-border overflow-x-auto">
          <pre className="text-xs font-mono leading-5 m-0">
            {diff.diff.split('\n').map((line, i) => (
              <DiffLine key={i} line={line} />
            ))}
          </pre>
        </div>
      )}
    </div>
  );
}

function DiffLine({ line }: { line: string }) {
  let className = 'px-4 whitespace-pre ';
  if (line.startsWith('+') && !line.startsWith('+++')) {
    className += 'bg-diff-add text-success';
  } else if (line.startsWith('-') && !line.startsWith('---')) {
    className += 'bg-diff-del text-error';
  } else if (line.startsWith('@@')) {
    className += 'bg-diff-hunk text-accent';
  } else {
    className += 'text-text-muted';
  }

  return <div className={className}>{line || ' '}</div>;
}
