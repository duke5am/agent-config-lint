import type { Result } from './types';

export async function get<T>(path: string): Promise<Result<T>> {
  const response = await fetch(`https://api.example.invalid${path}`, {
    headers: { accept: 'application/json' },
  });
  return {
    ok: response.ok,
    status: response.status,
    value: (await response.json()) as T,
  };
}
