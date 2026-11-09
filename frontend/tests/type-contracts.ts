import type { Column, ButtonProps, InputProps, ToggleProps } from '../src/components';

interface Row { id: number; name: string }
export const field: Column<Row> = { key: 'name', header: 'Nombre' };
export const computed: Column<Row> = { key: 'actions', header: 'Acciones', render: row => row.id };
// @ts-expect-error Una propiedad inexistente necesita render explícito.
export const invalid: Column<Row> = { key: 'naem', header: 'Nombre' };
export const button: ButtonProps = { type: 'submit', loading: true, 'aria-label': 'Enviar' };
export const input: InputProps = { name: 'email', error: 'Revisa el correo', 'aria-describedby': 'help' };
export const toggle: ToggleProps = { name: 'enabled', disabled: true, checked: true, onChange: () => {} };
// @ts-expect-error El componente administra el tipo checkbox.
export const invalidToggle: ToggleProps = { type: 'text', checked: true, onChange: () => {} };
