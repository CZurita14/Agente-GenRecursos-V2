import { createContext, useContext, useEffect, useLayoutEffect, useState, type ReactNode } from 'react';
import type { ThemePreference, ThemeType } from './theme';

export const THEME_STORAGE_KEY = 'uti-theme';
const mediaQuery = '(prefers-color-scheme: dark)';
function readPreference(): ThemePreference {
  try {
    const value = localStorage.getItem(THEME_STORAGE_KEY);
    return value === 'light' || value === 'dark' ? value : 'system';
  } catch { return 'system'; }
}
function systemTheme(): ThemeType { return window.matchMedia(mediaQuery).matches ? 'dark' : 'light'; }
function applyTheme(theme: ThemeType) {
  document.documentElement.classList.toggle('dark', theme === 'dark');
  document.documentElement.style.colorScheme = theme;
}
/** Ejecutar antes de montar React para aplicar la preferencia desde el primer render. */
export function initializeTheme() {
  const preference = readPreference();
  applyTheme(preference === 'system' ? systemTheme() : preference);
}
export interface ThemeContextValue {
  theme: ThemeType;
  preference: ThemePreference;
  isDarkMode: boolean;
  setPreference: (preference: ThemePreference) => void;
  toggleTheme: () => void;
}
const ThemeContext = createContext<ThemeContextValue | null>(null);
export function ThemeProvider({ children }: { children: ReactNode }) {
  const [preference, setState] = useState<ThemePreference>(readPreference);
  const [system, setSystem] = useState<ThemeType>(systemTheme);
  const theme = preference === 'system' ? system : preference;
  useLayoutEffect(() => { applyTheme(theme); }, [theme]);
  useEffect(() => {
    const media = window.matchMedia(mediaQuery);
    const syncSystem = () => setSystem(systemTheme());
    const syncStorage = (event: StorageEvent) => {
      if (event.key === THEME_STORAGE_KEY || event.key === null) setState(readPreference());
    };
    syncSystem();
    media.addEventListener('change', syncSystem);
    window.addEventListener('storage', syncStorage);
    return () => { media.removeEventListener('change', syncSystem); window.removeEventListener('storage', syncStorage); };
  }, []);
  function setPreference(value: ThemePreference) {
    setState(value);
    try { localStorage.setItem(THEME_STORAGE_KEY, value); } catch { /* La interfaz funciona sin almacenamiento. */ }
  }
  return <ThemeContext.Provider value={{ theme, preference, isDarkMode: theme === 'dark', setPreference,
    toggleTheme: () => setPreference(theme === 'dark' ? 'light' : 'dark') }}>{children}</ThemeContext.Provider>;
}
export function useTheme() {
  const context = useContext(ThemeContext);
  if (!context) throw new Error('useTheme debe usarse dentro de ThemeProvider.');
  return context;
}
