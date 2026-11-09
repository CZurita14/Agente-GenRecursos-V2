import { useEffect, useId, useRef, type DialogHTMLAttributes, type ReactNode, type RefObject } from 'react';
import { createPortal } from 'react-dom';
import { X } from 'lucide-react';

export interface ModalProps extends Omit<DialogHTMLAttributes<HTMLDialogElement>, 'title' | 'onClose' | 'open'> {
  isOpen: boolean;
  onClose: () => void;
  title: string;
  icon?: ReactNode;
  footer?: ReactNode;
  closeOnBackdrop?: boolean;
  initialFocusRef?: RefObject<HTMLElement>;
}

/** El diálogo nativo gestiona foco, Escape y aislamiento del resto de la página. */
export function Modal({ isOpen, onClose, title, icon, footer, closeOnBackdrop = false, initialFocusRef,
  children, className = '', onClick, onCancel, onKeyDown, ...rest }: ModalProps) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    if (!isOpen || !ref.current) return;
    const dialog = ref.current;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    dialog.showModal();
    if (initialFocusRef?.current && dialog.contains(initialFocusRef.current)) initialFocusRef.current.focus();
    document.body.style.overflow = 'hidden';
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, [isOpen, initialFocusRef]);
  if (!isOpen) return null;
  return createPortal(<dialog {...rest} ref={ref} aria-labelledby={titleId} aria-modal="true" tabIndex={-1}
    className={`m-auto p-0 w-[calc(100%-2rem)] max-w-lg max-h-[calc(100dvh-2rem)] rounded-xl border border-line bg-surface text-fg shadow-2xl backdrop:bg-black/60 backdrop:backdrop-blur-sm ${className}`}
    onKeyDown={event => {
      onKeyDown?.(event);
      if (event.defaultPrevented || event.key !== 'Tab') return;
      const dialog = event.currentTarget;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button, a[href], input, select, textarea, [tabindex]'))
        .filter(node => node.tabIndex >= 0 && !node.matches(':disabled') && node.getClientRects().length > 0 && !node.closest('[inert]'));
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (!first) { event.preventDefault(); dialog.focus(); }
      else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog)) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }}
    onCancel={event => { onCancel?.(event); if (!event.defaultPrevented) { event.preventDefault(); onClose(); } }}
    onClick={event => {
      onClick?.(event);
      if (!closeOnBackdrop || event.defaultPrevented || event.target !== event.currentTarget) return;
      const rect = event.currentTarget.getBoundingClientRect();
      if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
    }}>
    <div className="flex max-h-[calc(100dvh-2rem)] flex-col">
      <div className="bg-header text-white p-5 flex shrink-0 items-center justify-between gap-3">
        <div className="flex items-center gap-2.5 min-w-0">
          {icon && <span aria-hidden="true" className="text-highlight">{icon}</span>}
          <h2 id={titleId} className="font-bold text-base break-words">{title}</h2>
        </div>
        <button type="button" onClick={onClose} className="text-header-muted hover:text-white p-1" aria-label="Cerrar diálogo"><X aria-hidden="true" className="w-5 h-5" /></button>
      </div>
      <div className="p-6 overflow-y-auto min-h-0">{children}</div>
      {footer && <div className="px-6 py-4 border-t border-line flex flex-wrap shrink-0 items-center justify-end gap-3">{footer}</div>}
    </div>
  </dialog>, document.body);
}
