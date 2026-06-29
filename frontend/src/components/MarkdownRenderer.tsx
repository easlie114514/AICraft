import { StreamMD } from 'stream-md'
import { Prism as SyntaxHighlighter } from 'react-syntax-highlighter'
import { vscDarkPlus } from 'react-syntax-highlighter/dist/esm/styles/prism'
import type {
  BlockComponentProps,
  CodeBlockProps,
  ListBlockProps,
  TableBlockProps,
  LinkProps,
  InlineCodeProps,
  ImageProps,
} from 'stream-md'

interface Props {
  content: string
}

/**
 * 修复 LLM 输出中常见的 Markdown 语法不严谨问题，
 * 避免 StreamMD 因严格解析而将表格/标题显示为纯文本。
 */
function normalizeMarkdown(text: string): string {
  // 1. 修复标题标记后缺少空格：##text → ## text
  text = text.replace(/^(#{1,6})([^\s#])/gm, '$1 $2')

  // 2. 修复标题行与表格内容挤在同一行：
  //    "## 标题| col1 | col2 |\n| --- | --- |" → "## 标题\n\n| col1 | col2 |\n| --- | --- |"
  //    按行扫描，发现标题行内含有表格分隔符（|---|---）时拆分为独立行
  const lines = text.split('\n')
  const result: string[] = []
  for (const line of lines) {
    const headingMatch = line.match(/^(#{1,6}\s)(.+)$/)
    if (headingMatch) {
      const afterHeading = headingMatch[2]
      // 标题文本后紧跟着表格内容（检测 GFM 表格分隔符 |---|）
      if (/\|[-| :]+\|/.test(afterHeading)) {
        const pipeIdx = afterHeading.indexOf('|')
        if (pipeIdx > 0) {
          result.push(headingMatch[1] + afterHeading.slice(0, pipeIdx).trimEnd())
          result.push('')
          result.push(afterHeading.slice(pipeIdx))
          continue
        }
      }
    }
    result.push(line)
  }
  return result.join('\n')
}

export default function MarkdownRenderer({ content }: Props) {
  return (
    <StreamMD
      text={normalizeMarkdown(content)}
      theme="none"
      showCursor={false}
      components={{
        // ── Headings ──
        h1: ({ children }: BlockComponentProps) => (
          <h1 className="text-xl font-bold mt-3 mb-1.5 text-text-primary">{children}</h1>
        ),
        h2: ({ children }: BlockComponentProps) => (
          <h2 className="text-lg font-semibold mt-2.5 mb-1 text-text-primary">{children}</h2>
        ),
        h3: ({ children }: BlockComponentProps) => (
          <h3 className="text-base font-semibold mt-2 mb-1 text-text-primary">{children}</h3>
        ),
        h4: ({ children }: BlockComponentProps) => (
          <h4 className="text-sm font-medium mt-1.5 mb-0.5 text-text-primary">{children}</h4>
        ),
        h5: ({ children }: BlockComponentProps) => (
          <h5 className="text-sm font-medium mt-1.5 mb-0.5 text-text-secondary">{children}</h5>
        ),
        h6: ({ children }: BlockComponentProps) => (
          <h6 className="text-xs font-medium mt-1 mb-0.5 text-text-secondary">{children}</h6>
        ),
        // ── Paragraph ──
        p: ({ children }: BlockComponentProps) => (
          <p className="mb-1.5 last:mb-0">{children}</p>
        ),
        // ── Code Block ──
        pre: ({ code, language, streaming }: CodeBlockProps) => {
          if (streaming) {
            // Don't highlight streaming code blocks — render as plain pre
            return (
              <div className="my-2 rounded-lg overflow-hidden border border-border">
                {language && (
                  <div className="bg-muted px-3 py-1.5 text-xs text-muted-foreground font-medium">
                    {language}
                  </div>
                )}
                <pre className="p-3 text-xs font-mono bg-[#1E1E1E] text-[#D4D4D4] overflow-auto max-h-96">
                  {code}
                </pre>
              </div>
            )
          }
          return (
            <div className="my-2 rounded-lg overflow-hidden border border-border">
              {language && (
                <div className="bg-muted px-3 py-1.5 text-xs text-muted-foreground font-medium">
                  {language}
                </div>
              )}
              <SyntaxHighlighter
                style={vscDarkPlus}
                language={language || 'text'}
                PreTag="div"
                customStyle={{
                  margin: 0,
                  borderRadius: 0,
                  fontSize: '0.8125rem',
                  padding: '0.75rem 1rem',
                }}
              >
                {code}
              </SyntaxHighlighter>
            </div>
          )
        },
        // ── Inline Code ──
        code: ({ children }: InlineCodeProps) => (
          <code className="bg-muted px-1.5 py-0.5 rounded-md text-xs font-mono">
            {children}
          </code>
        ),
        // ── Lists ──
        ul: ({ children }: ListBlockProps) => (
          <ul className="list-disc list-inside mb-1.5 space-y-0.5">{children}</ul>
        ),
        ol: ({ children }: ListBlockProps) => (
          <ol className="list-decimal list-inside mb-1.5 space-y-0.5">{children}</ol>
        ),
        // ── Blockquote ──
        blockquote: ({ children }: BlockComponentProps) => (
          <blockquote className="border-l-3 border-primary/20 pl-3 my-1.5 text-text-secondary">
            {children}
          </blockquote>
        ),
        // ── Link ──
        a: ({ href, children }: LinkProps) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-primary underline">
            {children}
          </a>
        ),
        // ── Table ──
        table: ({ headers, rows, alignments }: TableBlockProps) => (
          <div className="overflow-auto my-2">
            <table className="min-w-full border-collapse border border-border text-xs">
              <thead>
                <tr>
                  {headers.map((h, i) => (
                    <th
                      key={i}
                      className="border border-border px-2 py-1 bg-muted font-medium"
                      style={alignments[i] && alignments[i] !== 'none'
                        ? { textAlign: alignments[i] }
                        : undefined}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((row, ri) => (
                  <tr key={ri}>
                    {row.map((cell, ci) => (
                      <td
                        key={ci}
                        className="border border-border px-2 py-1"
                        style={alignments[ci] && alignments[ci] !== 'none'
                          ? { textAlign: alignments[ci] }
                          : undefined}
                      >
                        {cell}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ),
        // ── Horizontal Rule ──
        hr: () => <hr className="my-3 border-border" />,
        // ── Emphasis & Strong ──
        strong: ({ children }: { children: React.ReactNode }) => (
          <strong className="font-semibold">{children}</strong>
        ),
        em: ({ children }: { children: React.ReactNode }) => (
          <em className="italic">{children}</em>
        ),
        del: ({ children }: { children: React.ReactNode }) => (
          <del className="line-through text-text-secondary">{children}</del>
        ),
        // ── Image ──
        img: ({ src, alt, title }: ImageProps) => (
          <img
            src={src}
            alt={alt}
            title={title}
            className="max-w-full h-auto rounded-lg my-2"
          />
        ),
      }}
    />
  )
}
