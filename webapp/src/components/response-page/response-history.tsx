'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { StandardFormDto, StandardFormFieldDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { RevisionEntry, RevisionValues, useGetResponseRevisionsQuery, useLazyGetResponseRevisionValuesQuery } from '@app/store/workspaces/response-revisions-api';
import { utcToLocalDateTimeIn } from '@app/utils/date-utils';
import { getAnswerForField } from '@app/utils/form-builder-block-utils';
import { pageQuestions } from '@app/utils/staff-answers';

function who(t: (key: string, options?: any) => string, entry: RevisionEntry): string {
    const { actor } = entry;
    if (actor.kind === 'respondent') return t('RESPONSE_HISTORY.BY_RESPONDENT');
    if (actor.former) return actor.role ? t('RESPONSE_HISTORY.BY_FORMER_ROLE', { role: t(`WORKSPACE_ROLES.${actor.role}.NAME`, { defaultValue: actor.role }) }) : t('RESPONSE_HISTORY.BY_FORMER');
    const role = actor.role ? t(`WORKSPACE_ROLES.${actor.role}.NAME`, { defaultValue: '' }) : '';
    if (actor.name && role) return t('RESPONSE_HISTORY.BY_MEMBER', { name: actor.name, role });
    if (actor.name) return actor.name;
    return role ? t('RESPONSE_HISTORY.BY_ROLE', { role }) : t('RESPONSE_HISTORY.BY_STAFF');
}

/**
 * The history of a response (needs response.read, behind the server's
 * RESPONSE_REVISIONS_ENABLED): who changed answers, when and which questions;
 * "Show previous values" opens one entry's values from the server and forgets
 * them when closed. Staff only; never printed.
 */
export default function ResponseHistory({ workspaceId, formId, responseId, form }: { workspaceId: string; formId: string; responseId: string; form: StandardFormDto }) {
    const { t, i18n } = useTranslation();
    const { data, isLoading, isError, refetch } = useGetResponseRevisionsQuery({ workspaceId, formId, responseId });
    const [openSeq, setOpenSeq] = useState<number | null>(null);
    const [loadValues, values] = useLazyGetResponseRevisionValuesQuery();
    const questions = new Map<string, StandardFormFieldDto>(pageQuestions(form).map((field) => [field.id, field]));
    // newest first
    const entries = [...(data?.revisions ?? [])].reverse();

    const toggle = (seq: number) => {
        if (openSeq === seq) {
            setOpenSeq(null);
            return;
        }
        setOpenSeq(seq);
        loadValues({ workspaceId, formId, responseId, seq });
    };

    return (
        <section aria-labelledby="response-history-heading" className="flex flex-col gap-3 rounded-lg border border-black-300 bg-white p-4 print:hidden" data-testid="response-history">
            <h2 id="response-history-heading" className="text-sm font-semibold text-black-800">
                {t('RESPONSE_HISTORY.TITLE')}
            </h2>
            <p className="text-xs text-black-600">{t('RESPONSE_HISTORY.NOTE')}</p>
            {isLoading && (
                <p role="status" className="text-sm text-black-700">
                    {t('RESPONSE_HISTORY.LOADING')}
                </p>
            )}
            {isError && (
                <div role="alert" className="flex flex-wrap items-center gap-3 text-sm">
                    <span>{t('RESPONSE_HISTORY.LOAD_ERROR')}</span>
                    <Button variant="v2Button" size="sm" onClick={() => refetch()}>
                        {t('RESPONSE_HISTORY.RETRY')}
                    </Button>
                </div>
            )}
            {!isLoading && !isError && entries.length === 0 && <p className="text-sm">{t('RESPONSE_HISTORY.EMPTY')}</p>}
            {entries.length > 0 && (
                <ol className="flex flex-col divide-y divide-black-300">
                    {entries.map((entry) => {
                        const opened = openSeq === entry.seq;
                        const shown: RevisionValues | undefined = opened && values.data?.seq === entry.seq ? values.data : undefined;
                        return (
                            <li key={entry.seq} className="flex flex-col gap-1.5 py-3 first:pt-0 last:pb-0" data-testid={`revision-${entry.seq}`}>
                                <p className="text-sm">
                                    <span className="font-medium">{who(t, entry)}</span> {t('RESPONSE_HISTORY.CHANGED', { count: entry.changed.length })}
                                    {entry.at ? <span className="text-black-600"> · {utcToLocalDateTimeIn(entry.at, i18n.language)}</span> : null}
                                </p>
                                <p className="text-sm break-words text-black-700">{entry.changed.map((item) => item.title || t('RESPONSE_HISTORY.UNTITLED')).join(', ')}</p>
                                <div>
                                    <Button variant="v2Button" size="sm" aria-expanded={opened} aria-controls={`revision-values-${entry.seq}`} onClick={() => toggle(entry.seq)}>
                                        {opened ? t('RESPONSE_HISTORY.HIDE_VALUES') : t('RESPONSE_HISTORY.SHOW_VALUES')}
                                    </Button>
                                </div>
                                <div id={`revision-values-${entry.seq}`} aria-live="polite">
                                    {opened && values.isFetching && <p className="text-sm text-black-700">{t('RESPONSE_HISTORY.LOADING')}</p>}
                                    {opened && values.isError && (
                                        <p role="alert" className="text-sm">
                                            {t('RESPONSE_HISTORY.VALUES_ERROR')}
                                        </p>
                                    )}
                                    {shown && (
                                        <dl className="mt-1 flex flex-col gap-2 rounded bg-black-100 p-3 text-sm" data-testid={`revision-values-${entry.seq}`}>
                                            {entry.changed.map((item) => {
                                                const field = questions.get(item.id);
                                                const answer = shown.values[item.id];
                                                const text = answer && field ? String(getAnswerForField({ answers: { [item.id]: answer } } as any, field) ?? '') : '';
                                                return (
                                                    <div key={item.id} className="flex flex-col gap-0.5">
                                                        <dt className="text-xs text-black-600">{item.title || t('RESPONSE_HISTORY.UNTITLED')}</dt>
                                                        <dd className="break-words">{text || t('RESPONSE_HISTORY.NO_ANSWER')}</dd>
                                                    </div>
                                                );
                                            })}
                                        </dl>
                                    )}
                                </div>
                            </li>
                        );
                    })}
                </ol>
            )}
        </section>
    );
}
