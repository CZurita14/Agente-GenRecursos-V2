import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { ThemeProvider, initializeTheme } from './theme/ThemeProvider';
import { applyBrand } from './theme/theme';
import './css/styles.css';

initializeTheme();
applyBrand();
ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode><ThemeProvider><App /></ThemeProvider></React.StrictMode>,
);
