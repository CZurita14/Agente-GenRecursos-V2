import { isValidElement, type HTMLAttributes, type ReactNode } from 'react';

type FieldColumn<T> = { key: Extract<keyof T, string>; render?: (row: T) => ReactNode };
type ComputedColumn<T> = { key: string; render: (row: T) => ReactNode };
export type Column<T> = (FieldColumn<T> | ComputedColumn<T>) & { header: ReactNode; className?: string };
export interface DataTableProps<T> extends Omit<HTMLAttributes<HTMLDivElement>, 'onChange'> {
  columns: readonly Column<T>[];
  rows: readonly T[];
  rowKey: (row: T) => string | number;
  caption: string;
  onRowClick?: (row: T) => void;
  rowActionLabel?: (row: T) => string;
  emptyMessage?: string;
  loading?: boolean;
}
/** Los valores complejos requieren render explícito; nunca se imprimen objetos crudos. */
function cellValue(value: unknown): ReactNode {
  if (value == null) return '—';
  if (typeof value === 'string' || typeof value === 'number' || isValidElement(value)) return value;
  if (typeof value === 'boolean') return value ? 'Sí' : 'No';
  return '—';
}
export function DataTable<T extends object>({ columns, rows, rowKey, caption, onRowClick, rowActionLabel,
  emptyMessage = 'No hay datos para mostrar', loading = false, className = '', ...rest }: DataTableProps<T>) {
  return <div {...rest} aria-busy={loading} className={`bg-surface rounded-xl border border-line overflow-hidden shadow-sm ${className}`}>
    <div className="overflow-x-auto" role="region" aria-label={caption} tabIndex={0}>
      <table className="w-full text-sm text-left">
        <caption className="sr-only">{caption}</caption>
        <thead className="bg-app-soft text-muted text-xs uppercase tracking-wider"><tr>
          {columns.map(c => <th scope="col" key={c.key} className={`px-4 py-3 font-bold ${c.className ?? ''}`}>{c.header}</th>)}
          {onRowClick && <th scope="col" className="px-4 py-3">Acciones</th>}
        </tr></thead>
        <tbody className="divide-y divide-line">
          {loading || rows.length === 0 ? <tr><td colSpan={Math.max(1, columns.length + (onRowClick ? 1 : 0))} className="px-4 py-8 text-center text-muted">{loading ? 'Cargando datos…' : emptyMessage}</td></tr> :
            rows.map(row => <tr key={rowKey(row)} className="text-fg hover:bg-app-soft">
              {columns.map(c => <td key={c.key} className={`px-4 py-3 ${c.className ?? ''}`}>{c.render ? c.render(row) : cellValue(row[c.key as keyof T])}</td>)}
              {onRowClick && <td className="px-4 py-3"><button type="button" className="rounded px-2 py-1 text-action-ink font-semibold" onClick={() => onRowClick(row)} aria-label={rowActionLabel?.(row) ?? `Ver detalle de ${rowKey(row)}`}>Ver detalle</button></td>}
            </tr>)}
        </tbody>
      </table>
    </div>
    <p role="status" className="sr-only">{loading ? 'Cargando datos' : `${rows.length} registros`}</p>
  </div>;
}
