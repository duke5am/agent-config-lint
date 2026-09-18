/** Tests for the inventory badge helper. */

import { needsReorder } from '../src/components/InventoryBadge';

test('flags a sku at its reorder point', () => {
  expect(needsReorder({ sku: 'sku-1', onHand: 3, reorderPoint: 3 })).toBe(true);
});

test('ignores a sku above its reorder point', () => {
  expect(needsReorder({ sku: 'sku-2', onHand: 9, reorderPoint: 3 })).toBe(false);
});
