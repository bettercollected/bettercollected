'use client';

import { useId, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { MAX_RESPONSE_LIMIT, fromLocalInputValue, opensBeforeCloses, parseResponseLimit, toLocalInputValue, viewerTimeZone } from '@app/utils/form-availability';

const FIELD = 'border-black-300 text-black-900 focus-visible:ring-brand-500 rounded border bg-white px-3 py-2 text-sm focus:outline-hidden focus-visible:ring-2';

type Labelling = { 'aria-labelledby'?: string; 'aria-describedby'?: string };

/**
 * The date and time a form starts taking responses. Typed in the viewer's
 * own time zone and stored as a UTC instant; respondents read it in theirs.
 * Saved with the button, never while the date is half typed. `onSave` gets
 * the instant, or "" to remove the date, and returns a truthy value when the
 * save failed (the field then keeps what was typed).
 */
export function OpenDateControl({ value, closeDate, onSave, ...labelling }: { value?: string | null; closeDate?: string | null; onSave: (instant: string) => Promise<unknown> | void } & Labelling) {
    const { t } = useTranslation();
    const noteId = useId();
    const [text, setText] = useState(toLocalInputValue(value));
    const [saving, setSaving] = useState(false);

    const instant = fromLocalInputValue(text);
    const beforeClose = !instant || opensBeforeCloses(instant, closeDate);
    const changed = text !== toLocalInputValue(value);
    const canSave = !!instant && changed && beforeClose && !saving;

    const save = async (next: string) => {
        setSaving(true);
        try {
            const failed = await onSave(next);
            if (!failed && next === '') setText('');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="flex flex-col items-start gap-2 sm:items-end">
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                <input
                    type="datetime-local"
                    className={FIELD}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    aria-invalid={!beforeClose || undefined}
                    aria-describedby={[labelling['aria-describedby'], noteId].filter(Boolean).join(' ')}
                    aria-labelledby={labelling['aria-labelledby']}
                    data-testid="open-date-input"
                />
                <Button type="button" variant="secondary" disabled={!canSave} onClick={() => instant && save(instant)}>
                    {t('FORM_PAGE.SETTINGS.OPEN_DATE.SAVE')}
                </Button>
                {!!value && (
                    <Button type="button" variant="ghost" disabled={saving} onClick={() => save('')}>
                        {t('FORM_PAGE.SETTINGS.OPEN_DATE.REMOVE')}
                    </Button>
                )}
            </div>
            <p id={noteId} role={beforeClose ? undefined : 'alert'} className={beforeClose ? 'max-w-[320px] text-left text-xs sm:text-right text-black-700' : 'max-w-[320px] text-left text-xs sm:text-right font-medium text-[#B42318]'}>
                {beforeClose ? t('FORM_PAGE.SETTINGS.OPEN_DATE.ZONE', { zone: viewerTimeZone() }) : t('FORM_PAGE.SETTINGS.OPEN_DATE.AFTER_CLOSE')}
            </p>
        </div>
    );
}

/**
 * The number of responses after which a form takes no more. A whole number
 * from 1 up; empty = no limit. `onSave` gets the number, or 0 to remove the
 * limit, and returns a truthy value when the save failed.
 */
export function ResponseLimitControl({ value, onSave, ...labelling }: { value?: number | null; onSave: (limit: number) => Promise<unknown> | void } & Labelling) {
    const { t } = useTranslation();
    const noteId = useId();
    const [text, setText] = useState(value ? String(value) : '');
    const [saving, setSaving] = useState(false);

    const parsed = parseResponseLimit(text);
    const changed = (parsed.value ?? 0) !== (value ?? 0);
    const canSave = !parsed.error && changed && !saving;

    const save = async (next: number) => {
        setSaving(true);
        try {
            const failed = await onSave(next);
            if (!failed && next === 0) setText('');
        } finally {
            setSaving(false);
        }
    };

    return (
        <div className="flex flex-col items-start gap-2 sm:items-end">
            <div className="flex flex-wrap items-center gap-2 sm:justify-end">
                <input
                    type="text"
                    inputMode="numeric"
                    autoComplete="off"
                    className={`${FIELD} w-32`}
                    value={text}
                    onChange={(event) => setText(event.target.value)}
                    placeholder={t('FORM_PAGE.SETTINGS.RESPONSE_LIMIT.PLACEHOLDER')}
                    aria-invalid={parsed.error || undefined}
                    aria-describedby={[labelling['aria-describedby'], noteId].filter(Boolean).join(' ')}
                    aria-labelledby={labelling['aria-labelledby']}
                    data-testid="response-limit-input"
                />
                <Button type="button" variant="secondary" disabled={!canSave} onClick={() => save(parsed.value ?? 0)}>
                    {t('FORM_PAGE.SETTINGS.RESPONSE_LIMIT.SAVE')}
                </Button>
                {!!value && (
                    <Button type="button" variant="ghost" disabled={saving} onClick={() => save(0)}>
                        {t('FORM_PAGE.SETTINGS.RESPONSE_LIMIT.REMOVE')}
                    </Button>
                )}
            </div>
            <p id={noteId} role={parsed.error ? 'alert' : undefined} className={parsed.error ? 'max-w-[320px] text-left text-xs sm:text-right font-medium text-[#B42318]' : 'max-w-[320px] text-left text-xs sm:text-right text-black-700'}>
                {parsed.error ? t('FORM_PAGE.SETTINGS.RESPONSE_LIMIT.INVALID', { max: MAX_RESPONSE_LIMIT.toLocaleString('en-GB') }) : t('FORM_PAGE.SETTINGS.RESPONSE_LIMIT.NOTE')}
            </p>
        </div>
    );
}
