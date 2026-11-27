import type { ReactNode } from 'react';
import { Navbar, type NavbarProps } from './Navbar';
import { Footer } from './Footer';
import { useTheme } from '../theme/ThemeProvider';

export interface AppLayoutProps extends Omit<NavbarProps, 'isDarkMode' | 'onToggleTheme' | 'children'> {
  children: ReactNode;
  footer?: ReactNode;
  /** Pantallas de trabajo en columnas (el Proyecto Formativo): usan casi todo el ancho de la pantalla. */
  amplio?: boolean;
}
export function AppLayout({ children, footer, brand, amplio = false, ...navbar }: AppLayoutProps) {
  const { isDarkMode, toggleTheme } = useTheme();
  return <div className="min-h-screen flex flex-col bg-app text-fg">
    <a href="#main-content" className="skip-link">Saltar al contenido</a>
    <Navbar {...navbar} brand={brand} isDarkMode={isDarkMode} onToggleTheme={toggleTheme} amplio={amplio} />
    <main id="main-content" tabIndex={-1}
      className={`w-full flex-1 ${amplio ? 'max-w-[1920px]' : 'max-w-7xl'} mx-auto px-4 sm:px-6 lg:px-8 py-8 space-y-8`}>{children}</main>
    <Footer institution={brand?.institution}>{footer}</Footer>
  </div>;
}
