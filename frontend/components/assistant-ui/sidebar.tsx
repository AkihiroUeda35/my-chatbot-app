'use client';

import { CustomThreadList } from '@/components/assistant-ui/custom-thread-list';
import { ThemeToggle } from '@/components/ui/theme-toggle';
import { Menu, PenSquare } from 'lucide-react';
import { FC } from 'react';
import { useSidebarStore } from '@/lib/sidebar-store';

interface SidebarProps {
  currentThreadId: string | null;
  onThreadSelect: (threadId: string | null) => void;
}

export const Sidebar: FC<SidebarProps> = ({ currentThreadId, onThreadSelect }) => {
  const { isOpen, toggle } = useSidebarStore();

  const handleNewThread = () => {
    onThreadSelect(null);
  };

  return (
    <>
      {/* Overlay for mobile */}
      {isOpen && (
        <div 
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={toggle}
        />
      )}
      
      {/* Sidebar */}
      <aside 
        className={`
          fixed lg:static inset-y-0 left-0 z-50
          border-r border-border bg-background p-4
          transition-all duration-300 ease-in-out
          ${isOpen ? 'w-64' : 'w-16'}
        `}
      >
        <div className="flex flex-col gap-2">
          {/* Top controls */}
          <div className="flex items-center gap-2">
            {/* Hamburger menu button */}
            <button
              onClick={toggle}
              className="p-2 rounded-md hover:bg-muted transition-all flex-shrink-0"
              aria-label={isOpen ? 'Close sidebar' : 'Open sidebar'}
            >
              <Menu className="h-5 w-5" />
            </button>
            
            
            {/* Theme toggle - only when open */}
            {isOpen && (
              <div className="ml-auto">
                <ThemeToggle />
              </div>
            )}
          </div>
          
            <div className="flex items-center gap-2">
              <button
                onClick={handleNewThread}
                className="p-2 rounded-md hover:bg-muted transition-all flex items-center gap-2 flex-shrink-0 whitespace-nowrap"
                aria-label="New thread"
              >
                <PenSquare className="h-5 w-5 flex-shrink-0" />
                {isOpen && <span className="text-sm">New Thread</span>}
              </button>
            </div>
          
          {/* Thread list - only when open */}
          {isOpen && (
            <div className="mt-2">
              <CustomThreadList 
                currentThreadId={currentThreadId}
                onThreadSelect={onThreadSelect}
              />
            </div>
          )}
        </div>
      </aside>
    </>
  );
};
