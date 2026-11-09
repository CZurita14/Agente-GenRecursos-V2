export interface FileRejection {
  file: File;
  code: 'too-many-files' | 'invalid-type' | 'too-large';
  message: string;
}
export interface FileRules { accept?: string; multiple?: boolean; maxSize?: number }

/** Validación de interfaz. El servidor también debe validar contenido y tamaño. */
export function validateFiles(files: File[], { accept, multiple = false, maxSize }: FileRules = {}) {
  const accepted: File[] = [];
  const rejected: FileRejection[] = [];
  const types = accept?.split(',').map(type => type.trim().toLowerCase()).filter(Boolean) ?? [];
  if (!multiple && files.length > 1) {
    return { accepted, rejected: files.map(file => ({ file, code: 'too-many-files' as const, message: 'Selecciona un solo archivo.' })) };
  }
  for (const file of files) {
    const matches = !types.length || types.some(type =>
      type.startsWith('.') ? file.name.toLowerCase().endsWith(type) :
      type.endsWith('/*') ? file.type.toLowerCase().startsWith(type.slice(0, -1)) :
      file.type.toLowerCase() === type);
    if (!matches) rejected.push({ file, code: 'invalid-type', message: 'Tipo de archivo no permitido.' });
    else if (maxSize !== undefined && file.size > maxSize) rejected.push({ file, code: 'too-large', message: `El archivo supera ${maxSize} bytes.` });
    else accepted.push(file);
  }
  return { accepted, rejected };
}
