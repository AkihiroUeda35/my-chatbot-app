'use client';

import { Button } from '@/components/ui/button';
import { Skeleton } from '@/components/ui/skeleton';
import { TooltipIconButton } from '@/components/assistant-ui/tooltip-icon-button';
import { useApiGetThreadsApiThreadsGet, useApiDeleteThreadApiThreadThreadIdDelete } from '@/lib/api/default/default';
import { PlusIcon, ArchiveIcon } from 'lucide-react';
import { FC } from 'react';

interface CustomThreadListProps {
  currentThreadId: string | null;
  onThreadSelect: (threadId: string | null) => void;
}

export const CustomThreadList: FC<CustomThreadListProps> = ({ 
  currentThreadId, 
  onThreadSelect 
}) => {
  const { data, isLoading, refetch } = useApiGetThreadsApiThreadsGet({
    query: {
      staleTime: 30000, // Cache for 30 seconds to avoid redundant fetches
      cacheTime: 60000,
    }
  });
  const deleteThread = useApiDeleteThreadApiThreadThreadIdDelete();

  const handleNewThread = () => {
    onThreadSelect(null);
  };

  const handleSelectThread = (threadId: string) => {
    onThreadSelect(threadId);
  };

  const handleDeleteThread = async (threadId: string, e: React.MouseEvent) => {
    e.stopPropagation();
    try {
      await deleteThread.mutateAsync({ threadId });
      refetch();
      if (currentThreadId === threadId) {
        onThreadSelect(null);
      }
    } catch (error) {
      console.error('Failed to delete thread:', error);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col gap-1">
        {Array.from({ length: 5 }, (_, i) => (
          <div
            key={i}
            role="status"
            aria-label="Loading threads"
            className="flex h-9 items-center px-3"
          >
            <Skeleton className="h-4 w-full" />
          </div>
        ))}
      </div>
    );
  }

  // Note: The API response structure is { data: { threads: [...] } }
  // where the first 'data' is from Axios and the second 'data' is from the API response
  const threads = data?.data?.threads || [];

  return (
    <div className="flex flex-col gap-1">

      {threads.map((thread) => (
        <div
          key={thread.thread_id}
          className={`group flex h-9 items-center rounded-lg transition-colors hover:bg-muted focus-visible:bg-muted focus-visible:outline-none ${
            currentThreadId === thread.thread_id ? 'bg-muted' : ''
          }`}
        >
          <button
            className="flex h-full flex-1 items-center truncate px-3 text-start text-sm"
            onClick={() => handleSelectThread(thread.thread_id)}
          >
            {thread.title || 'New Chat'}
          </button>
          <TooltipIconButton
            variant="ghost"
            tooltip="Delete thread"
            className="mr-2 size-7 p-0 opacity-0 transition-opacity group-hover:opacity-100"
            onClick={(e) => handleDeleteThread(thread.thread_id, e)}
          >
            <ArchiveIcon className="size-4" />
          </TooltipIconButton>
        </div>
      ))}
    </div>
  );
};
