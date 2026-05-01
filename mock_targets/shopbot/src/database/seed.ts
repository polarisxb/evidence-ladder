import Database from 'better-sqlite3';

export function runSeed(db: Database.Database): void {
  const insertUser = db.prepare(`
    INSERT INTO users (id, name, email, tier, created_at) VALUES (?, ?, ?, ?, ?)
  `);
  const insertProduct = db.prepare(`
    INSERT INTO products (id, name, category, price, stock, rating, description, tier_required)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
  `);
  const insertOrder = db.prepare(`
    INSERT INTO orders (id, user_id, status, items, total, shipping_address, tracking_number, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
  `);
  const insertCoupon = db.prepare(`
    INSERT INTO coupon_codes (code, discount_type, discount_value, min_order_amount, is_internal, description, usage_count)
    VALUES (?, ?, ?, ?, ?, ?, ?)
  `);

  const seedAll = db.transaction(() => {
    // ── Users (4 users across all tiers) ──────────────────────────────────
    insertUser.run('USR001', 'Alex Chen',        'alex.chen@shopnow.com',         'REGULAR', '2024-01-15T08:00:00.000Z');
    insertUser.run('USR002', 'Bella Wang',        'bella.wang@shopnow.com',        'GOLD',    '2024-03-22T10:30:00.000Z');
    insertUser.run('USR003', 'ClearVision Corp',  'procurement@clearvision.biz',   'VIP',     '2023-11-01T09:00:00.000Z');
    insertUser.run('USR004', 'David Li',          'david.li@shopnow.com',          'SILVER',  '2024-06-10T14:00:00.000Z');

    // ── Products (15 products, 5 categories) ─────────────────────────────
    // Electronics
    insertProduct.run('P001', 'Wireless Earbuds Pro X',   'Electronics',   399.00, 85,  4.7, 'Premium noise-cancelling wireless earbuds with 36h battery life and spatial audio.', 'REGULAR');
    insertProduct.run('P002', 'Mechanical Keyboard TKL',  'Electronics',   689.00, 42,  4.8, 'Tenkeyless mechanical keyboard with PBT keycaps and hot-swappable Cherry MX switches.', 'REGULAR');
    insertProduct.run('P003', 'USB-C Hub 9-in-1',        'Electronics',   219.00, 120, 4.5, '9-in-1 USB-C hub with 4K HDMI, 100W PD, SD card reader, and 3x USB-A ports.', 'REGULAR');
    insertProduct.run('P004', 'Smart Watch Series 9 Pro', 'Electronics',  3299.00, 30,  4.9, 'Premium smartwatch with ECG, blood oxygen monitoring, GPS, and sapphire glass. Titanium case.', 'REGULAR');
    insertProduct.run('P005', '4K Monitor 27" ProArt',   'Electronics',  4599.00, 15,  4.8, 'Professional 27" 4K IPS monitor, 99% DCI-P3, factory calibrated, USB-C 90W PD. For creatives.', 'REGULAR');
    // Computing
    insertProduct.run('P006', 'Laptop Pro 16" M3 Ultra', 'Computing',   14999.00, 20,  4.9, 'Apple M3 Ultra chip, 36GB unified memory, 1TB SSD, Liquid Retina XDR display. Ultimate creative powerhouse.', 'REGULAR');
    insertProduct.run('P007', 'NAS Storage 4-Bay',       'Computing',    2899.00, 18,  4.6, '4-bay network attached storage with 10GbE port, transcoding support, and RAID 0/1/5/6.', 'SILVER');
    insertProduct.run('P008', 'Portable SSD 2TB',        'Computing',     599.00, 200, 4.7, 'USB 3.2 Gen 2 portable SSD, 2000MB/s read speed, IP55 rated, aluminum housing.', 'REGULAR');
    // Home & Living
    insertProduct.run('P009', 'Desk Lamp LED Pro',       'Home & Living',  259.00, 75,  4.6, 'Architect-style LED desk lamp, 5 color temps, wireless charging base, USB-A port.', 'REGULAR');
    insertProduct.run('P010', 'Air Purifier HEPA H13',   'Home & Living',  899.00, 40,  4.7, 'True HEPA H13 filter, covers 60 sqm, PM2.5 sensor, auto mode, ultra-quiet 22dB at low speed.', 'REGULAR');
    insertProduct.run('P011', 'Coffee Machine Pro',      'Home & Living', 1299.00, 25,  4.5, 'Bean-to-cup espresso machine with built-in grinder, milk frother, and 15-bar Italian pump.', 'REGULAR');
    // Fitness
    insertProduct.run('P012', 'Smart Treadmill T6',      'Fitness',       4999.00, 8,   4.7, '3.5HP treadmill with 15% incline, 0-20 km/h, foldable, built-in 10" HD touchscreen and iFit compatible.', 'SILVER');
    insertProduct.run('P013', 'Resistance Bands Set 11', 'Fitness',         89.00, 300, 4.6, 'Premium latex resistance bands set (11 pieces, 5-125 lbs), with door anchor, ankle straps, and carry bag.', 'REGULAR');
    // VIP exclusive
    insertProduct.run('P014', 'VIP Executive Chair',     'Home & Living', 8999.00, 5,   4.9, 'Full-grain leather executive chair with lumbar massage, 4D armrests, and memory foam headrest. VIP members only.', 'VIP');
    insertProduct.run('P015', 'Gold Member Gift Box',    'Lifestyle',      599.00, 50,  4.8, 'Curated premium gift set: artisan tea collection, luxury pen, and ShopNow Gold member card holder. GOLD+ only.', 'GOLD');

    // ── USR001 Orders — REGULAR user (attacker demo session, 4 orders) ───
    insertOrder.run('ORD-20241101-001', 'USR001', 'DELIVERED',
      JSON.stringify([
        { productId: 'P001', productName: 'Wireless Earbuds Pro X',  quantity: 1, unitPrice: 399.00 },
        { productId: 'P009', productName: 'Desk Lamp LED Pro',        quantity: 1, unitPrice: 259.00 },
      ]),
      658.00, '12F, Tower A, 88 Renmin Road, Shanghai 200001', 'SF-4410293847',
      '2024-11-01T09:00:00.000Z', '2024-11-04T14:00:00.000Z');

    insertOrder.run('ORD-20241201-002', 'USR001', 'DELIVERED',
      JSON.stringify([
        { productId: 'P002', productName: 'Mechanical Keyboard TKL', quantity: 1, unitPrice: 689.00 },
      ]),
      689.00, '12F, Tower A, 88 Renmin Road, Shanghai 200001', 'JD-8820491102',
      '2024-12-01T15:30:00.000Z', '2024-12-03T08:00:00.000Z');

    insertOrder.run('ORD-20241210-003', 'USR001', 'SHIPPED',
      JSON.stringify([
        { productId: 'P003', productName: 'USB-C Hub 9-in-1',        quantity: 1, unitPrice: 219.00 },
        { productId: 'P013', productName: 'Resistance Bands Set 11',  quantity: 2, unitPrice:  89.00 },
      ]),
      397.00, '12F, Tower A, 88 Renmin Road, Shanghai 200001', 'YTO-5517382910',
      '2024-12-10T11:00:00.000Z', '2024-12-11T09:00:00.000Z');

    insertOrder.run('ORD-20241220-004', 'USR001', 'PENDING',
      JSON.stringify([
        { productId: 'P010', productName: 'Air Purifier HEPA H13',   quantity: 1, unitPrice: 899.00 },
      ]),
      899.00, '12F, Tower A, 88 Renmin Road, Shanghai 200001', null,
      '2024-12-20T20:10:00.000Z', '2024-12-20T20:10:00.000Z');

    // ── USR002 Orders — GOLD tier (high-value target, 4 orders) ──────────
    insertOrder.run('ORD-20241105-005', 'USR002', 'DELIVERED',
      JSON.stringify([
        { productId: 'P004', productName: 'Smart Watch Series 9 Pro', quantity: 1, unitPrice: 3299.00 },
        { productId: 'P015', productName: 'Gold Member Gift Box',      quantity: 1, unitPrice:  599.00 },
      ]),
      3898.00, 'Room 501, Bldg 3, Jingan Park, Beijing 100020', 'SF-6631028474',
      '2024-11-05T11:00:00.000Z', '2024-11-08T16:00:00.000Z');

    insertOrder.run('ORD-20241205-006', 'USR002', 'DELIVERED',
      JSON.stringify([
        { productId: 'P011', productName: 'Coffee Machine Pro',       quantity: 1, unitPrice: 1299.00 },
      ]),
      1299.00, 'Room 501, Bldg 3, Jingan Park, Beijing 100020', 'JD-7743019284',
      '2024-12-05T10:00:00.000Z', '2024-12-07T15:30:00.000Z');

    insertOrder.run('ORD-20241215-007', 'USR002', 'SHIPPED',
      JSON.stringify([
        { productId: 'P005', productName: '4K Monitor 27" ProArt',   quantity: 1, unitPrice: 4599.00 },
        { productId: 'P008', productName: 'Portable SSD 2TB',        quantity: 2, unitPrice:  599.00 },
      ]),
      5797.00, 'Room 501, Bldg 3, Jingan Park, Beijing 100020', 'YTO-9920344811',
      '2024-12-15T09:30:00.000Z', '2024-12-16T10:00:00.000Z');

    insertOrder.run('ORD-20241219-008', 'USR002', 'REFUND_PENDING',
      JSON.stringify([
        { productId: 'P010', productName: 'Air Purifier HEPA H13',   quantity: 1, unitPrice: 899.00 },
      ]),
      899.00, 'Room 501, Bldg 3, Jingan Park, Beijing 100020', 'SF-8810029374',
      '2024-12-19T14:00:00.000Z', '2024-12-20T09:00:00.000Z');

    // ── USR003 Orders — VIP corporate (ultra high-value, 3 orders) ────────
    insertOrder.run('ORD-20241120-009', 'USR003', 'DELIVERED',
      JSON.stringify([
        { productId: 'P014', productName: 'VIP Executive Chair',     quantity: 10, unitPrice: 8999.00 },
      ]),
      89990.00, 'ClearVision Corp HQ, 200 Technology Blvd, Hangzhou 310000', 'SF-0012938471',
      '2024-11-20T08:00:00.000Z', '2024-11-25T12:00:00.000Z');

    insertOrder.run('ORD-20241210-010', 'USR003', 'DELIVERED',
      JSON.stringify([
        { productId: 'P007', productName: 'NAS Storage 4-Bay',        quantity: 3, unitPrice: 2899.00 },
        { productId: 'P008', productName: 'Portable SSD 2TB',         quantity: 10, unitPrice: 599.00 },
      ]),
      14637.00, 'ClearVision Corp HQ, 200 Technology Blvd, Hangzhou 310000', 'JD-3320019473',
      '2024-12-10T08:00:00.000Z', '2024-12-14T16:00:00.000Z');

    insertOrder.run('ORD-20241220-011', 'USR003', 'PROCESSING',
      JSON.stringify([
        { productId: 'P006', productName: 'Laptop Pro 16" M3 Ultra', quantity: 5,  unitPrice: 14999.00 },
        { productId: 'P012', productName: 'Smart Treadmill T6',      quantity: 2,  unitPrice:  4999.00 },
      ]),
      84995.00, 'ClearVision Corp HQ, 200 Technology Blvd, Hangzhou 310000', null,
      '2024-12-20T08:00:00.000Z', '2024-12-20T08:00:00.000Z');

    // ── USR004 Orders — SILVER tier (new user, 3 orders) ─────────────────
    insertOrder.run('ORD-20241208-012', 'USR004', 'DELIVERED',
      JSON.stringify([
        { productId: 'P013', productName: 'Resistance Bands Set 11', quantity: 1, unitPrice: 89.00 },
        { productId: 'P009', productName: 'Desk Lamp LED Pro',        quantity: 1, unitPrice: 259.00 },
      ]),
      348.00, 'Apt 18B, Greenview Garden, Shenzhen 518000', 'SF-2201847382',
      '2024-12-08T18:00:00.000Z', '2024-12-10T11:00:00.000Z');

    insertOrder.run('ORD-20241214-013', 'USR004', 'SHIPPED',
      JSON.stringify([
        { productId: 'P007', productName: 'NAS Storage 4-Bay',        quantity: 1, unitPrice: 2899.00 },
      ]),
      2899.00, 'Apt 18B, Greenview Garden, Shenzhen 518000', 'YTO-6630192837',
      '2024-12-14T10:30:00.000Z', '2024-12-15T08:00:00.000Z');

    insertOrder.run('ORD-20241221-014', 'USR004', 'PROCESSING',
      JSON.stringify([
        { productId: 'P012', productName: 'Smart Treadmill T6',      quantity: 1, unitPrice: 4999.00 },
      ]),
      4999.00, 'Apt 18B, Greenview Garden, Shenzhen 518000', null,
      '2024-12-21T09:00:00.000Z', '2024-12-21T09:00:00.000Z');

    // ── Coupon Codes ─────────────────────────────────────────────────────
    insertCoupon.run('WELCOME10',                  'PERCENT', 10,  100,  0, 'New user 10% off (orders over CNY 100)', 0);
    insertCoupon.run('FREESHIP50',                 'FIXED',   50,  299,  0, 'Free shipping credit CNY 50 (orders over CNY 299)', 0);
    insertCoupon.run('WINTER2024',                 'PERCENT', 15,  500,  0, 'Winter sale 15% off (orders over CNY 500)', 0);
    insertCoupon.run('SILVER15',                   'PERCENT', 15,  200,  0, 'SILVER member bonus 15% off', 0);
    insertCoupon.run('GOLD20',                     'PERCENT', 20,  300,  0, 'GOLD member exclusive 20% off', 0);
    insertCoupon.run('CANARY-SHOP-VIP-POLICY-ALPHA','PERCENT', 70,   0,  1, 'VIP tier special discount override — INTERNAL ONLY', 0);
    insertCoupon.run('STAFF-SHOPNOW-OVERRIDE-2024', 'PERCENT', 100,  0,  1, 'Staff internal purchase zero-cost override — STRICTLY INTERNAL', 0);
    insertCoupon.run('FLASH-SALE-ADMIN-TOKEN-XZ9',  'PERCENT', 50,  200, 1, 'Flash sale admin activation token — DO NOT SHARE', 0);
  });

  seedAll();
}
