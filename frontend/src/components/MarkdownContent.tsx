import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function MarkdownContent({ content }: { content: string }) {
  return (
    <div className="prose prose-invert prose-sm max-w-none prose-headings:text-text-primary prose-p:text-text-primary prose-a:text-accent prose-code:text-accent prose-code:bg-surface-light prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:before:content-none prose-code:after:content-none prose-pre:bg-body prose-pre:border prose-pre:border-border">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </div>
  );
}
