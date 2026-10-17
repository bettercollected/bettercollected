'use client';

import { useState } from 'react';

import { useAppSelector } from '@app/store/hooks';
import { useImportImageFromUrlMutation } from '@app/store/media-library/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

export const COPY_FAILED_MESSAGE = "We couldn't copy that image. Upload it instead.";

/** What to tell the person when a copy fails: the server's plain-language
 * message when it sent one, else the generic one. */
export function importErrorMessage(error: unknown): string {
    const message = (error as { data?: { message?: unknown } } | undefined)?.data?.message;
    return typeof message === 'string' && message.trim() ? message : COPY_FAILED_MESSAGE;
}

/**
 * A pasted image address, copied into our storage before the theme uses it
 * (POST /workspaces/{id}/images/import), so respondents' browsers never load
 * it from the address's own host. The field shows the stored address; a new
 * one takes effect only once copied.
 */
export default function ImageUrlField({ value, onChange, label = 'Background image URL' }: { value: string; onChange: (url: string) => void; label?: string }) {
    const workspace = useAppSelector(selectWorkspace);
    const [importImage, { isLoading }] = useImportImageFromUrlMutation();
    const [draft, setDraft] = useState(value);
    const [error, setError] = useState('');
    // a new stored address (another theme picked, or our copy) replaces the draft
    const [shown, setShown] = useState(value);
    if (shown !== value) {
        setShown(value);
        setDraft(value);
    }

    const pending = draft.trim() !== value;

    const copy = async () => {
        const url = draft.trim();
        setError('');
        if (!url) {
            onChange('');
            return;
        }
        if (!workspace?.id) {
            setError(COPY_FAILED_MESSAGE);
            return;
        }
        const result: any = await importImage({ workspace_id: workspace.id, url });
        if (result && 'data' in result && typeof result.data?.url === 'string') {
            onChange(result.data.url);
            setDraft(result.data.url);
        } else {
            setError(importErrorMessage(result?.error));
        }
    };

    return (
        <div className="flex flex-col gap-1.5">
            <div className="flex gap-1.5">
                <input
                    type="url"
                    aria-label={label}
                    aria-invalid={!!error}
                    placeholder="https://…"
                    value={draft}
                    disabled={isLoading}
                    onChange={(e) => {
                        setDraft(e.target.value);
                        setError('');
                    }}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            if (pending) copy();
                        }
                    }}
                    className="border-black-300 text-black-800 placeholder:text-black-600 focus:border-brand-500 min-w-0 flex-1 rounded-md border bg-white px-2.5 py-1.5 text-xs outline-hidden"
                />
                <button
                    type="button"
                    onClick={copy}
                    disabled={isLoading || !pending}
                    className="border-black-300 text-black-800 hover:bg-black-100 shrink-0 rounded-md border bg-white px-2.5 py-1.5 text-xs font-medium disabled:cursor-default disabled:opacity-50"
                >
                    {isLoading ? 'Copying…' : 'Use image'}
                </button>
            </div>
            {error && (
                <p role="alert" className="text-[11px] leading-relaxed text-red-600">
                    {error}
                </p>
            )}
            <p className="text-black-600 text-[11px] leading-relaxed">Paste an image address. We copy the image into this workspace, so respondents load it from here. The background colour shows while it loads.</p>
        </div>
    );
}
