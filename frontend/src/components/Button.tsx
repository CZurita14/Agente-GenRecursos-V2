import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
  icon?: ReactNode;
  loading?: boolean;
}
const variants = {
  primary: 'bg-action hover:bg-action-hover text-white shadow-sm',
  secondary: 'bg-surface border border-line text-fg hover:bg-app-soft',
  ghost: 'text-muted hover:text-fg hover:bg-app-soft',
  danger: 'bg-destructive text-white hover:opacity-90 shadow-sm',
};
const sizes = { sm: 'px-3 py-1.5 text-xs', md: 'px-4 py-2 text-sm' };
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(function Button({
  variant = 'primary', size = 'md', type = 'button', icon, loading = false,
  disabled, className = '', children, ...rest
}, ref) {
  return <button {...rest} ref={ref} type={type} disabled={disabled || loading}
    aria-busy={loading || rest['aria-busy']}
    className={`inline-flex items-center justify-center gap-1.5 rounded-lg font-semibold transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${variants[variant]} ${sizes[size]} ${className}`}>
    {loading ? <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-current border-r-transparent" /> : icon}
    {children}
  </button>;
});
