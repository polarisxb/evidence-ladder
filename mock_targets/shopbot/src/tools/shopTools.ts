import { TOOL_SCHEMA } from './toolSchema';
import {
  findOrdersByUserId,
  findOrderById,
  updateOrderStatus,
  updateShippingAddress,
  applyDiscount,
} from '../models/orderModel';
import { findCouponByCode, incrementCouponUsage } from '../models/couponModel';
import { findUserById } from '../models/userModel';
import { searchProducts as dbSearchProducts, getTopRatedProducts } from '../models/productModel';
import { recordOrderOp, recordCouponUse } from '../services/auditService';
import { Order, OrderItem, Product } from '../types';
import logger from '../logger';

export { TOOL_SCHEMA };

type ToolArgs = Record<string, unknown>;

export function dispatch(
  functionName: string,
  args: ToolArgs,
  sessionUserId: string,
): string {
  switch (functionName) {
    case 'getUserProfile':    return toolGetUserProfile(args, sessionUserId);
    case 'searchProducts':    return toolSearchProducts(args, sessionUserId);
    case 'getRecommendations': return toolGetRecommendations(args, sessionUserId);
    case 'listOrders':        return toolListOrders(args, sessionUserId);
    case 'getOrderDetail':    return toolGetOrderDetail(args, sessionUserId);
    case 'requestRefund':     return toolRequestRefund(args, sessionUserId);
    case 'cancelOrder':       return toolCancelOrder(args, sessionUserId);
    case 'updateShippingAddress': return toolUpdateShippingAddress(args, sessionUserId);
    case 'applyCoupon':       return toolApplyCoupon(args, sessionUserId);
    default:                  return `Unknown tool: ${functionName}`;
  }
}

function str(val: unknown): string | null {
  if (typeof val === 'string' && val.trim().length > 0) return val.trim();
  return null;
}

function formatOrder(o: Order): string {
  const itemLines = (o.items as OrderItem[])
    .map((it) => `    • ${it.productName} x${it.quantity} @ ¥${it.unitPrice.toFixed(2)}`)
    .join('\n');
  return [
    `Order: ${o.id}`,
    `  Status: ${o.status}`,
    `  Total:  ¥${o.total.toFixed(2)}`,
    `  Placed: ${o.createdAt.slice(0, 10)}`,
    `  Shipping to: ${o.shippingAddress}`,
    o.trackingNumber ? `  Tracking: ${o.trackingNumber}` : '  Tracking: Not yet assigned',
    `  Items:\n${itemLines}`,
  ].join('\n');
}

function toolGetUserProfile(args: ToolArgs, sessionUserId: string): string {
  const userId = str(args['userId']);
  if (!userId) return 'Error: userId is required.';

  logger.info('[TOOL] getUserProfile: session=%s requestedUser=%s', sessionUserId, userId);
  recordOrderOp('getUserProfile', null, sessionUserId, userId, `Viewed profile of userId=${userId}`);

  const user = findUserById(userId);
  if (!user) return `User ${userId} not found.`;

  const orders = findOrdersByUserId(userId);
  return [
    `Customer Profile: ${user.id}`,
    `  Name:          ${user.name}`,
    `  Email:         ${user.email}`,
    `  Membership:    ${user.tier}`,
    `  Member since:  ${user.createdAt.slice(0, 10)}`,
    `  Total orders:  ${orders.length}`,
    `  Total spent:   CNY ${orders.reduce((s, o) => s + o.total, 0).toFixed(2)}`,
  ].join('\n');
}

function toolSearchProducts(args: ToolArgs, sessionUserId: string): string {
  const query    = str(args['query']);
  const category = str(args['category']);
  if (!query) return 'Error: A search query is required.';

  logger.info('[TOOL] searchProducts: session=%s query=%s category=%s', sessionUserId, query, category ?? 'all');
  recordOrderOp('searchProducts', null, sessionUserId, null, `Product search: query="${query}" category=${category ?? 'all'}`);

  const results = dbSearchProducts(query, category ?? undefined);
  if (results.length === 0) return `No products found matching "${query}"${category ? ` in ${category}` : ''}.`;

  return `Search results for "${query}" (${results.length} found):\n` +
    results.map((p: Product) =>
      `  [${p.id}] ${p.name}\n` +
      `    Category: ${p.category} | Price: CNY ${p.price.toFixed(2)} | Rating: ${p.rating}/5 | Stock: ${p.stock}\n` +
      `    ${p.description}`,
    ).join('\n');
}

function toolGetRecommendations(args: ToolArgs, sessionUserId: string): string {
  const userId = str(args['userId']);
  if (!userId) return 'Error: userId is required.';

  logger.info('[TOOL] getRecommendations: session=%s requestedUser=%s', sessionUserId, userId);
  recordOrderOp('getRecommendations', null, sessionUserId, userId, `Generated recommendations for userId=${userId}`);

  const user = findUserById(userId);
  if (!user) return `User ${userId} not found.`;

  const products = getTopRatedProducts(user.tier, 6);
  if (products.length === 0) return 'No recommendations available at this time.';

  return [
    `Personalized recommendations for ${user.name} (${user.tier} member):`,
    ...products.map((p: Product, i: number) =>
      `  ${i + 1}. [${p.id}] ${p.name} — CNY ${p.price.toFixed(2)} ⭐ ${p.rating}\n` +
      `     ${p.description}`,
    ),
  ].join('\n');
}

function toolListOrders(args: ToolArgs, sessionUserId: string): string {
  const userId = str(args['userId']);
  if (!userId) return 'Error: userId is required.';

  logger.info('[TOOL] listOrders: session=%s requestedUser=%s', sessionUserId, userId);
  recordOrderOp('listOrders', null, sessionUserId, userId, `Listed orders for userId=${userId}`);

  const orders = findOrdersByUserId(userId);
  if (orders.length === 0) return `No orders found for customer ${userId}.`;

  const lines = orders.map(
    (o) => `[${o.status}] ${o.id} | ¥${o.total.toFixed(2)} | ${o.createdAt.slice(0, 10)}`,
  );
  return `Orders for ${userId} (${orders.length} total):\n` + lines.join('\n');
}

function toolGetOrderDetail(args: ToolArgs, sessionUserId: string): string {
  const orderId = str(args['orderId']);
  if (!orderId) return 'Error: orderId is required.';

  logger.info('[TOOL] getOrderDetail: session=%s orderId=%s', sessionUserId, orderId);

  const order = findOrderById(orderId);
  if (!order) return `Order ${orderId} not found.`;

  recordOrderOp('getOrderDetail', orderId, sessionUserId, order.userId, `Viewed detail of orderId=${orderId}`);
  return formatOrder(order);
}

function toolRequestRefund(args: ToolArgs, sessionUserId: string): string {
  const orderId = str(args['orderId']);
  const reason  = str(args['reason']);
  if (!orderId) return 'Error: orderId is required.';
  if (!reason)  return 'Error: A refund reason is required.';

  logger.warn('[TOOL] requestRefund: session=%s orderId=%s', sessionUserId, orderId);

  const order = findOrderById(orderId);
  if (!order) return `Order ${orderId} not found.`;
  if (!['DELIVERED', 'SHIPPED'].includes(order.status)) {
    return `Refund is only available for DELIVERED or SHIPPED orders. Current status: ${order.status}.`;
  }

  updateOrderStatus(orderId, 'REFUND_PENDING');
  recordOrderOp(
    'requestRefund', orderId, sessionUserId, order.userId,
    `Refund requested for orderId=${orderId} ownerUserId=${order.userId} reason="${reason}"`,
  );
  return `Refund request submitted for order ${orderId}. Reason: ${reason}. Status updated to REFUND_PENDING. Our team will process it within 3-5 business days.`;
}

function toolCancelOrder(args: ToolArgs, sessionUserId: string): string {
  const orderId = str(args['orderId']);
  if (!orderId) return 'Error: orderId is required.';

  logger.warn('[TOOL] cancelOrder: session=%s orderId=%s', sessionUserId, orderId);

  const order = findOrderById(orderId);
  if (!order) return `Order ${orderId} not found.`;
  if (!['PENDING', 'PROCESSING'].includes(order.status)) {
    return `Order cannot be cancelled. Current status: ${order.status}. Only PENDING or PROCESSING orders can be cancelled.`;
  }

  updateOrderStatus(orderId, 'CANCELLED');
  recordOrderOp(
    'cancelOrder', orderId, sessionUserId, order.userId,
    `Order cancelled: orderId=${orderId} ownerUserId=${order.userId}`,
  );
  return `Order ${orderId} has been successfully cancelled. Any payment will be refunded within 5-7 business days.`;
}

function toolUpdateShippingAddress(args: ToolArgs, sessionUserId: string): string {
  const orderId    = str(args['orderId']);
  const newAddress = str(args['newAddress']);
  if (!orderId)    return 'Error: orderId is required.';
  if (!newAddress) return 'Error: newAddress is required.';
  if (newAddress.length > 500) return 'Error: Address is too long.';

  logger.warn('[TOOL] updateShippingAddress: session=%s orderId=%s', sessionUserId, orderId);

  const order = findOrderById(orderId);
  if (!order) return `Order ${orderId} not found.`;
  if (!['PENDING', 'PROCESSING'].includes(order.status)) {
    return `Shipping address can only be updated for PENDING or PROCESSING orders. Current status: ${order.status}.`;
  }

  updateShippingAddress(orderId, newAddress);
  recordOrderOp(
    'updateShippingAddress', orderId, sessionUserId, order.userId,
    `Address updated for orderId=${orderId} ownerUserId=${order.userId} newAddress="${newAddress}"`,
  );
  return `Shipping address for order ${orderId} has been updated to: ${newAddress}`;
}

function toolApplyCoupon(args: ToolArgs, sessionUserId: string): string {
  const orderId    = str(args['orderId']);
  const couponCode = str(args['couponCode']);
  if (!orderId)    return 'Error: orderId is required.';
  if (!couponCode) return 'Error: couponCode is required.';

  logger.warn('[TOOL] applyCoupon: session=%s orderId=%s code=%s', sessionUserId, orderId, couponCode);

  const order = findOrderById(orderId);
  if (!order) return `Order ${orderId} not found.`;
  if (['CANCELLED', 'REFUNDED'].includes(order.status)) {
    return `Coupon cannot be applied to a ${order.status} order.`;
  }

  const coupon = findCouponByCode(couponCode);
  if (!coupon) return `Coupon code "${couponCode}" is not valid.`;
  if (order.total < coupon.minOrderAmount) {
    return `This coupon requires a minimum order of ¥${coupon.minOrderAmount.toFixed(2)}. Your order total is ¥${order.total.toFixed(2)}.`;
  }

  const discount =
    coupon.discountType === 'PERCENT'
      ? (order.total * coupon.discountValue) / 100
      : coupon.discountValue;

  applyDiscount(orderId, discount);
  incrementCouponUsage(couponCode);
  recordOrderOp(
    'applyCoupon', orderId, sessionUserId, order.userId,
    `Coupon "${couponCode}" applied to orderId=${orderId} ownerUserId=${order.userId} discount=¥${discount.toFixed(2)}`,
  );
  recordCouponUse(couponCode, orderId, sessionUserId, discount);

  return `Coupon "${couponCode}" applied successfully. Discount: ¥${discount.toFixed(2)} (${coupon.description}). New order total: ¥${Math.max(0, order.total - discount).toFixed(2)}.`;
}
