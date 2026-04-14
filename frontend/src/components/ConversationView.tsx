import { useState, useMemo } from 'react';
import type { ConversationMessage, ContentBlock, ToolUseBlock, ThinkingBlock, ToolResultBlock, TextBlock } from '../api/types';
import { formatDuration } from '../utils/formatters';

const PAGE_SIZE = 100;

interface ConversationViewProps {
  messages: ConversationMessage[];
}

export default function ConversationView({ messages }: ConversationViewProps) {
  const [visibleCount, setVisibleCount] = useState(PAGE_SIZE);

  const visible = useMemo(() => messages.slice(0, visibleCount), [messages, visibleCount]);
  const remaining = messages.length - visibleCount;

  if (!messages.length) {
    return <div className="text-text-muted text-sm py-4">No conversation data.</div>;
  }

  return (
    <div className="space-y-3">
      {visible.map((msg, i) => (
        <MessageCard key={i} message={msg} />
      ))}
      {remaining > 0 && (
        <button
          onClick={() => setVisibleCount((c) => c + PAGE_SIZE)}
          className="w-full py-2.5 text-sm text-accent bg-surface hover:bg-surface-light border border-border rounded-lg transition-colors cursor-pointer"
        >
          Load more ({remaining} remaining)
        </button>
      )}
    </div>
  );
}

const roleBorderColors: Record<string, string> = {
  assistant: 'border-l-purple',
  user: 'border-l-success',
  system: 'border-l-text-muted',
  result: 'border-l-accent',
};

const roleLabelColors: Record<string, string> = {
  assistant: 'text-purple',
  user: 'text-success',
  system: 'text-text-muted',
  result: 'text-accent',
};

function MessageCard({ message }: { message: ConversationMessage }) {
  const borderColor = roleBorderColors[message.type] || 'border-l-border';
  const labelColor = roleLabelColors[message.type] || 'text-text-muted';

  return (
    <div className={`border-l-4 ${borderColor} bg-surface rounded-r-lg p-4`}>
      <div className="flex items-center gap-2 mb-2">
        <span className={`text-xs font-semibold uppercase ${labelColor}`}>
          {message.type === 'result' ? 'Session Result' : message.type}
        </span>
        {message.model && (
          <span className="text-xs text-text-muted bg-surface-light px-1.5 py-0.5 rounded">
            {message.model}
          </span>
        )}
      </div>
      <MessageContent message={message} />
    </div>
  );
}

function MessageContent({ message }: { message: ConversationMessage }) {
  if (message.type === 'result') {
    return <ResultContent message={message} />;
  }

  if (message.type === 'system') {
    return (
      <CollapsibleBlock title="System data" defaultOpen={false}>
        <pre className="text-xs font-mono text-text-muted whitespace-pre-wrap">
          {typeof message.content === 'string'
            ? message.content
            : JSON.stringify(message.data || message.content, null, 2)}
        </pre>
      </CollapsibleBlock>
    );
  }

  const content = message.content;
  if (typeof content === 'string') {
    return <p className="text-sm whitespace-pre-wrap">{content}</p>;
  }

  if (Array.isArray(content)) {
    return (
      <div className="space-y-2">
        {(content as ContentBlock[]).map((block, i) => (
          <BlockRenderer key={i} block={block} />
        ))}
      </div>
    );
  }

  return null;
}

function BlockRenderer({ block }: { block: ContentBlock }) {
  switch (block.type) {
    case 'text':
      return <p className="text-sm whitespace-pre-wrap">{(block as TextBlock).text}</p>;

    case 'thinking':
      return (
        <CollapsibleBlock title="Thinking" defaultOpen={false}>
          <p className="text-sm text-text-muted whitespace-pre-wrap italic">
            {(block as ThinkingBlock).thinking}
          </p>
        </CollapsibleBlock>
      );

    case 'tool_use': {
      const tb = block as ToolUseBlock;
      return (
        <CollapsibleBlock
          title={
            <span className="flex items-center gap-2">
              <span className="bg-accent/20 text-accent text-xs px-1.5 py-0.5 rounded">tool</span>
              <span className="font-mono">{tb.name}</span>
            </span>
          }
          defaultOpen={false}
        >
          <pre className="text-xs font-mono text-text-muted whitespace-pre-wrap bg-body rounded p-3">
            {JSON.stringify(tb.input, null, 2)}
          </pre>
        </CollapsibleBlock>
      );
    }

    case 'tool_result': {
      const tr = block as ToolResultBlock;
      return (
        <CollapsibleBlock
          title={
            <span className="flex items-center gap-2">
              <span className={`text-xs px-1.5 py-0.5 rounded ${tr.is_error ? 'bg-error/20 text-error' : 'bg-success/20 text-success'}`}>
                {tr.is_error ? 'error' : 'result'}
              </span>
            </span>
          }
          defaultOpen={false}
        >
          <pre className="text-xs font-mono text-text-muted whitespace-pre-wrap bg-body rounded p-3 max-h-60 overflow-auto">
            {typeof tr.content === 'string' ? tr.content : JSON.stringify(tr.content, null, 2)}
          </pre>
        </CollapsibleBlock>
      );
    }

    default:
      return null;
  }
}

function ResultContent({ message }: { message: ConversationMessage }) {
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {message.duration_ms != null && (
          <MetricCard label="Duration" value={formatDuration(message.duration_ms / 1000)} />
        )}
        {message.num_turns != null && (
          <MetricCard label="Turns" value={String(message.num_turns)} />
        )}
        {message.total_cost_usd != null && (
          <MetricCard label="Cost" value={`$${message.total_cost_usd.toFixed(4)}`} />
        )}
        <MetricCard
          label="Status"
          value={message.is_error ? 'Error' : 'Success'}
          valueClass={message.is_error ? 'text-error' : 'text-success'}
        />
      </div>
      {message.result && (
        <div className="text-sm whitespace-pre-wrap bg-body rounded-lg p-3 border border-border">
          {message.result}
        </div>
      )}
    </div>
  );
}

function MetricCard({
  label,
  value,
  valueClass = 'text-text-primary',
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="bg-body rounded-lg p-3 border border-border">
      <div className="text-xs text-text-muted mb-1">{label}</div>
      <div className={`text-sm font-semibold ${valueClass}`}>{value}</div>
    </div>
  );
}

function CollapsibleBlock({
  title,
  defaultOpen,
  children,
}: {
  title: React.ReactNode;
  defaultOpen: boolean;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(defaultOpen);

  return (
    <div className="border border-border rounded-lg overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-surface-light/30 hover:bg-surface-light/50 transition-colors text-sm cursor-pointer"
      >
        <span className="text-text-muted text-xs">{open ? '▼' : '▶'}</span>
        <span className="flex-1 text-left">{title}</span>
      </button>
      {open && <div className="p-3 border-t border-border">{children}</div>}
    </div>
  );
}
