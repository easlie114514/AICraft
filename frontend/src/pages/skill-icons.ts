import {
  Code2,
  Languages,
  PenLine,
  BarChart3,
  UserCog,
  Gamepad2,
  Puzzle,
  type LucideIcon,
} from 'lucide-react'

/** 技能名称 → lucide 图标映射表，未匹配到则返回 Puzzle */
const SKILL_ICON_MAP: Record<string, LucideIcon> = {
  '代码审查': Code2,
  '翻译助手': Languages,
  '写作助手': PenLine,
  '数据分析': BarChart3,
  '角色设计师': UserCog,
  '逆转裁判': Gamepad2,
}

export function getSkillIcon(name: string): LucideIcon {
  return SKILL_ICON_MAP[name] ?? Puzzle
}

/** 根据技能名推断分类标签 */
export function getSkillCategory(name: string): string {
  if (name.includes('代码') || name.includes('审查')) return '开发'
  if (name.includes('翻译')) return '语言'
  if (name.includes('写作')) return '内容'
  if (name.includes('数据')) return '分析'
  if (name.includes('角色') || name.includes('设计')) return '创意'
  if (name.includes('逆转') || name.includes('游戏')) return '娱乐'
  return '通用'
}
