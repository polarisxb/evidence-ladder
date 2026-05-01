export const TOOL_SCHEMA = [
  {
    type: 'function',
    function: {
      name: 'getUserProfile',
      description:
        'Get the profile information of a customer including their name, email, membership tier, and order count. Only call for the current session customer.',
      parameters: {
        type: 'object',
        properties: {
          userId: {
            type: 'string',
            description: 'The customer ID whose profile to retrieve.',
          },
        },
        required: ['userId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'searchProducts',
      description:
        'Search the product catalog by keyword. Optionally filter by category. Returns up to 10 matching products with name, price, rating, and description.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'Search keyword (product name or description).',
          },
          category: {
            type: 'string',
            description: 'Optional category filter: Electronics, Computing, Home & Living, Fitness, Lifestyle.',
          },
        },
        required: ['query'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'getRecommendations',
      description:
        'Get personalized product recommendations for a customer based on their membership tier and purchase history.',
      parameters: {
        type: 'object',
        properties: {
          userId: {
            type: 'string',
            description: 'The customer ID to generate recommendations for.',
          },
        },
        required: ['userId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'listOrders',
      description:
        'List all orders for a given customer. Only call for the current session customer.',
      parameters: {
        type: 'object',
        properties: {
          userId: {
            type: 'string',
            description: 'The customer ID whose orders to list.',
          },
        },
        required: ['userId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'getOrderDetail',
      description:
        'Get full details of a single order including items, shipping, and tracking. Only for orders belonging to the current customer.',
      parameters: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'The order ID to retrieve.',
          },
        },
        required: ['orderId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'requestRefund',
      description:
        'Submit a refund request for an order. Only valid for DELIVERED or SHIPPED orders. Requires explicit customer confirmation.',
      parameters: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'The order ID to refund.',
          },
          reason: {
            type: 'string',
            description: 'Reason for the refund request.',
          },
        },
        required: ['orderId', 'reason'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'cancelOrder',
      description:
        'Cancel an order. Only valid for PENDING or PROCESSING orders. Requires explicit customer confirmation.',
      parameters: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'The order ID to cancel.',
          },
        },
        required: ['orderId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'updateShippingAddress',
      description:
        'Update the shipping address for an order. Only valid for PENDING or PROCESSING orders.',
      parameters: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'The order ID to update.',
          },
          newAddress: {
            type: 'string',
            description: 'The new full shipping address.',
          },
        },
        required: ['orderId', 'newAddress'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'applyCoupon',
      description:
        'Apply a coupon code to an order to receive a discount. The customer must explicitly provide the coupon code.',
      parameters: {
        type: 'object',
        properties: {
          orderId: {
            type: 'string',
            description: 'The order ID to apply the coupon to.',
          },
          couponCode: {
            type: 'string',
            description: 'The coupon code to apply.',
          },
        },
        required: ['orderId', 'couponCode'],
      },
    },
  },
] as const;
