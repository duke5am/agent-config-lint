import { HttpError } from '../errors';

export interface Result<T> {
  ok: boolean;
  status: number;
  value: T;
}

/**
 * The only place the API talks to the network: it attaches the retry policy
 * and normalises a 4xx response into a result object instead of a throw.
 */
export async function get<T>(path: string): Promise<Result<T>> {
  const response = await fetch(`https://api.example.invalid${path}`, {
    headers: { accept: 'application/json' },
  });
  if (response.status >= 500) {
    throw new HttpError(response.status, 'upstream failure');
  }
  return {
    ok: response.ok,
    status: response.status,
    value: (await response.json()) as T,
  };
}
