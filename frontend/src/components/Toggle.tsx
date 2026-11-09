import { forwardRef, type InputHTMLAttributes } from 'react';

export interface ToggleProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'onChange' | 'checked' | 'defaultChecked'> {
  checked: boolean;
  onChange: (checked: boolean) => void;
  label?: string;
}
export const Toggle = forwardRef<HTMLInputElement, ToggleProps>(function Toggle({ checked, onChange, label, className = '', disabled, ...rest }, ref) {
  return <label className={`inline-flex items-center gap-3 ${disabled ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer'}`}>
    <span className="relative inline-flex items-center">
      <input {...rest} ref={ref} disabled={disabled} type="checkbox" checked={checked}
        onChange={e => onChange(e.target.checked)} className={`sr-only peer ${className}`} />
      <span aria-hidden="true" className="w-11 h-6 bg-line rounded-full peer-focus-visible:ring-2 peer-focus-visible:ring-action-ink peer-focus-visible:ring-offset-2 peer-checked:bg-action after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:after:translate-x-full" />
    </span>
    {label && <span className="text-sm font-medium text-fg">{label}</span>}
  </label>;
});
