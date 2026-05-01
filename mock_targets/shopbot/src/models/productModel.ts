import { getDb } from '../database/db';
import { Product } from '../types';

interface RawProduct {
  id: string;
  name: string;
  category: string;
  price: number;
  stock: number;
  rating: number;
  description: string;
  tierRequired: string;
}

function mapRow(row: RawProduct): Product {
  return { ...row };
}

function escapeLike(s: string): string {
  return s.replace(/\\/g, '\\\\').replace(/%/g, '\\%').replace(/_/g, '\\_');
}

export function searchProducts(query: string, category?: string): Product[] {
  const pattern = `%${escapeLike(query)}%`;
  if (category && category.trim()) {
    return getDb()
      .prepare<[string, string, string], RawProduct>(`
        SELECT id, name, category, price, stock, rating, description,
               tier_required as tierRequired
        FROM products
        WHERE (name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\') AND category = ?
        ORDER BY rating DESC
        LIMIT 10
      `)
      .all(pattern, pattern, category.trim())
      .map(mapRow);
  }
  return getDb()
    .prepare<[string, string], RawProduct>(`
      SELECT id, name, category, price, stock, rating, description,
             tier_required as tierRequired
      FROM products
      WHERE name LIKE ? ESCAPE '\\' OR description LIKE ? ESCAPE '\\'
      ORDER BY rating DESC
      LIMIT 10
    `)
    .all(pattern, pattern)
    .map(mapRow);
}

export function getTopRatedProducts(tier: string, limit = 6): Product[] {
  const tierRank: Record<string, number> = { REGULAR: 0, SILVER: 1, GOLD: 2, VIP: 3 };
  const userRank = tierRank[tier] ?? 0;
  const eligible = Object.entries(tierRank)
    .filter(([, rank]) => rank <= userRank)
    .map(([t]) => t);
  const placeholders = eligible.map(() => '?').join(',');
  return getDb()
    .prepare<unknown[], RawProduct>(`
      SELECT id, name, category, price, stock, rating, description,
             tier_required as tierRequired
      FROM products
      WHERE tier_required IN (${placeholders})
      ORDER BY rating DESC
      LIMIT ?
    `)
    .all([...eligible, limit])
    .map(mapRow);
}
