import type { HTMLAttributes, ReactNode } from 'react';
import { Badge, type BadgeTone } from './Badge';
export interface StatCardProps extends HTMLAttributes<HTMLDivElement> {
  label: string; value: ReactNode; icon?: ReactNode; status?: string; statusTone?: BadgeTone;
}
export function StatCard({ label, value, icon, status, statusTone = 'success', className = '', ...rest }: StatCardProps) {
  return <div {...rest} className={`p-4 rounded-lg bg-app/60 border border-line ${className}`}>
    <div className="flex flex-wrap items-center justify-between gap-2">
      <span className="text-sm font-semibold text-muted flex items-center gap-1.5">{icon}{label}</span>
      {status && <Badge tone={statusTone}>{status}</Badge>}
    </div><div className="mt-3 text-2xl font-bold text-fg">{value}</div>
  </div>;
}
