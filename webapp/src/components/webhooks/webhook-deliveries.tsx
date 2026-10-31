'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { DeliveryStatus, WebhookDelivery, useGetWebhookAuditQuery, useGetWebhookDeliveriesQuery } from '@app/store/workspaces/webhooks-api';
import { WAITING_STATUSES, deliveryErrorKey, formatDateTime, formatDuration } from '@app/utils/webhooks';

const PAGE = 20;
// How often the waiting count is asked again: a delivery is sent by a
// background job and ends as delivered or failed a little later.
const POLL_MS = 10_000;

type Filter = 'all' | 'delivered' | 'failed' | 'waiting';

const FILTER_STATUSES: Record<Filter, DeliveryStatus[]> = {
    all: [],
    delivered: ['delivered'],
    failed: ['failed', 'cancelled'],
    waiting: [...WAITING_STATUSES]
};

/**
 * "Deliveries": what each webhook sent for this form, newest first. Ids,
 * statuses, HTTP codes, attempt counts and timings only: the log never holds
 * an answer, a request or a reply, and is kept 30 days. Next to it, who
 * changed the webhooks and when.
 */
export default function WebhookDeliveries({ workspaceId, formId }: { workspaceId: string; formId: string }) {
    const { t, i18n } = useTranslation('builder');
    const [filter, setFilter] = useState<Filter>('all');
    const [limit, setLimit] = useState(PAGE);
    const [showChanges, setShowChanges] = useState(false);
    const waiting = useGetWebhookDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.waiting, limit: 1 }, { pollingInterval: POLL_MS });
    const delivered = useGetWebhookDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.delivered, limit: 1 });
    const failed = useGetWebhookDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES.failed, limit: 1 });
    const list = useGetWebhookDeliveriesQuery({ workspaceId, formId, status: FILTER_STATUSES[filter], limit }, { pollingInterval: (waiting.data?.total ?? 0) > 0 ? POLL_MS : 0 });
    const audit = useGetWebhookAuditQuery({ workspaceId, formId }, { skip: !showChanges });

    const items = list.data?.items ?? [];
    const total = list.data?.total ?? 0;
    const everything = (waiting.data?.total ?? 0) + (delivered.data?.total ?? 0) + (failed.data?.total ?? 0);
    const settled = !waiting.isLoading && !delivered.isLoading && !failed.isLoading;
    const forbidden = (waiting.error as any)?.status === 403;
    if (!settled || forbidden) return null;

    return (
        <section className="flex flex-col gap-4 rounded-lg border border-black-300 bg-white p-4 md:p-5" aria-labelledby="webhook-deliveries-title" data-testid="webhook-deliveries">
            <div className="flex flex-col gap-1">
                <h2 id="webhook-deliveries-title" className="text-sm font-semibold text-black-900">
                    {t('WEBHOOKS.DELIVERIES.TITLE')}
                </h2>
                <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('WEBHOOKS.DELIVERIES.INTRO')}</p>
            </div>

            <dl className="flex flex-wrap gap-x-8 gap-y-2">
                <Count label={t('WEBHOOKS.DELIVERIES.DELIVERED')} value={delivered.data?.total ?? 0} testId="webhook-count-delivered" />
                <Count label={t('WEBHOOKS.DELIVERIES.WAITING')} value={waiting.data?.total ?? 0} testId="webhook-count-waiting" />
                <Count label={t('WEBHOOKS.DELIVERIES.NOT_SENT')} value={failed.data?.total ?? 0} testId="webhook-count-failed" warn={(failed.data?.total ?? 0) > 0} />
            </dl>

            {everything === 0 && !list.isError && <p className="text-sm text-black-700">{t('WEBHOOKS.DELIVERIES.NONE')}</p>}

            {everything > 0 && (
                <div className="flex flex-col gap-1.5">
                    <label htmlFor="webhook-filter" className="text-xs font-medium text-black-700">
                        {t('WEBHOOKS.DELIVERIES.FILTER')}
                    </label>
                    <select
                        id="webhook-filter"
                        className="h-10 w-full rounded-md border border-control bg-white px-3 text-sm text-black-900 sm:max-w-60"
                        value={filter}
                        onChange={(e) => {
                            setFilter(e.target.value as Filter);
                            setLimit(PAGE);
                        }}
                    >
                        {(['all', 'delivered', 'failed', 'waiting'] as Filter[]).map((option) => (
                            <option key={option} value={option}>
                                {t(`WEBHOOKS.DELIVERIES.FILTER_${option.toUpperCase()}`)}
                            </option>
                        ))}
                    </select>
                </div>
            )}

            {list.isError && (
                <p role="alert" className="text-sm text-[#A83434]">
                    {t('WEBHOOKS.DELIVERIES.LOAD_ERROR')}
                </p>
            )}

            {items.length > 0 && (
                <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300" aria-label={t('WEBHOOKS.DELIVERIES.LIST')}>
                    {items.map((delivery) => (
                        <Row key={delivery.id} delivery={delivery} language={i18n.language} />
                    ))}
                </ul>
            )}
            {items.length > 0 && (
                <div className="flex flex-wrap items-center gap-3">
                    <p role="status" className="text-xs text-black-600">
                        {t('WEBHOOKS.DELIVERIES.SHOWING', { shown: items.length, total })}
                    </p>
                    {total > items.length && (
                        <Button type="button" variant="v2Button" size="sm" onClick={() => setLimit((current) => current + PAGE)}>
                            {t('WEBHOOKS.DELIVERIES.SHOW_MORE')}
                        </Button>
                    )}
                </div>
            )}
            <p className="text-xs text-black-600">{t('WEBHOOKS.DELIVERIES.RETENTION')}</p>

            <div className="flex flex-col gap-2">
                <div>
                    <Button type="button" variant="v2Button" size="sm" aria-expanded={showChanges} aria-controls="webhook-changes" onClick={() => setShowChanges((current) => !current)}>
                        {showChanges ? t('WEBHOOKS.CHANGES.HIDE') : t('WEBHOOKS.CHANGES.SHOW')}
                    </Button>
                </div>
                <div id="webhook-changes">
                    {showChanges && audit.isError && (
                        <p role="alert" className="text-sm text-[#A83434]">
                            {t('WEBHOOKS.CHANGES.LOAD_ERROR')}
                        </p>
                    )}
                    {showChanges && audit.data && audit.data.length === 0 && <p className="text-sm text-black-700">{t('WEBHOOKS.CHANGES.NONE')}</p>}
                    {showChanges && (audit.data?.length ?? 0) > 0 && (
                        <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300" aria-label={t('WEBHOOKS.CHANGES.LIST')}>
                            {audit.data!.map((entry) => (
                                <li key={entry.id} className="flex flex-col gap-0.5 px-3 py-2.5 text-sm text-black-900">
                                    <span>
                                        {t(`WEBHOOKS.CHANGES.EVENT.${entry.event}`, { defaultValue: entry.event })}
                                        {entry.host ? <span className="text-black-600"> · {entry.host}</span> : null}
                                        {entry.changed.length > 0 ? <span className="text-black-600"> · {entry.changed.map((c) => t(`WEBHOOKS.CHANGES.FIELD.${c}`, { defaultValue: c })).join(', ')}</span> : null}
                                    </span>
                                    <span className="text-xs text-black-600">{formatDateTime(entry.createdAt, i18n.language)}</span>
                                </li>
                            ))}
                        </ul>
                    )}
                </div>
            </div>
        </section>
    );
}

function Row({ delivery, language }: { delivery: WebhookDelivery; language: string }) {
    const { t } = useTranslation('builder');
    const bad = delivery.status === 'failed' || delivery.status === 'cancelled';
    const time = delivery.finishedAt ?? delivery.lastAttemptAt ?? delivery.createdAt;
    return (
        <li className="flex flex-col gap-1 px-3 py-3" data-testid={`webhook-delivery-${delivery.id}`}>
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                <span className="text-sm font-medium text-black-900">
                    <span className={bad ? 'text-[#A83434]' : undefined}>{t(`WEBHOOKS.DELIVERIES.STATUS.${delivery.status}`, { defaultValue: delivery.status })}</span>
                    {delivery.host ? <span className="font-normal break-all text-black-700"> · {delivery.host}</span> : null}
                    {delivery.event === 'test' ? <span className="font-normal text-black-700"> · {t('WEBHOOKS.DELIVERIES.TEST')}</span> : null}
                </span>
                <span className="text-xs text-black-600">{formatDateTime(time, language)}</span>
            </div>
            <p className="text-xs text-black-700">
                {t('WEBHOOKS.DELIVERIES.ATTEMPTS', { count: delivery.attempts })}
                {delivery.lastHttpStatus ? ` · HTTP ${delivery.lastHttpStatus}` : ''}
                {delivery.lastDurationMs !== null && delivery.lastDurationMs !== undefined ? ` · ${formatDuration(delivery.lastDurationMs)}` : ''}
                {delivery.responseId ? (
                    <>
                        {' · '}
                        {t('WEBHOOKS.DELIVERIES.SUBMISSION')} <code className="break-all">{delivery.responseId}</code>
                    </>
                ) : null}
            </p>
            {bad || delivery.status === 'retrying' ? (
                <p className="max-w-[70ch] text-sm leading-relaxed text-black-800">
                    {t(deliveryErrorKey(delivery.lastErrorCode), { status: delivery.lastHttpStatus ?? '' })}
                    {delivery.status === 'retrying' && delivery.nextAttemptAt ? ` ${t('WEBHOOKS.DELIVERIES.NEXT_ATTEMPT', { time: formatDateTime(delivery.nextAttemptAt, language) })}` : ''}
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
