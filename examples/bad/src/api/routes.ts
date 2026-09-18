import { HttpError } from '../errors';
import { get } from './client';

export interface Order {
  id: string;
  totalCents: number;
}

/** Look up one order. Throws HttpError when the upstream refuses the call. */
export async function fetchOrder(orderId: string): Promise<Order> {
  const result = await get<Order>(`/orders/${orderId}`);
  if (!result.ok) {
    throw new HttpError(result.status, 'order lookup failed');
  }
  return result.value;
}
