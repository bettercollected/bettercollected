'use client';

import { useState } from 'react';

import { XIcon } from 'lucide-react';

import { Button } from '@app/shadcn/components/ui/button';
import useFormFieldsAtom from '@app/store/jotai/field-selectors';
import { useFormState } from '@app/store/jotai/form';
import { pruneOrphanedPipes } from '@app/utils/answer-piping';

// URL-parameter-safe names only; these become `?name=value` on the share link.
const VALID_NAME = /^[a-zA-Z0-9_-]+$/;

/**
 * Form-wide hidden fields: URL parameters (utm_source, name, …) the share
 * link can carry. Captured at fill time, stored with each response, and
 * available to answer piping in question text via the "@ Answer" menu.
 */
export default function HiddenFieldsEditor() {
    const { formState, setHiddenFields } = useFormState();
    const { formFields, setFormFields } = useFormFieldsAtom();
    const [draft, setDraft] = useState('');
    const [error, setError] = useState<string | null>(null);

    const names = formState.hiddenFields ?? [];

    const addName = () => {
        const name = draft.trim();
        if (!name) return;
        if (!VALID_NAME.test(name)) {
            setError('Use only letters, numbers, dashes and underscores.');
            return;
        }
        if (names.includes(name)) {
            setError('That hidden field already exists.');
            return;
        }
        setHiddenFields([...names, name]);
        setDraft('');
        setError(null);
    };

    const removeName = (name: string) => {
        setHiddenFields(names.filter((n) => n !== name));
        // Sweep any piping chips that referenced the removed name.
        setFormFields([...pruneOrphanedPipes(formFields, names.filter((n) => n !== name))]);
    };

    return (
        <div className="px-4 py-6">
            <div className="text-black-600 text-xs font-semibold uppercase tracking-wide">Hidden fields</div>
            <div className="text-black-500 mt-1 text-xs">
                Values passed in the share link (<span className="font-mono">?utm_source=…</span>) are saved with each response and can be piped into questions. Form-wide setting.
            </div>
            <div className="mt-3 flex flex-col gap-2">
                {names.map((name) => (
                    <div key={name} className="text-black-800 flex items-center justify-between rounded border px-2 py-1 text-xs">
                        <span className="truncate font-mono">{name}</span>
                        <div role="button" tabIndex={0} aria-label={`Remove hidden field ${name}`} className="cursor-pointer p-0.5 hover:text-red-500" onClick={() => removeName(name)}>
                            <XIcon className="h-3.5 w-3.5" />
                        </div>
                    </div>
                ))}
            </div>
            <div className="mt-2 flex items-center gap-2">
                <input
                    type="text"
                    placeholder="e.g. utm_source"
                    value={draft}
                    onChange={(e) => {
                        setDraft(e.target.value);
                        setError(null);
                    }}
                    onKeyDown={(e) => {
                        if (e.key === 'Enter') addName();
                    }}
                    className="border-black-300 focus:border-black-300 min-w-0 flex-1 rounded-lg border-[1px] p-2 text-xs"
                />
                <Button size="sm" variant="v2Button" onClick={addName} disabled={!draft.trim()}>
                    Add
                </Button>
            </div>
            {error && <div className="mt-1 text-xs text-amber-700">{error}</div>}
        </div>
    );
}
