import { useState } from 'react';
import { ExternalLink, ChevronDown, ChevronRight } from 'lucide-react';

interface Props {
  source: {
    id: number;
    title: string;
    author?: string;
    organization?: string;
    date?: string;
    url?: string;
    license?: string;
    excerpt?: string;
  };
}

export function SourceCard({ source }: Props) {
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="bg-gray-50 border border-gray-200 rounded p-3 text-sm">
      <div className="flex items-start justify-between">
        <div>
          <p className="font-medium text-gray-800">{source.title}</p>
          {(source.author || source.organization) && (
            <p className="text-gray-600 text-xs">
              {source.author || source.organization}
              {source.date && ` · ${source.date}`}
            </p>
          )}
        </div>
        <button
          onClick={() => setExpanded(!expanded)}
          className="text-gray-400 hover:text-gray-600"
        >
          {expanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        </button>
      </div>

      {expanded && source.excerpt && (
        <div className="mt-2 p-2 bg-white border rounded text-xs text-gray-700 italic">
          "{source.excerpt}"
        </div>
      )}

      {source.url && (
        <a
          href={source.url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center mt-2 text-xs text-blue-600 hover:underline"
        >
          View source <ExternalLink className="w-3 h-3 ml-1" />
        </a>
      )}

      {source.license && (
        <span className="inline-block mt-2 text-xs text-gray-500">
          License: {source.license}
        </span>
      )}
    </div>
  );
}
