export interface Result<T> {
  ok: boolean;
  status: number;
  value: T;
}
