import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react';

export interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  hint?: ReactNode;
  error?: ReactNode;
  containerClassName?: string;
}
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input({
  label, hint, error, id, className = '', containerClassName = '', ...rest
}, ref) {
  const generatedId = useId();
  const inputId = id ?? generatedId;
  const describedBy = [rest['aria-describedby'], hint ? `${inputId}-hint` : '', error ? `${inputId}-error` : ''].filter(Boolean).join(' ') || undefined;
  return <div className={containerClassName}>
    {label && <label htmlFor={inputId} className="block text-xs font-semibold text-muted mb-1">{label}</label>}
    <input {...rest} ref={ref} id={inputId} aria-invalid={error ? true : rest['aria-invalid']} aria-describedby={describedBy}
      className={`w-full px-3 py-2 bg-surface border rounded-md text-sm text-fg placeholder:text-muted disabled:opacity-50 disabled:cursor-not-allowed ${error ? 'border-danger' : 'border-line'} ${className}`} />
    {hint && <p id={`${inputId}-hint`} className="mt-1 text-xs text-muted">{hint}</p>}
    {error && <p id={`${inputId}-error`} className="mt-1 text-xs text-danger">{error}</p>}
  </div>;
});
