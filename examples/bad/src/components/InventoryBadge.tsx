import { HttpError } from '../../errors';

export interface ReorderCandidate {
  sku: string;
  onHand: number;
  reorderPoint: number;
}

export function needsReorder(candidate: ReorderCandidate): boolean {
  return candidate.onHand <= candidate.reorderPoint;
}

export function assertCandidate(candidate: ReorderCandidate): void {
  if (!candidate.sku) {
    throw new HttpError(400, 'sku is required');
  }
}
