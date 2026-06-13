import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { cn } from "@/lib/utils";

/** Render agent text as rich Markdown. react-markdown does NOT render raw HTML, so this is
 * XSS-safe; images (e.g. an asset preview_url) and links render normally. */
export function Markdown({ children, className }: { children: string; className?: string }) {
  return (
    <div className={cn("prose prose-invert prose-sm max-w-none break-words", className)}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noreferrer" />,
          img: ({ node: _node, ...props }) => (
            // Asset previews are same-origin (/api/assets/:id/content).
            // biome-ignore lint/a11y/useAltText: alt is passed through from the markdown when present
            <img {...props} className="max-h-72 rounded-md border border-border" />
          ),
        }}
      >
        {children}
      </ReactMarkdown>
    </div>
  );
}
