'use client';

import { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { DEFAULT_DRAFT_DAYS, parseDraftDays } from '@app/utils/form-drafts';

const FIELD = 'border-black-300 text-black-900 focus-visible:ring-brand-500 rounded border bg-white px-3 py-2 text-sm focus:outline-hidden focus-visible:ring-2';

/**
 * How many days after the last save a draft is kept (the setting "Let
 * respondents save and continue later" is on). A whole number from 1 to 90;
 * empty = the default of 30. `onSave` gets the number, or 0 for the default,
 * and returns a truthy value when the save failed.
 */
export function DraftRetentionControl({ value, onSave }: { value?: number | null; onSave: (days: number) => Promise<unknown> | void }) {
    const { t } = useTranslation();
    const inputId = useId();
    const noteId = useId();
    const [text, setText] = useState(value ? String(value) : '');
    const [saving, setSaving] = useState(false);

    const parsed = parseDraftDays(text);
    const changed = (parsed.value ?? 0) !== (value ?? 0);
    const canSave = !parsed.error && changed && !saving;

    const save = async () => {
        setSaving(true);
        try {
            await onSave(parsed.value ?? 0);
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="mt-2 flex flex-col items-start gap-2">
            <label htmlFor={inputId} className="text-sm font-medium text-black-900">
                {t('FORM_PAGE.SETTINGS.SAVE_DRAFT.DAYS_LABEL')}
            </label>
            <div className="flex flex-wrap items-center gap-2">
                <input
                    id={inputId}
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    className={`${FIELD} w-24`}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    placeholder={String(DEFAULT_DRAFT_DAYS)}
                    aria-invalid={parsed.error || undefined}
                    aria-describedby={noteId}
                    data-testid="draft-days-input"
                />
                <Button type="button" variant="secondary" disabled={!canSave} onClick={save}>
                    {t('FORM_PAGE.SETTINGS.SAVE_DRAFT.SAVE')}
                </Button>
            </div>
            <p id={noteId} role={parsed.error ? 'alert' : undefined} className={parsed.error ? 'max-w-[420px] text-xs font-medium text-[#B42318]' : 'max-w-[420px] text-xs text-black-700'}>
                {parsed.error ? t('FORM_PAGE.SETTINGS.SAVE_DRAFT.INVALID') : t('FORM_PAGE.SETTINGS.SAVE_DRAFT.NOTE', { default: DEFAULT_DRAFT_DAYS })}
            </p>
        </div>
    );
}
