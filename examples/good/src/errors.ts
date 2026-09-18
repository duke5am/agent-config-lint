/**
 * Error type shared by the API handlers.
 *
 * Handlers throw `HttpError` so the request wrapper can turn it into a
 * response without every handler repeating the status-code mapping.
 */
export class HttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
  }
}

export function badRequest(message: string): HttpError {
  return new HttpError(400, message);
}
