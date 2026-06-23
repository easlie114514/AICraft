import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'

interface Props {
  content: string
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        code({ className, children, ...props }) {
          const match = /language-(\w+)/.exec(className || '')
          const codeStr = String(children).replace(/\n$/, '')
          if (match) {
            return (
              <div className="my-2 rounded-lg overflow-hidden border border-border">
                <div className="bg-muted px-3 py-1.5 text-xs text-muted-foreground font-medium">
                  {match[1]}
                </div>
                <SyntaxHighlighter
                  style={vscDarkPlus}
                  language={match[1]}
                  PreTag="div"
                  customStyle={{
                    margin: 0,
                    borderRadius: 0,
                    fontSize: '0.8125rem',
                    padding: '0.75rem 1rem',
                  }}
                >
                  {codeStr}
                </SyntaxHighlighter>
              </div>
            )
          }
          return (
            <code className="bg-muted px-1.5 py-0.5 rounded-md text-xs font-mono" {...props}>
              {children}
            </code>
          )
        },
        pre({ children }) {
          return <>{children}</>
        },
        p({ children }) {
          return <p className="mb-1.5 last:mb-0">{children}</p>
        },
        ul({ children }) {
          return <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>
        },
        ol({ children }) {
          return <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>
        },
        blockquote({ children }) {
          return (
            <blockquote className="border-l-3 border-primary/20 pl-3 my-1.5 text-text-secondary">
              {children}
            </blockquote>
          )
        },
        a({ href, children }) {
          return (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
              {children}
            </a>
          )
        },
        table({ children }) {
          return (
            <div className="overflow-auto my-2">
              <table className="min-w-full border-collapse border border-border text-xs">
                {children}
              </table>
            </div>
          )
        },
        th({ children }) {
          return <th className="border border-border px-2 py-1 bg-muted font-medium">{children}</th>
        },
        td({ children }) {
          return <td className="border border-border px-2 py-1">{children}</td>
        },
      }}
    >
      {content}
    </ReactMarkdown>
  )
}
