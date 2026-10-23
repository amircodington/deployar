import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

// The assistant writes Markdown; raw HTML in it is not rendered (react-markdown's default), so a
// model reply can't inject markup. Code, URLs and env names stay LTR inside Persian text (brand voice).
const C: Components = {
  p: ({ children }) => <p className="mb-2 last:mb-0">{children}</p>,
  strong: ({ children }) => <strong className="font-semibold text-ink">{children}</strong>,
  em: ({ children }) => <em className="text-ink-muted not-italic">{children}</em>,
  h1: ({ children }) => <h3 className="mb-2 mt-3 text-[17px] font-bold first:mt-0">{children}</h3>,
  h2: ({ children }) => <h3 className="mb-2 mt-3 text-[16px] font-bold first:mt-0">{children}</h3>,
  h3: ({ children }) => <h4 className="mb-1.5 mt-3 text-[15px] font-semibold first:mt-0">{children}</h4>,
  ul: ({ children }) => <ul className="mb-2 list-disc space-y-1 ps-5 marker:text-ink-faint last:mb-0">{children}</ul>,
  ol: ({ children }) => <ol className="mb-2 list-decimal space-y-1 ps-5 marker:text-ink-faint last:mb-0">{children}</ol>,
  li: ({ children }) => <li className="ps-1">{children}</li>,
  a: ({ href, children }) => (
    <a href={href} target="_blank" rel="noopener noreferrer" className="text-mint underline decoration-mint/40 underline-offset-4 hover:decoration-mint">
      {children}
    </a>
  ),
  code: ({ className, children }) =>
    className ? (
      <code className={className}>{children}</code>
    ) : (
      <code dir="ltr" className="mono rounded-md bg-raised px-1.5 py-0.5 text-[13px] [unicode-bidi:isolate]">
        {children}
      </code>
    ),
  pre: ({ children }) => (
    <pre dir="ltr" className="mono scroll-thin mb-2 overflow-x-auto rounded-2xl bg-raised p-3 text-[13px] leading-5 last:mb-0">
      {children}
    </pre>
  ),
  blockquote: ({ children }) => (
    <blockquote className="mb-2 border-s-2 border-amber/60 ps-3 text-ink-muted last:mb-0">{children}</blockquote>
  ),
  hr: () => <hr className="my-3 border-line" />,
  table: ({ children }) => (
    <div className="scroll-thin mb-2 overflow-x-auto last:mb-0">
      <table className="w-full border-collapse text-[14px]">{children}</table>
    </div>
  ),
  th: ({ children }) => <th className="border-b border-line px-2 py-1.5 text-start font-medium text-ink-muted">{children}</th>,
  td: ({ children }) => <td className="border-b border-line/60 px-2 py-1.5 align-top">{children}</td>,
};

export function Markdown({ text }: { text: string }) {
  return (
    <ReactMarkdown remarkPlugins={[remarkGfm]} components={C}>
      {text}
    </ReactMarkdown>
  );
}
