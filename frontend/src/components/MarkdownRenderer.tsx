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
  /** 是否正在流式输出中。从 true→false 时触发 StreamMD 完整重解析 */
  streaming?: boolean
}

/**
 * 修复 LLM 输出中常见的 Markdown 语法不严谨问题，
 * 避免 StreamMD 因严格解析而将表格/标题/列表显示为纯文本。
 */
function normalizeMarkdown(text: string): string {
  // ── 0. 剥离 [EMOTION:xxx] 标记（仅移除标签本身，保留前后换行/空白）──
  text = text.replace(/\[EMOTION:\w+\]/g, '')

  // ── 预处理：标题/列表修复 + 多头标记拆分 ──
  // 循环直到稳定：每次迭代修复行首标题空格→拆分内嵌标题→下一次迭代再修复新露出的行首标题

  // 1. 列表标记缺空格（先做，不受循环影响）：-text → - text
  text = text.replace(/^(\s*[-*+])([^\s\-*+])/gm, '$1 $2')

  let prev = ''
  while (prev !== text) {
    prev = text

    // 1. 行首标题缺空格：###text → ### text
    text = text.replace(/^(#{1,6})([^\s#])/gm, '$1 $2')

    // 2. 同行内嵌标题拆分（两种模式都覆盖）：
    //    模式 A：前标题 "## 几点建议" + 后标题有空格 "### 1️⃣" → 拆分
    text = text.replace(/^(#{1,6}\s.+?)(?=#{1,6}\s)/gm, '$1\n')
    //    模式 B：前标题 "## 几点建议" + 后标题缺空格 "###1️⃣" → 拆分
    text = text.replace(/^(#{1,6}\s.+?)(?=#{1,6}[^\s#])/gm, '$1\n')
  }

  // ── 逐行处理（表格相关）──
  const lines = text.split('\n')
  const result: string[] = []

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i]

    // 空行直接透传
    if (line.trim() === '') {
      result.push(line)
      continue
    }

    // ── Markdown 标题 + 表格挤在同一行 ──
    // "## 标题| col1 | col2 |\n|:---|:---|" → "## 标题\n\n| col1 | col2 |\n|:---|:---|"
    const hMatch = line.match(/^(#{1,6}\s)(.+)$/)
    if (hMatch) {
      const rest = hMatch[2]
      // 标题 + 表格同行
      const pipeMatch = rest.match(/^(.+?)\s*(\|.+\|)\s*$/)
      if (pipeMatch) {
        result.push(hMatch[1] + pipeMatch[1].trimEnd())
        result.push('')
        result.push(pipeMatch[2])
        continue
      }
      // 标题 + 列表同行："### 📍贴士- 第一次来：...- 避坑：..."
      const dashIdx = rest.indexOf('- ')
      if (dashIdx > 0) {
        result.push(hMatch[1] + rest.slice(0, dashIdx).trimEnd())
        const listPart = rest.slice(dashIdx)
        const items = listPart.split(/(?=- )/g).filter(s => s.trim())
        result.push(...items)
        continue
      }
      result.push(line)
      continue
    }

    // ── 普通文本 + 表格挤在同一行 ──
    // "📅一览|日期|天气|" → "📅一览\n\n|日期|天气|"
    if (!line.startsWith('|') && line.includes('|')) {
      const firstPipe = line.indexOf('|')
      const before = line.slice(0, firstPipe).trimEnd()
      const after = line.slice(firstPipe)
      if (before.length > 0) {
        result.push(before)
        result.push('')
        result.push(after)
        continue
      }
    }

    // ── 表头 + 分隔行挤在同一行（|| 黏连）──
    // "|日期|天气||------|------|" → "|日期|天气|\n|------|------|"
    if (line.startsWith('|') && line.includes('||')) {
      const ddIdx = line.indexOf('||')
      const header = line.slice(0, ddIdx)
      const sep = '|' + line.slice(ddIdx + 2) // 跳过两个 ||，补回开头的 |
      if (header.includes('|') && /^\|[-:| ]+\|$/.test(sep)) {
        result.push(header)
        result.push(sep)
        continue
      }
    }

    // ── 同行内嵌多个列表项：拆分为独立行 ──
    // "🔥火锅类- 成都火锅...- 串串香..." → "🔥火锅类\n- 成都火锅...\n- 串串香..."
    // "- 🔥 高温...- ☔ 多雨..."        → "- 🔥 高温...\n- ☔ 多雨..."
    if ((line.match(/- /g) || []).length >= 2) {
      const items = line.split(/(?=- )/g).filter(s => s.trim())
      if (items.length >= 2) {
        result.push(...items)
        continue
      }
    }

    // ── 表格行紧跟前一行非空内容，缺空行 ──
    // "文本\n|表头|\n|---|" → "文本\n\n|表头|\n|---|"
    if (line.trim().startsWith('|') && result.length > 0) {
      const prev = result[result.length - 1]
      if (prev.trim() !== '' && !prev.includes('|')) {
        result.push('')
      }
    }

    result.push(line)
  }

  return result.join('\n')
}

export default function MarkdownRenderer({ content, streaming }: Props) {
  const streamKey = streaming ? 'streaming' : `done-${content.length}`

  return (
    <StreamMD
      key={streamKey}
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
          <p className="mb-1.5 last:mb-0 whitespace-pre-line">{children}</p>
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
