import * as fs from 'fs';
import { config } from '../config';
import { findUserById } from '../models/userModel';
import { dispatch, TOOL_SCHEMA } from '../tools/shopTools';
import { ChatMessage, ChatResult, LlmMessage, LlmToolCall } from '../types';
import logger from '../logger';

const MAX_TOOL_ROUNDS = config.maxToolRounds;

let _systemPromptTemplate: string | null = null;

function getSystemPromptTemplate(): string {
  if (_systemPromptTemplate === null) {
    try {
      _systemPromptTemplate = fs.readFileSync(config.systemPromptPath, 'utf-8');
    } catch (err) {
      logger.error('[CHAT] Failed to load system prompt template: %s', String(err));
      _systemPromptTemplate = 'You are a helpful shopping assistant.';
    }
  }
  return _systemPromptTemplate;
}

interface LlmChoice {
  message: LlmMessage;
  finish_reason: string;
}

interface LlmResponse {
  choices?: LlmChoice[];
  error?: { message: string };
}

function loadSystemPrompt(userId: string): string {
  const template = getSystemPromptTemplate();
  const user = findUserById(userId);
  const tier = user?.tier ?? 'REGULAR';
  const date = new Date().toISOString().slice(0, 10);
  return template
    .replace(/\{userId\}/g, userId)
    .replace(/\{userTier\}/g, tier)
    .replace(/\{date\}/g, date);
}

export async function chat(
  userId: string,
  userMessage: string,
  history: ChatMessage[],
): Promise<ChatResult> {
  try {
    const systemPrompt = loadSystemPrompt(userId);

    const messages: LlmMessage[] = [
      { role: 'system', content: systemPrompt },
      ...history
        .filter((m) => m.role === 'user' || m.role === 'assistant')
        .slice(-20)
        .map((m) => ({ role: m.role, content: m.content })),
      { role: 'user', content: userMessage },
    ];

    for (let round = 0; round < MAX_TOOL_ROUNDS; round++) {
      const requestBody = {
        model: config.openaiModel,
        messages,
        tools: TOOL_SCHEMA,
        tool_choice: 'auto',
        temperature: 0.2,
        max_tokens: 1024,
      };

      const rawResponse = await callLlmApi(requestBody);
      const llmResp: LlmResponse = JSON.parse(rawResponse) as LlmResponse;

      if (llmResp.error) {
        logger.error('[CHAT] LLM API error for userId=%s: %s', userId, llmResp.error.message);
        return {
          response: 'I am experiencing technical difficulties. Please contact our support line.',
          modelInvoked: false, postProcessed: false, blockReason: 'pre_guardrail',
        };
      }

      const choice = llmResp.choices?.[0];
      if (!choice) {
        logger.warn('[CHAT] LLM returned no choices for userId=%s', userId);
        return {
          response: 'I am experiencing technical difficulties. Please contact our support line.',
          modelInvoked: false, postProcessed: false, blockReason: 'pre_guardrail',
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
            response: "I'm sorry, I couldn't generate a response. Please rephrase your question.",
            modelInvoked: true, postProcessed: true, postReason: 'format_enforcement',
          };
        }
        return { response: content, modelInvoked: true, postProcessed: false };
      }
    }

    return {
      response: 'Request processed. Please contact support if you need further assistance.',
      modelInvoked: true, postProcessed: true, postReason: 'tool_rewrite',
    };

  } catch (err) {
    logger.error('[CHAT] Unhandled error for userId=%s: %s', userId, String(err));
    return {
      response: 'I am experiencing technical difficulties. Please contact our support line.',
      modelInvoked: false, postProcessed: true, postReason: 'error_fallback',
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
