/**
 * Renders lightweight inline markdown (**bold**, *italic*) for assistant chat copy.
 */
export function MarkdownText({ text, className }) {
  if (!text) return null;

  const nodes = [];
  const re = /(\*\*[^*]+\*\*|\*[^*]+\*|[^*]+)/g;
  let match;
  while ((match = re.exec(text)) !== null) {
    const part = match[0];
    if (!part) continue;
    const key = nodes.length;
    if (part.startsWith("**") && part.endsWith("**")) {
      nodes.push(<strong key={key}>{part.slice(2, -2)}</strong>);
    } else if (part.startsWith("*") && part.endsWith("*")) {
      nodes.push(<em key={key}>{part.slice(1, -1)}</em>);
    } else {
      nodes.push(<span key={key}>{part}</span>);
    }
  }

  return <span className={className}>{nodes}</span>;
}
