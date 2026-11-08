import { ClientError } from 'graphql-request';

export function errorCode(error: unknown): string | undefined {
  if (error instanceof ClientError) return error.response.errors?.[0]?.extensions?.code as string | undefined;
  return undefined;
}
export function readError(error: unknown): string {
  const code = errorCode(error);
  return ({
    NOT_FOUND: 'El recurso ya no está disponible.',
    VALIDATION_ERROR: 'Revisa los datos ingresados.',
    FORBIDDEN: 'El servicio rechazó esta operación.',
    CONFLICT: 'La operación entró en conflicto. Actualiza los datos.',
    GONE: 'El recurso ya no está disponible.',
    BAD_UPSTREAM_RESPONSE: 'El servicio devolvió una respuesta que no pudimos procesar.',
    NOT_IMPLEMENTED: 'Esta función todavía no está disponible.',
  } as Record<string, string>)[code ?? ''] ?? 'No pudimos conectar con el servicio. Intenta actualizar.';
}
export function writeError(error: unknown): string {
  if (['VALIDATION_ERROR', 'NOT_FOUND', 'FORBIDDEN', 'CONFLICT', 'GONE'].includes(errorCode(error) ?? '')) return readError(error);
  return 'No pudimos confirmar el envío. El resultado es incierto: actualiza el listado antes de repetirlo manualmente.';
}
export function chronological<T extends { id: string; createdAt: string }>(items: T[]): T[] {
  return [...new Map(items.map(item => [item.id, item])).values()].sort((a, b) =>
    Date.parse(a.createdAt) - Date.parse(b.createdAt) || a.id.localeCompare(b.id));
}

// Match Pydantic string lengths (Unicode code points, not UTF-16 units).
export const characterCount = (value: string) => Array.from(value).length;
