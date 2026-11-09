export interface BrandConfig {
  institution: string;
  appTitle: string;
  appSubtitle: string;
  version?: string;
  logoPath: string;
  faviconPath: string;
}
/** Los archivos públicos respetan la base de despliegue configurada en Vite. */
export const BRAND_CONFIG: BrandConfig = {
  institution: 'Universidad Tecnológica Indoamérica',
  appTitle: 'Recursos de estudio',
  appSubtitle: 'Generador de recursos · Universidad Tecnológica Indoamérica',
  version: 'v1.0',
  logoPath: `${import.meta.env.BASE_URL}logo-uti.png`,
  faviconPath: `${import.meta.env.BASE_URL}favicon.svg`,
};
export type ThemeType = 'light' | 'dark';
export type ThemePreference = ThemeType | 'system';

/** CSS es la única fuente de colores; útil para gráficos que necesiten un color en JS. */
export function getThemeColor(token: string): string {
  const channels = getComputedStyle(document.documentElement).getPropertyValue(`--uti-${token}`).trim();
  return channels ? `rgb(${channels})` : '';
}
export function applyBrand(brand: BrandConfig = BRAND_CONFIG) {
  document.title = brand.appTitle;
  const favicon = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (favicon) favicon.href = brand.faviconPath;
}
