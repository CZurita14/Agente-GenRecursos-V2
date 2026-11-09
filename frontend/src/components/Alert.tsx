import type { HTMLAttributes } from 'react';
import { CheckCircle2, AlertCircle, AlertTriangle, Info } from 'lucide-react';
export type AlertTone = 'success' | 'warning' | 'danger' | 'info';
export interface AlertProps extends HTMLAttributes<HTMLDivElement> { tone?: AlertTone }
const styles = {
  success: { box: 'bg-success-soft text-success border-success/30', Icon: CheckCircle2 },
  warning: { box: 'bg-warning-soft text-warning border-warning/30', Icon: AlertTriangle },
  danger: { box: 'bg-danger-soft text-danger border-danger/30', Icon: AlertCircle },
  info: { box: 'bg-info-soft text-info border-info/30', Icon: Info },
};
export function Alert({ tone = 'info', children, className = '', role = 'status', ...rest }: AlertProps) {
  const { box, Icon } = styles[tone];
  return <div {...rest} role={role} className={`p-3 rounded-lg border flex items-start gap-2 text-sm font-medium ${box} ${className}`}>
    <Icon aria-hidden="true" className="w-4 h-4 mt-0.5 shrink-0" /><div>{children}</div>
  </div>;
}
