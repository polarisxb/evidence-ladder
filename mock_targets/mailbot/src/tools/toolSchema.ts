export const TOOL_SCHEMA = [
  {
    type: 'function',
    function: {
      name: 'list_emails',
      description:
        'List the emails in a folder for the current user. Returns id, sender, subject, and read status for each message.',
      parameters: {
        type: 'object',
        properties: {
          folder: {
            type: 'string',
            description: 'The folder to list: inbox, sent, or trash. Defaults to inbox.',
            enum: ['inbox', 'sent', 'trash'],
          },
        },
        required: [],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'read_email',
      description:
        'Read the full content (sender, subject, and body) of a single email by its id.',
      parameters: {
        type: 'object',
        properties: {
          emailId: {
            type: 'string',
            description: 'The id of the email to read.',
          },
        },
        required: ['emailId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'send_email',
      description:
        'Send a new email on behalf of the current user. Only send to recipients the user has explicitly requested.',
      parameters: {
        type: 'object',
        properties: {
          to: {
            type: 'string',
            description: 'The recipient email address.',
          },
          subject: {
            type: 'string',
            description: 'The email subject line.',
          },
          body: {
            type: 'string',
            description: 'The email body.',
          },
        },
        required: ['to', 'subject', 'body'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'forward_email',
      description:
        'Forward an existing email to another recipient. Only forward when the user explicitly asks to.',
      parameters: {
        type: 'object',
        properties: {
          emailId: {
            type: 'string',
            description: 'The id of the email to forward.',
          },
          to: {
            type: 'string',
            description: 'The recipient email address to forward to.',
          },
        },
        required: ['emailId', 'to'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'delete_email',
      description:
        'Delete an email by moving it to the trash folder. Only delete when the user explicitly asks to.',
      parameters: {
        type: 'object',
        properties: {
          emailId: {
            type: 'string',
            description: 'The id of the email to delete.',
          },
        },
        required: ['emailId'],
      },
    },
  },
  {
    type: 'function',
    function: {
      name: 'search_emails',
      description:
        'Search the current user\'s emails by keyword across subject and body. Returns matching messages.',
      parameters: {
        type: 'object',
        properties: {
          query: {
            type: 'string',
            description: 'The search keyword.',
          },
        },
        required: ['query'],
      },
    },
  },
] as const;
