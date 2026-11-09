import { useId, useState, type HTMLAttributes, type ReactNode } from 'react';
import { Sun, Moon, Menu, X } from 'lucide-react';
import { BRAND_CONFIG, type BrandConfig } from '../theme/theme';

export interface NavItem { id: string; label: string; icon?: ReactNode; href?: string }
export interface NavbarProps extends Omit<HTMLAttributes<HTMLElement>, 'onChange'> {
  isDarkMode: boolean;
  onToggleTheme: () => void;
  brand?: BrandConfig;
  items?: readonly NavItem[];
  activeId?: string;
  onChange?: (id: string) => void;
  actions?: ReactNode;
}
export function Navbar({ isDarkMode, onToggleTheme, brand = BRAND_CONFIG, items = [], activeId, onChange, actions, className = '', ...rest }: NavbarProps) {
  const [expanded, setExpanded] = useState(false);
  const menuId = useId();
  const toggleLabel = isDarkMode ? 'Cambiar a modo claro' : 'Cambiar a modo oscuro';
  const navigation = items.map(item => {
    const props = {
      className: `flex items-center gap-2 px-3 py-2 rounded-lg font-medium text-sm ${activeId === item.id ? 'bg-action text-white' : 'text-header-muted hover:bg-header-border hover:text-white'}`,
      onClick: () => { onChange?.(item.id); setExpanded(false); },
      'aria-current': activeId === item.id ? 'page' as const : undefined,
      children: <>{item.icon}<span>{item.label}</span></>,
    };
    return item.href ? <a key={item.id} href={item.href} {...props} /> : <button key={item.id} type="button" {...props} />;
  });
  return <header {...rest} className={`bg-header text-white shadow-md border-b border-header-border ${className}`}>
    <div className="max-w-[1500px] mx-auto px-4 sm:px-6">
      <div className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div className="flex items-center gap-3 min-w-0 flex-1">
          <img src={brand.logoPath} alt={brand.institution} className="h-10 w-auto max-w-24 object-contain shrink-0" />
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-bold text-base break-words">{brand.appTitle}</span>
              {brand.version && <span className="bg-action text-white text-[10px] font-bold px-2 py-0.5 rounded-full">{brand.version}</span>}
            </div>
            <p className="text-xs text-header-muted mt-1 break-words">{brand.appSubtitle}</p>
          </div>
        </div>
        <nav aria-label="Navegación principal" className="hidden lg:flex flex-wrap items-center gap-2">{navigation}</nav>
        <div className="flex flex-wrap items-center gap-2">
          {actions}
          <button type="button" onClick={onToggleTheme} className="p-2 rounded-lg border border-header-border bg-header-soft" aria-label={toggleLabel} title={toggleLabel}>
            {isDarkMode ? <Sun aria-hidden="true" className="w-5 h-5" /> : <Moon aria-hidden="true" className="w-5 h-5" />}
          </button>
          {items.length > 0 && <button type="button" className="p-2 rounded-lg lg:hidden border border-header-border" aria-expanded={expanded} aria-controls={menuId} aria-label={expanded ? 'Cerrar navegación' : 'Abrir navegación'} onClick={() => setExpanded(value => !value)}>
            {expanded ? <X aria-hidden="true" className="w-5 h-5" /> : <Menu aria-hidden="true" className="w-5 h-5" />}
          </button>}
        </div>
      </div>
      <nav id={menuId} aria-label="Navegación móvil" hidden={!expanded} className="lg:hidden pb-4 space-y-1"
        onKeyDown={event => { if (event.key === 'Escape') { setExpanded(false); document.querySelector<HTMLButtonElement>(`[aria-controls="${menuId}"]`)?.focus(); } }}>{navigation}</nav>
    </div>
  </header>;
}
