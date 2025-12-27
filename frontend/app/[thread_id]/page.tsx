'use client';

import { Thread } from '@/components/assistant-ui/thread';
import { Sidebar } from '@/components/assistant-ui/sidebar';
import { AssistantRuntimeProvider, useLocalRuntime } from '@assistant-ui/react';
import { chatModelAdapter, setCurrentThreadId } from '@/lib/assistant-runtime';
import '@/lib/axios-config';
import { use, useEffect } from 'react';
import { useApiGetThreadApiThreadThreadIdGet } from '@/lib/api/default/default';
import type { ThreadMessage } from '@assistant-ui/react';
import { Loader2 } from 'lucide-react';
import { useRouter } from 'next/navigation';

export default function ThreadPage({ params }: { params: Promise<{ thread_id: string }> }) {
  const router = useRouter();
  const { thread_id: threadId } = use(params);

  // Fetch thread messages
  const { data: threadData, isFetching, isError } = useApiGetThreadApiThreadThreadIdGet(threadId);

  // Update global thread ID
  useEffect(() => {
    setCurrentThreadId(threadId);
  }, [threadId]);

  const handleThreadSelect = (newThreadId: string | null) => {
    console.log('Selected thread ID:', newThreadId);
    if (newThreadId) {
      router.push(`/${newThreadId}`);
    } else {
      router.push('/');
    }
  };

  // Show loading spinner while fetching
  if (isFetching) {
    return (
      <div className="flex h-screen w-full bg-background">
        <Sidebar 
          currentThreadId={threadId}
          onThreadSelect={handleThreadSelect}
        />
        <main className="flex flex-1 flex-col">
          <div className="flex flex-1 items-center justify-center">
            <div className="flex flex-col items-center gap-4">
              <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Loading thread...</p>
            </div>
          </div>
        </main>
      </div>
    );
  }

  // Show error if failed to load
  if (isError || !threadData) {
    return (
      <div className="flex h-screen w-full bg-background">
        <Sidebar 
          currentThreadId={threadId}
          onThreadSelect={handleThreadSelect}
        />
        <main className="flex flex-1 flex-col items-center justify-center">
          <p className="text-sm text-muted-foreground">Failed to load thread</p>
        </main>
      </div>
    );
  }

  // Convert thread data to initial messages
  const initialMessages: ThreadMessage[] = threadData.data.messages
    .filter((msg) => msg.type === 'human' || msg.type === 'ai')
    .map((msg) => ({
      role: msg.type === 'human' ? ('user' as const) : ('assistant' as const),
      content: [{ type: 'text' as const, text: msg.content }],
      id: msg.id || undefined,
    }));

  return <ThreadContent threadId={threadId} initialMessages={initialMessages} onThreadSelect={handleThreadSelect} />;
}

function ThreadContent({ 
  threadId, 
  initialMessages, 
  onThreadSelect
}: { 
  threadId: string;
  initialMessages: ThreadMessage[];
  onThreadSelect: (threadId: string | null) => void;
}) {
  const runtime = useLocalRuntime(chatModelAdapter, {
    initialMessages,
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-screen w-full bg-background">
        <Sidebar 
          currentThreadId={threadId}
          onThreadSelect={onThreadSelect}
        />

        <main className="flex flex-1 flex-col">
          <Thread />
        </main>
      </div>
    </AssistantRuntimeProvider>
  );
}
