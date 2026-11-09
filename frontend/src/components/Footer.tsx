import type { HTMLAttributes } from 'react';
import { BRAND_CONFIG } from '../theme/theme';
export interface FooterProps extends HTMLAttributes<HTMLElement> { institution?: string }
export function Footer({ children, institution = BRAND_CONFIG.institution, className = '', ...rest }: FooterProps) {
  return <footer {...rest} className={`border-t border-line px-4 py-6 text-center text-xs text-muted ${className}`}>
    {children ?? `${institution} © ${new Date().getFullYear()}`}
  </footer>;
}
