import { useState, useEffect } from 'react';
import { formatSize } from '../utils/formatters';

interface FileViewerProps {
  sessionId: string;
  filePath: string;
}

const IMAGE_EXTENSIONS = new Set(['.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp', '.ico']);

function getExtension(path: string): string {
  const dot = path.lastIndexOf('.');
  return dot >= 0 ? path.substring(dot).toLowerCase() : '';
}

export default function FileViewer({ sessionId, filePath }: FileViewerProps) {
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [fileSize, setFileSize] = useState<number | null>(null);

  const isImage = IMAGE_EXTENSIONS.has(getExtension(filePath));
  const fileUrl = `/sessions/${sessionId}/files/${filePath}`;

  useEffect(() => {
    if (isImage) {
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);
    fetch(fileUrl)
      .then(async (res) => {
        if (!res.ok) throw new Error(`${res.status}`);
        const size = res.headers.get('content-length');
        if (size) setFileSize(parseInt(size));
        return res.text();
      })
      .then((text) => {
        setContent(text);
        if (!fileSize) setFileSize(new Blob([text]).size);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, [fileUrl, isImage]);

  const fileName = filePath.split('/').pop() || filePath;
  const isJson = getExtension(filePath) === '.json';

  let displayContent = content;
  if (isJson && content) {
    try {
      displayContent = JSON.stringify(JSON.parse(content), null, 2);
    } catch {
      // keep raw
    }
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-4 py-2 bg-surface border-b border-border">
        <div className="flex items-center gap-2 text-sm">
          <span className="text-text-muted">📄</span>
          <span className="font-mono text-text-primary">{filePath}</span>
        </div>
        {fileSize != null && (
          <span className="text-text-muted text-xs">{formatSize(fileSize)}</span>
        )}
      </div>

      <div className="flex-1 overflow-auto p-4">
        {loading && <div className="text-text-muted text-sm">Loading...</div>}
        {error && <div className="text-error text-sm">Error loading file: {error}</div>}

        {isImage && (
          <div className="flex justify-center">
            <img src={fileUrl} alt={fileName} className="max-w-full max-h-[600px] rounded" />
          </div>
        )}

        {!isImage && displayContent != null && (
          <pre className="text-sm font-mono leading-relaxed whitespace-pre-wrap break-words text-text-primary bg-body rounded-lg p-4 overflow-auto">
            {displayContent}
          </pre>
        )}
      </div>
    </div>
  );
}
