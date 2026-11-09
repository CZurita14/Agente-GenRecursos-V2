import type { HTMLAttributes, ReactNode } from 'react';
export type BadgeTone = 'neutral' | 'brand' | 'highlight' | 'success' | 'warning' | 'danger' | 'info';
export interface BadgeProps extends HTMLAttributes<HTMLSpanElement> { tone?: BadgeTone; icon?: ReactNode }
const tones = {
  neutral: 'bg-app-soft text-muted border-line',
  brand: 'bg-brand-soft text-brand border-transparent',
  highlight: 'bg-highlight-soft text-action-ink border-transparent',
  success: 'bg-success-soft text-success border-transparent',
  warning: 'bg-warning-soft text-warning border-transparent',
  danger: 'bg-danger-soft text-danger border-transparent',
  info: 'bg-info-soft text-info border-transparent',
};
export function Badge({ tone = 'neutral', icon, children, className = '', ...rest }: BadgeProps) {
  return <span {...rest} className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full border text-xs font-bold ${tones[tone]} ${className}`}>{icon}{children}</span>;
}
