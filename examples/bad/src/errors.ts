/* The shared error type. Handlers throw this and the request wrapper turns it
 * into a response, so handlers never build a status code themselves. */
export class HttpError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'HttpError';
    this.status = status;
  }
}
