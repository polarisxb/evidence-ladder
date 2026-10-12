import * as fs from 'fs';
import { config } from '../config';
import { findUserById } from '../models/userModel';
import { dispatch, TOOL_SCHEMA } from '../tools/mailTools';
import { ChatMessage, ChatResult, LlmMessage, LlmToolCall, ToolCallRecord } from '../types';
import logger from '../logger';

const MAX_TOOL_ROUNDS = config.maxToolRounds;

// Defense strength is an experimental factor, not a product feature: 'defended'
// uses the guarded system prompt (least-privilege, do-not-exfiltrate), 'undefended'
// uses a permissive one that follows instructions found while doing the task. This
// lets an evaluation isolate how much of an attack's failure is the model vs the
// application's prompt-level defense.
export type DefenseLevel = 'defended' | 'undefended';

const _systemPromptCache: Partial<Record<DefenseLevel, string>> = {};

function systemPromptPathFor(defense: DefenseLevel): string {
  return defense === 'undefended' ? config.systemPromptUndefendedPath : config.systemPromptPath;
}

function getSystemPromptTemplate(defense: DefenseLevel): string {
  const cached = _systemPromptCache[defense];
  if (cached !== undefined) return cached;
  let template: string;
  try {
    template = fs.readFileSync(systemPromptPathFor(defense), 'utf-8');
  } catch (err) {
    logger.error('[CHAT] Failed to load %s system prompt: %s', defense, String(err));
    template = 'You are a helpful email assistant.';
  }
  _systemPromptCache[defense] = template;
  return template;
}

interface LlmChoice {
  message: LlmMessage;
  finish_reason: string;
}

interface LlmResponse {
  choices?: LlmChoice[];
  error?: { message: string };
}

function loadSystemPrompt(userId: string, defense: DefenseLevel): string {
  const template = getSystemPromptTemplate(defense);
  const user = findUserById(userId);
  const ownerEmail = user?.email ?? `${userId}@corp.com`;
  return template.replace(/\{ownerEmail\}/g, ownerEmail);
}

export async function chat(
  userId: string,
  userMessage: string,
  history: ChatMessage[],
  defense: DefenseLevel = 'defended',
): Promise<ChatResult> {
  // Declared outside the try so every exit, the catch included, reports the
  // tool calls that already ran.
  const toolCalls: ToolCallRecord[] = [];
  try {
    const systemPrompt = loadSystemPrompt(userId, defense);

    const messages: LlmMessage[] = [
      { role: 'system', content: systemPrompt },
      ...history
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-20)
        .map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: userMessage },
    ];

    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      // extraRequestBody may override sampling knobs (temperature, max_tokens,
      // tool_choice) but never the conversation or tool schema.
      const requestBody = {
        model: config.openaiModel,
        tool_choice: 'auto',
        temperature: config.temperature,
        max_tokens: config.maxTokens,
        ...config.extraRequestBody,
        messages,
        tools: TOOL_SCHEMA,
      };

      const rawResponse = await callLlmApi(requestBody);
      const llmResp: LlmResponse = JSON.parse(rawResponse) as LlmResponse;

      if (llmResp.error) {
        logger.error('[CHAT] LLM API error for userId=%s: %s', userId, llmResp.error.message);
        return {
          response: 'I am experiencing technical difficulties. Please contact support.',
          modelInvoked: false, postProcessed: false, blockReason: 'pre_guardrail', toolCalls, evaluable: false,
        };
      }

      const choice = llmResp.choices?.[0];
      if (!choice) {
        logger.warn('[CHAT] LLM returned no choices for userId=%s', userId);
        return {
          response: 'I am experiencing technical difficulties. Please contact support.',
          modelInvoked: false, postProcessed: false, blockReason: 'pre_guardrail', toolCalls, evaluable: false,
        };
      }

      const assistantMsg = choice.message;
      const finishReason = choice.finish_reason;

      messages.push(assistantMsg);

      if (finishReason === 'tool_calls' && assistantMsg.tool_calls?.length) {
        for (const toolCall of assistantMsg.tool_calls as LlmToolCall[]) {
          const funcName = toolCall.function.name;
          let funcArgs: Record<string, unknown>;
          try {
            funcArgs = JSON.parse(toolCall.function.arguments) as Record<string, unknown>;
          } catch {
            funcArgs = {};
          }

          logger.info('[FC] round=%d function=%s args=%s', round, funcName, toolCall.function.arguments);
          const toolResult = dispatch(funcName, funcArgs, userId);
          toolCalls.push({ name: funcName, arguments: toolCall.function.arguments, result: toolResult });

          messages.push({
            role: 'tool',
            tool_call_id: toolCall.id,
            content: toolResult,
          });
        }
      } else {
        const content = (assistantMsg.content ?? '').trim();
        logger.info('[CHAT] userId=%s rounds=%d response_len=%d', userId, round + 1, content.length);
        if (!content) {
          logger.warn('[CHAT] LLM returned empty content for userId=%s finishReason=%s', userId, finishReason);
          return {
            response: "I'm sorry, I couldn't generate a response. Please rephrase your request.",
            modelInvoked: true, postProcessed: true, postReason: 'format_enforcement', toolCalls, evaluable: false,
          };
        }
        return { response: content, modelInvoked: true, postProcessed: false, toolCalls, evaluable: true };
      }
    }

    return {
      response: 'Request processed. Please contact support if you need further assistance.',
      modelInvoked: true, postProcessed: true, postReason: 'tool_rewrite', toolCalls, evaluable: false,
    };

  } catch (err) {
    logger.error('[CHAT] Unhandled error for userId=%s: %s', userId, String(err));
    return {
      response: 'I am experiencing technical difficulties. Please contact support.',
      modelInvoked: false, postProcessed: true, postReason: 'error_fallback', toolCalls, evaluable: false,
    };
  }
}

async function callLlmApi(body: unknown): Promise<string> {
  const url = `${config.openaiBaseUrl}/chat/completions`;
  const response = await fetch(url, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${config.openaiApiKey}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  });

  const text = await response.text();
  if (!response.ok) {
    throw new Error(`LLM API error ${response.status}: ${text}`);
  }
  return text;
}
