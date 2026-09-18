import { badRequest, HttpError } from '../errors';
import { get } from './client';

export interface Order {
  id: string;
  totalCents: number;
}

export async function fetchOrder(orderId: string): Promise<Order> {
  if (!orderId) {
    throw badRequest('orderId is required');
  }
  const result = await get<Order>(`/orders/${orderId}`);
  if (!result.ok) {
    throw new HttpError(result.status, 'order lookup failed');
  }
  return result.value;
}
