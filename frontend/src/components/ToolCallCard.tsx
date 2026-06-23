import { Wrench, ChevronDown } from 'lucide-react'
import { Card, CardContent } from '@/components/ui/card'
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible'
import { Badge } from '@/components/ui/badge'
import { useState } from 'react'

interface Props {
  name: string
  args?: Record<string, unknown>
  result?: string
}

export default function ToolCallCard({ name, args, result }: Props) {
  const [open, setOpen] = useState(false)

  return (
    <div className="flex justify-start py-1.5">
      <Card className="max-w-[85%] border-l-4 border-l-warning bg-warning-light/30 shadow-card">
        <Collapsible open={open} onOpenChange={setOpen}>
          <CollapsibleTrigger>
            <CardContent className="p-3 flex items-center gap-2 cursor-pointer hover:bg-muted/50 transition-colors">
              <Wrench className="h-4 w-4 text-muted-foreground shrink-0" />
              <span className="text-sm font-medium truncate">
                {args ? `调用工具: ${name}` : `工具结果: ${name}`}
              </span>
              <Badge variant="secondary" className="rounded-lg text-xs ml-auto shrink-0">
                {args ? '执行中' : '完成'}
              </Badge>
              <ChevronDown className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            </CardContent>
          </CollapsibleTrigger>
          <CollapsibleContent>
            <CardContent className="px-3 pb-3 pt-0 space-y-2">
              {args && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">参数</p>
                  <pre className="text-xs bg-muted p-2 rounded-lg overflow-auto max-h-32 font-mono whitespace-pre-wrap break-all">
                    {JSON.stringify(args, null, 2)}
                  </pre>
                </div>
              )}
              {result && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground mb-1">结果</p>
                  <pre className="text-xs bg-muted p-2 rounded-lg overflow-auto max-h-48 font-mono whitespace-pre-wrap break-all">
                    {result}
                  </pre>
                </div>
              )}
            </CardContent>
          </CollapsibleContent>
        </Collapsible>
      </Card>
    </div>
  )
}
