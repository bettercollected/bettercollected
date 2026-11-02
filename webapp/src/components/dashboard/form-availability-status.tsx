'use client';

import { Fragment } from 'react';

import { useTranslation } from 'react-i18next';

import cn from 'classnames';

import { StandardFormDto } from '@app/models/dtos/form';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { availabilityState } from '@app/utils/form-availability';

/**
 * One line that says whether respondents can send answers right now and why:
 * "Open · closes 12 December 2026 at 18:00 · 37 of 100 responses". The state is
 * a word, never just a colour. It is a polite live region, so a change made
 * below (closing the form, a new limit) is read out once it is saved.
 */
export default function FormAvailabilityStatus({ form }: { form: StandardFormDto }) {
    const { t, i18n } = useTranslation();
    const state = availabilityState(form as any);
    const date = (instant: string) => utcToLocalDateTimeIn(instant, i18n.language);
    const limit = form?.settings?.responseLimit;
    const responses = form?.responses ?? 0;
    const count = limit ? t('STAFF.FORM_SETTINGS.STATUS_COUNT_OF', { n: responses, limit }) : t('FORM_SHELL.RESPONSES', { count: responses });

    let label: string;
    let tone: 'open' | 'waiting' | 'stopped';
    let parts: string[];
    switch (state.kind) {
        case 'draft':
            label = t('STAFF.FORM_SETTINGS.STATUS_DRAFT');
            tone = 'waiting';
            parts = [t('STAFF.FORM_SETTINGS.STATUS_DRAFT_NOTE')];
            break;
        case 'closed':
            label = t('STAFF.FORM_SETTINGS.STATUS_CLOSED');
            tone = 'stopped';
            parts = [t('STAFF.FORM_SETTINGS.STATUS_SINCE', { date: date(state.since) }), count];
            break;
        case 'full':
            label = t('STAFF.FORM_SETTINGS.STATUS_FULL');
            tone = 'stopped';
            parts = [t('STAFF.FORM_SETTINGS.STATUS_LIMIT_REACHED', { limit: state.limit })];
            break;
        case 'not-open':
            label = t('STAFF.FORM_SETTINGS.STATUS_NOT_OPEN');
            tone = 'waiting';
            parts = [t('STAFF.FORM_SETTINGS.STATUS_OPENS', { date: date(state.opens) }), ...(state.closes ? [t('STAFF.FORM_SETTINGS.STATUS_CLOSES', { date: date(state.closes) })] : []), count];
            break;
        default:
            label = t('STAFF.FORM_SETTINGS.STATUS_OPEN');
            tone = 'open';
            parts = [...(state.closes ? [t('STAFF.FORM_SETTINGS.STATUS_CLOSES', { date: date(state.closes) })] : []), count];
    }

    return (
        <div role="status" aria-label={t('STAFF.FORM_SETTINGS.STATUS_LABEL')} data-testid="availability-status" className="bg-black-100 border-black-300 mb-2 mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border px-4 py-3 text-sm">
            <span className={cn('inline-flex items-center gap-1.5 font-semibold', tone === 'open' ? 'text-success-700' : tone === 'stopped' ? 'text-amber-900' : 'text-black-800')}>
                <span aria-hidden="true" className={cn('h-2 w-2 rounded-full', tone === 'open' ? 'bg-success-700' : tone === 'stopped' ? 'bg-amber-500' : 'bg-black-600')} />
                {label}
            </span>
            {parts.map((part, index) => (
                <Fragment key={index}>
                    <span aria-hidden="true" className="text-black-600">
                        ·
                    </span>
                    <span className="sr-only">, </span>
                    <span className="text-black-800 tabular-nums">{part}</span>
                </Fragment>
            ))}
        </div>
    );
}
