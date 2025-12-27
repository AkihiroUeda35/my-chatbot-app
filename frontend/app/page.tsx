'use client';

import { Thread } from '@/components/assistant-ui/thread';
import { Sidebar } from '@/components/assistant-ui/sidebar';
import { AssistantRuntimeProvider, useLocalRuntime } from '@assistant-ui/react';
import { chatModelAdapter, setCurrentThreadId } from '@/lib/assistant-runtime';
import '@/lib/axios-config';
import { useEffect } from 'react';
import { useRouter } from 'next/navigation';

function NewThreadContent({ onThreadSelect }: { onThreadSelect: (threadId: string | null) => void }) {
  const runtime = useLocalRuntime(chatModelAdapter, {
    initialMessages: [],
  });

  // Set current thread ID to null for new thread
  useEffect(() => {
    setCurrentThreadId(null);
  }, []);

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-screen w-full bg-background">
        <Sidebar 
          currentThreadId={null}
          onThreadSelect={onThreadSelect}
        />

        <main className="flex flex-1 flex-col">
          <Thread />
        </main>
      </div>
    </AssistantRuntimeProvider>
  );
}

export default function Home() {
  const router = useRouter();

  const handleThreadSelect = (threadId: string | null) => {
    console.log('Selected thread ID:', threadId);
    if (threadId) {
      router.push(`/${threadId}`);
    } else {
      router.push('/');
    }
  };

  return <NewThreadContent onThreadSelect={handleThreadSelect} />;
}
