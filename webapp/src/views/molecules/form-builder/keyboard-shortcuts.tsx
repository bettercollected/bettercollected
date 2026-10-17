'use client';

import { useState } from 'react';

import { Keyboard } from 'lucide-react';

import { BUILDER_SHORTCUTS, useBuilderShortcuts } from '@app/lib/hooks/use-builder-shortcuts';
import { Popover, PopoverContent, PopoverTrigger } from '@app/shadcn/components/ui/popover';

/**
 * The builder's keyboard shortcuts: turns them on, and lists them in a
 * popover (the keyboard button, or "?").
 */
export default function KeyboardShortcuts() {
    const [open, setOpen] = useState(false);
    useBuilderShortcuts({ openHelp: () => setOpen(true) });

    return (
        <Popover open={open} onOpenChange={setOpen}>
            <PopoverTrigger asChild>
                <button type="button" aria-label="Keyboard shortcuts" aria-keyshortcuts="?" title="Keyboard shortcuts (?)" className="rounded-md p-1.5 text-black-600 hover:bg-black-100 hover:text-black-900">
                    <Keyboard className="h-4 w-4" aria-hidden="true" />
                </button>
            </PopoverTrigger>
            <PopoverContent align="end" className="w-[340px] p-0" aria-labelledby="keyboard-shortcuts-title">
                <h2 id="keyboard-shortcuts-title" className="border-b border-black-300 px-4 py-3 text-sm font-semibold text-black-900">
                    Keyboard shortcuts
                </h2>
                <p className="px-4 pt-3 text-xs text-black-700">Question shortcuts act on the selected question when you are not typing in it.</p>
                <dl className="space-y-2 px-4 py-3 text-sm">
                    {BUILDER_SHORTCUTS.map((shortcut) => (
                        <div key={shortcut.label} className="flex items-start justify-between gap-4">
                            <dt className="text-black-800">{shortcut.label}</dt>
                            <dd className="flex shrink-0 gap-1">
                                {shortcut.keys.map((key) => (
                                    <kbd key={key} className="rounded border border-black-400 bg-black-100 px-1.5 py-0.5 font-sans text-xs text-black-800">
                                        {key}
                                    </kbd>
                                ))}
                            </dd>
                        </div>
                    ))}
                </dl>
            </PopoverContent>
        </Popover>
    );
}
