'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { inputClass } from '@app/components/registration/field';
import { Button } from '@app/shadcn/components/ui/button';
import { EmailDelivery, useGetEmailDeliveriesQuery } from '@app/store/workspaces/email-actions-api';
import { DeliveryStatus } from '@app/store/workspaces/webhooks-api';
import { CHANNEL_KEY, deliveryErrorKey } from '@app/utils/email-actions';
import { WAITING_STATUSES, formatDateTime } from '@app/utils/webhooks';

const PAGE = 20;
const POLL_MS = 10_000;

type Filter = 'all' | 'delivered' | 'failed' | 'waiting';
const FILTER_STATUSES: Record<Filter, DeliveryStatus[]> = { all: [], delivered: ['delivered'], failed: ['failed', 'cancelled'], waiting: [...WAITING_STATUSES] };

/**
 * "Sent mails": what each email action did for this form, newest first. Ids,
 * statuses, attempt counts and timings only: never an address, a subject or an
 * answer. Kept 30 days.
 */
export default function EmailDeliveries({ workspaceId, formId }: { workspaceId: string; formId: string }) {
    const { t, i18n } = useTranslation('builder');
    const [filter, setFilter] = useState<Filter>('all');
    const [limit, setLimit] = useState(PAGE);
    const waiting = useGetEmailDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.waiting, limit: 1 }, { pollingInterval: POLL_MS });
    const delivered = useGetEmailDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.delivered, limit: 1 });
    const failed = useGetEmailDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.failed, limit: 1 });
    const list = useGetEmailDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES[filter], limit });

    const items = list.data?.items ?? [];
    const total = list.data?.total ?? 0;
    const everything = (waiting.data?.total ?? 0) + (delivered.data?.total ?? 0) + (failed.data?.total ?? 0);
    const settled = !waiting.isLoading && !delivered.isLoading && !failed.isLoading;
    if (!settled || (waiting.error as any)?.status === 403) return null;

    return (
        <section className="flex flex-col gap-4 rounded-lg border border-black-300 bg-white p-4 md:p-5" aria-labelledby="email-deliveries-title" data-testid="email-deliveries">
            <div className="flex flex-col gap-1">
                <h2 id="email-deliveries-title" className="text-sm font-semibold text-black-900">
                    {t('EMAIL_ACTIONS.DELIVERIES.TITLE')}
                </h2>
                <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('EMAIL_ACTIONS.DELIVERIES.INTRO')}</p>
            </div>
            <dl className="flex flex-wrap gap-x-8 gap-y-2">
                <Count label={t('EMAIL_ACTIONS.DELIVERIES.SENT')} value={delivered.data?.total ?? 0} testId="email-count-delivered" />
                <Count label={t('EMAIL_ACTIONS.DELIVERIES.WAITING')} value={waiting.data?.total ?? 0} testId="email-count-waiting" />
                <Count label={t('EMAIL_ACTIONS.DELIVERIES.NOT_SENT')} value={failed.data?.total ?? 0} testId="email-count-failed" warn={(failed.data?.total ?? 0) > 0} />
            </dl>
            {everything === 0 && !list.isError && <p className="text-sm text-black-700">{t('EMAIL_ACTIONS.DELIVERIES.NONE')}</p>}
            {everything > 0 && (
                <div className="flex flex-col gap-1.5">
                    <label htmlFor="email-filter" className="text-xs font-medium text-black-700">
                        {t('EMAIL_ACTIONS.DELIVERIES.FILTER')}
                    </label>
                    <select id="email-filter" className={inputClass + ' sm:max-w-60'} value={filter} onChange={(e) => (setFilter(e.target.value as Filter), setLimit(PAGE))}>
                        {(['all', 'delivered', 'failed', 'waiting'] as Filter[]).map((option) => (
                            <option key={option} value={option}>
                                {t(`EMAIL_ACTIONS.DELIVERIES.FILTER_${option.toUpperCase()}`)}
                            </option>
                        ))}
                    </select>
                </div>
            )}
            {list.isError && (
                <p role="alert" className="text-sm text-[#A83434]">
                    {t('EMAIL_ACTIONS.DELIVERIES.LOAD_ERROR')}
                </p>
            )}
            {items.length > 0 && (
                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300" aria-label={t('EMAIL_ACTIONS.DELIVERIES.LIST')}>
                    {items.map((delivery) => (
                        <Row key={delivery.id} delivery={delivery} language={i18n.language} />
                    ))}
                </ul>
            )}
            {items.length > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                    <p role="status" className="text-xs text-black-600">
                        {t('EMAIL_ACTIONS.DELIVERIES.SHOWING', { shown: items.length, total })}
                    </p>
                    {total > items.length && (
                        <Button type="button" variant="v2Button" size="sm" onClick={() => setLimit((current) => current + PAGE)}>
                            {t('EMAIL_ACTIONS.DELIVERIES.SHOW_MORE')}
                        </Button>
                    )}
                </div>
            )}
            <p className="text-xs text-black-600">{t('EMAIL_ACTIONS.DELIVERIES.RETENTION')}</p>
        </section>
    );
}

function Row({ delivery, language }: { delivery: EmailDelivery; language: string }) {
    const { t } = useTranslation('builder');
    const bad = delivery.status === 'failed' || delivery.status === 'cancelled';
    const time = delivery.finishedAt ?? delivery.lastAttemptAt ?? delivery.createdAt;
    return (
        <li className="flex flex-col gap-1 px-3 py-3" data-testid={`email-delivery-${delivery.id}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="text-sm font-medium text-black-900">
                    <span className={bad ? 'text-[#A83434]' : undefined}>{t(`EMAIL_ACTIONS.DELIVERIES.STATUS.${delivery.status}`, { defaultValue: delivery.status })}</span>
                    <span className="font-normal text-black-700"> · {t(CHANNEL_KEY(delivery.channel))}</span>
                    {delivery.event === 'test' ? <span className="font-normal text-black-700"> · {t('EMAIL_ACTIONS.DELIVERIES.TEST')}</span> : null}
                </span>
                <span className="text-xs text-black-600">{formatDateTime(time, language)}</span>
            </div>
            <p className="text-xs text-black-700">
                {t('EMAIL_ACTIONS.DELIVERIES.ATTEMPTS', { count: delivery.attempts })}
                {delivery.responseId ? (
                    <>
                        {' · '}
                        {t('EMAIL_ACTIONS.DELIVERIES.SUBMISSION')} <code className="break-all">{delivery.responseId}</code>
                    </>
                ) : null}
            </p>
            {bad || delivery.status === 'retrying' ? (
                <p className="max-w-[70ch] text-sm leading-relaxed text-black-800">
                    {t(deliveryErrorKey(delivery.lastErrorCode))}
                    {delivery.status === 'retrying' && delivery.nextAttemptAt ? ` ${t('EMAIL_ACTIONS.DELIVERIES.NEXT_ATTEMPT', { time: formatDateTime(delivery.nextAttemptAt, language) })}` : ''}
                </p>
            ) : null}
        </li>
    );
}

function Count({ label, value, testId, warn = false }: { label: string; value: number; testId: string; warn?: boolean }) {
    return (
        <div className="flex flex-col">
            <dt className="text-xs font-medium text-black-600">{label}</dt>
            <dd className={warn ? 'text-lg font-semibold text-[#A83434] tabular-nums' : 'text-lg font-semibold text-black-900 tabular-nums'} data-testid={testId}>
                {value}
            </dd>
        </div>
    );
}
