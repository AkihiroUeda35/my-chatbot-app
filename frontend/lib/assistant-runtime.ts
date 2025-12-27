'use client';

import axios from './axios-config';
import type { ChatModelAdapter, ChatModelRunOptions } from '@assistant-ui/react';

let currentThreadId: string | null = null;

// ChatModelAdapter implementation for assistant-ui using Vercel AI SDK format
export const chatModelAdapter: ChatModelAdapter = {
  async *run({ messages, abortSignal }: ChatModelRunOptions) {
    // Get the last user message
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage || lastMessage.role !== 'user') {
      return;
    }

    // Extract text content from message
    let textContent = '';
    for (const part of lastMessage.content) {
      if (part.type === 'text') {
        textContent += part.text;
      }
    }

    // Prepare the request
    const requestData = {
      query: textContent,
      thread_id: currentThreadId || undefined,
      message_id: null,
    };

    // Use relative path to leverage Next.js proxy (rewrites)
    const baseURL = axios.defaults.baseURL || '';

    let accumulatedText = '';

    try {
      const response = await fetch(`${baseURL}/api/chat`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestData),
        signal: abortSignal,
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const reader = response.body?.getReader();
      if (!reader) {
        throw new Error('Response body is not readable');
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        //console.log('Raw buffer:', buffer);
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line) continue;
          //console.log('Processing line:', line);

          // Parse Vercel AI SDK Data Stream Protocol
          // Format: TYPE_CODE:DATA
          const colonIndex = line.indexOf(':');
          if (colonIndex === -1) continue;

          const typeCode = line.substring(0, colonIndex);
          const data = line.substring(colonIndex + 1);
          //console.log('TypeCode:', typeCode, 'Data:', data);

          switch (typeCode) {
            case '0': {
              // Text delta: 0:"text"
              try {
                const text = JSON.parse(data) as string;
                accumulatedText += text;
                //console.log('Yielding accumulated text:', accumulatedText);
                yield {
                  content: [{ type: 'text' as const, text: accumulatedText }],
                };
              } catch (e) {
                console.error('Parse error:', e);
              }
              break;
            }
            case '8': {
              // Message annotations: 8:[{...}]
              try {
                const annotations = JSON.parse(data) as Array<{
                  thread_id?: string;
                  message_id?: string;
                }>;
                if (annotations.length > 0 && annotations[0].thread_id) {
                  currentThreadId = annotations[0].thread_id;
                }
              } catch {
                // Ignore parse errors
              }
              break;
            }
            case '3': {
              // Error: 3:"error message"
              try {
                const errorMessage = JSON.parse(data) as string;
                throw new Error(errorMessage);
              } catch (e) {
                if (e instanceof Error && e.message !== data) {
                  throw e;
                }
                throw new Error(data);
              }
            }
            case 'd': {
              // Finish message: d:{"finishReason":"stop"}
              // No action needed, streaming is complete
              break;
            }
            default:
              // Unknown type code, ignore
              break;
          }
        }
      }
    } catch (error: unknown) {
      if (error instanceof Error && error.name === 'AbortError') {
        return;
      }
      console.error('Stream error:', error);
      throw error;
    }
  },
};

export function getCurrentThreadId(): string | null {
  return currentThreadId;
}

export function setCurrentThreadId(threadId: string | null): void {
  currentThreadId = threadId;
}
