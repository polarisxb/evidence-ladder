export type UserTier = 'REGULAR' | 'SILVER' | 'GOLD' | 'VIP';
export type OrderStatus =
  | 'PENDING'
  | 'PROCESSING'
  | 'SHIPPED'
  | 'DELIVERED'
  | 'CANCELLED'
  | 'REFUND_PENDING'
  | 'REFUNDED';
export type DiscountType = 'PERCENT' | 'FIXED';
export type AuditOperation =
  | 'listOrders'
  | 'getOrderDetail'
  | 'getUserProfile'
  | 'searchProducts'
  | 'getRecommendations'
  | 'requestRefund'
  | 'cancelOrder'
  | 'updateShippingAddress'
  | 'applyCoupon';

export interface Product {
  id: string;
  name: string;
  category: string;
  price: number;
  stock: number;
  rating: number;
  description: string;
  tierRequired: string;
}

export interface User {
  id: string;
  name: string;
  email: string;
  tier: UserTier;
  createdAt: string;
}

export interface OrderItem {
  productId: string;
  productName: string;
  quantity: number;
  unitPrice: number;
}

export interface Order {
  id: string;
  userId: string;
  status: OrderStatus;
  items: OrderItem[];
  total: number;
  shippingAddress: string;
  trackingNumber: string | null;
  createdAt: string;
  updatedAt: string;
}

export interface CouponCode {
  code: string;
  discountType: DiscountType;
  discountValue: number;
  minOrderAmount: number;
  isInternal: number;
  description: string;
  usageCount: number;
}

export interface AuditLog {
  id: number;
  operation: AuditOperation;
  orderId: string | null;
  sessionUserId: string;
  targetUserId: string | null;
  detail: string;
  executedAt: string;
}

export interface CouponUseLog {
  id: number;
  couponCode: string;
  orderId: string;
  sessionUserId: string;
  discountApplied: number;
  executedAt: string;
}

export interface ChatMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface ToolCallRecord {
  name: string;
  arguments: string;
  result: string;
}

export interface ChatResult {
  response: string;
  modelInvoked: boolean;
  postProcessed: boolean;
  blockReason?: string | null;
  postReason?: string | null;
  toolCalls?: ToolCallRecord[];
}

export interface ChatRequest {
  message: string;
  userId: string;
  history?: ChatMessage[];
}

export interface LlmMessage {
  role: string;
  content?: string | null;
  tool_calls?: LlmToolCall[];
  tool_call_id?: string;
}

export interface LlmToolCall {
  id: string;
  type: 'function';
  function: {
    name: string;
    arguments: string;
  };
}
