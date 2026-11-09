import type { HTMLAttributes, ReactNode } from 'react';
export interface CardProps extends Omit<HTMLAttributes<HTMLElement>, 'title'> {
  title?: string; description?: string; icon?: ReactNode; actions?: ReactNode;
}
export function Card({ title, description, icon, actions, className = '', children, ...rest }: CardProps) {
  return <section {...rest} className={`bg-surface rounded-xl border border-line p-4 sm:p-6 shadow-sm ${className}`}>
    {(title || description || icon || actions) && <div className="flex flex-wrap items-center justify-between gap-4 mb-5 pb-4 border-b border-line">
      <div className="flex items-center gap-3 min-w-0">
        {icon && <div aria-hidden="true" className="p-2.5 bg-app rounded-lg text-action-ink">{icon}</div>}
        <div className="min-w-0">{title && <h2 className="font-bold text-base text-fg break-words">{title}</h2>}
          {description && <p className="text-sm text-muted">{description}</p>}</div>
      </div>{actions}
    </div>}{children}
  </section>;
}
