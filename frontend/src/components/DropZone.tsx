import { useId, useRef, useState, type HTMLAttributes } from 'react';
import { Upload } from 'lucide-react';
import { validateFiles, type FileRejection } from '../utils/files';

export interface DropZoneProps extends Omit<HTMLAttributes<HTMLDivElement>, 'title' | 'onError'> {
  onFiles: (files: File[]) => void;
  onReject?: (rejections: FileRejection[]) => void;
  accept?: string;
  multiple?: boolean;
  maxSize?: number;
  disabled?: boolean;
  title?: string;
  hint?: string;
}
export function DropZone({ onFiles, onReject, accept, multiple = false, maxSize, disabled = false,
  title = 'Arrastra y suelta tus archivos aquí', hint = 'o selecciona los archivos',
  className = '', ...rest }: DropZoneProps) {
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<FileRejection[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);
  const hintId = useId();
  const errorId = useId();
  function emit(list: FileList | null) {
    if (disabled || !list?.length) return;
    const result = validateFiles(Array.from(list), { accept, multiple, maxSize });
    setErrors(result.rejected);
    if (result.rejected.length) onReject?.(result.rejected);
    if (result.accepted.length) onFiles(result.accepted);
  }
  return <div {...rest} className={`rounded-xl border-2 border-dashed p-6 sm:p-10 text-center transition-colors ${disabled ? 'opacity-50' : ''} ${dragging ? 'border-highlight bg-highlight-soft' : 'border-line bg-surface'} ${className}`}
    onDragOver={e => { rest.onDragOver?.(e); e.preventDefault(); if (!disabled) setDragging(true); }}
    onDragLeave={e => { rest.onDragLeave?.(e); if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setDragging(false); }}
    onDrop={e => { rest.onDrop?.(e); e.preventDefault(); setDragging(false); emit(e.dataTransfer.files); }}>
    <input ref={inputRef} type="file" accept={accept} multiple={multiple} disabled={disabled} tabIndex={-1}
      onChange={e => { emit(e.currentTarget.files); e.currentTarget.value = ''; }} className="hidden" />
    <Upload aria-hidden="true" className="w-10 h-10 mx-auto mb-3 text-highlight" />
    <p className="font-bold text-fg">{title}</p>
    <p id={hintId} className="text-xs text-muted mt-1">{hint}</p>
    <button type="button" disabled={disabled} aria-describedby={`${hintId}${errors.length ? ' ' + errorId : ''}`}
      onClick={() => inputRef.current?.click()} className="mt-4 rounded-lg px-4 py-2 bg-action text-white font-semibold text-sm disabled:cursor-not-allowed">
      Seleccionar archivos
    </button>
    <div id={errorId} aria-live="polite" className="mt-2 text-xs text-danger">
      {errors.map((item, i) => <p key={i}>{item.file.name}: {item.message}</p>)}
    </div>
  </div>;
}
