'use client';

import React, { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useRegistrationEnabled } from '@app/components/registration/use-registration-enabled';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { RegistrationDelivery, useGetFormRegistrationQuery, useGetRegistrationDeliveriesQuery, useRetryRegistrationDeliveryMutation } from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ATTENTION_STATUSES, WAITING_STATUSES, deliveryErrorKey, errorCodeOf, errorKey, formatDateTime } from '@app/utils/registration';

const PAGE = 50;

/**
 * The Responses tab's "Sending to a case system": how many submissions
 * arrived and are waiting, and the ones that were not sent, each with the
 * reason in a sentence and a Retry button for editors. Ids and codes only:
 * a delivery never carries answer content. Hidden while the feature is off,
 * for members who cannot read responses, and for a form that never sent.
 */
export default function DeliveriesPanel() {
    const { enabled } = useRegistrationEnabled();
    const { can } = useWorkspacePermissions();
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    if (!enabled || !can(WorkspacePermission.RESPONSE_READ) || !workspace?.id || !form?.formId) return null;
    return <Deliveries workspaceId={workspace.id} formId={form.formId} canRetry={can(WorkspacePermission.FORM_EDIT)} />;
}

export function Deliveries({ workspaceId, formId, canRetry }: { workspaceId: string; formId: string; canRetry: boolean }) {
    const { t, i18n } = useTranslation('builder');
    const [limit, setLimit] = useState(PAGE);
    const registration = useGetFormRegistrationQuery({ workspaceId, formId });
    const attention = useGetRegistrationDeliveriesQuery({ workspaceId, formId, status: [...ATTENTION_STATUSES], limit });
    const delivered = useGetRegistrationDeliveriesQuery({ workspaceId, formId, status: ['delivered'], limit: 1 });
    const waiting = useGetRegistrationDeliveriesQuery({ workspaceId, formId, status: [...WAITING_STATUSES], limit: 1 });
    const [retry] = useRetryRegistrationDeliveryMutation();
    const [retrying, setRetrying] = useState<string | null>(null);
    const [message, setMessage] = useState<{ id: string; text: string; failed: boolean } | null>(null);

    const failed = attention.data?.items ?? [];
    const failedTotal = attention.data?.total ?? 0;
    const deliveredTotal = delivered.data?.total ?? 0;
    const waitingTotal = waiting.data?.total ?? 0;
    const settled = !registration.isLoading && !attention.isLoading && !delivered.isLoading && !waiting.isLoading;
    // A form that never sent has nothing to show.
    if (!settled || (!registration.data?.enabled && failedTotal + deliveredTotal + waitingTotal === 0)) return null;

    const retryOne = async (delivery: RegistrationDelivery) => {
        setRetrying(delivery.id);
        setMessage(null);
        const response: any = await retry({ workspaceId, formId, deliveryId: delivery.id });
        setRetrying(null);
        if (response.error) setMessage({ id: delivery.id, text: t(errorKey(errorCodeOf(response.error))), failed: true });
        else setMessage({ id: delivery.id, text: t('REGISTRATION.DELIVERY.RETRY_STARTED'), failed: false });
    };

    const reason = (delivery: RegistrationDelivery) => t(deliveryErrorKey(delivery.lastErrorCode), { status: delivery.lastHttpStatus ?? '' });

    return (
        <section className="mb-6 flex flex-col gap-4 rounded-lg border border-black-300 bg-white p-4 md:p-5" aria-labelledby="registration-deliveries-title" data-testid="registration-deliveries">
            <div className="flex flex-col gap-1">
                <h2 id="registration-deliveries-title" className="text-sm font-semibold text-black-900">
                    {t('REGISTRATION.DELIVERY.TITLE')}
                </h2>
                {registration.data?.serviceName && <p className="text-xs break-words text-black-600">{t('REGISTRATION.DELIVERY.SENDING_TO', { name: registration.data.serviceName })}</p>}
            </div>

            <dl className="flex flex-wrap gap-x-8 gap-y-2">
                <Count label={t('REGISTRATION.DELIVERY.DELIVERED')} value={deliveredTotal} testId="registration-count-delivered" />
                <Count label={t('REGISTRATION.DELIVERY.WAITING')} value={waitingTotal} testId="registration-count-waiting" />
                <Count label={t('REGISTRATION.DELIVERY.NOT_SENT')} value={failedTotal} testId="registration-count-failed" warn={failedTotal > 0} />
            </dl>

            {attention.isError && (
                <p role="alert" className="text-sm text-[#A83434]">
                    {t('REGISTRATION.DELIVERY.LOAD_ERROR')}
                </p>
            )}

            {failedTotal === 0 && !attention.isError && <p className="text-sm text-black-700">{t('REGISTRATION.DELIVERY.NONE_FAILED')}</p>}

            {failed.length > 0 && (
                <div className="flex flex-col gap-2">
                    <p role="alert" className="text-sm font-medium text-[#7A2525]">
                        {t('REGISTRATION.DELIVERY.FAILED_BANNER', { count: failedTotal })}
                    </p>
                    <ul className="flex flex-col divide-y divide-black-200 rounded-md border border-black-300" aria-label={t('REGISTRATION.DELIVERY.NOT_SENT')}>
                        {failed.map((delivery) => (
                            <li key={delivery.id} className="flex flex-col gap-2 px-3 py-3 sm:flex-row sm:items-start sm:justify-between" data-testid={`registration-delivery-${delivery.id}`}>
                                <div className="flex min-w-0 flex-col gap-1">
                                    <div className="flex flex-wrap items-center gap-2">
                                        <span className="text-sm text-black-900">
                                            {t('REGISTRATION.DELIVERY.SUBMISSION')} <code className="text-xs break-all">{delivery.responseId}</code>
                                        </span>
                                        <span className="rounded-full bg-[#FBEFEF] px-2 py-0.5 text-xs font-semibold text-[#7A2525]">{t(`REGISTRATION.DELIVERY.STATUS.${delivery.status}`)}</span>
                                    </div>
                                    <p className="text-sm text-black-800">{delivery.status === 'cancelled' && !delivery.lastErrorCode ? t('REGISTRATION.DELIVERY.CANCELLED_REASON') : reason(delivery)}</p>
                                    <p className="text-xs text-black-600">
                                        {delivery.lastAttemptAt ? t('REGISTRATION.DELIVERY.LAST_ATTEMPT', { time: formatDateTime(delivery.lastAttemptAt, i18n.language) }) : t('REGISTRATION.DELIVERY.NO_ATTEMPT')}
                                        {' · '}
                                        {t('REGISTRATION.DELIVERY.ATTEMPTS', { count: delivery.attempts })}
                                    </p>
                                    {message?.id === delivery.id && (
                                        <p role="status" className={message.failed ? 'text-xs font-medium text-[#A83434]' : 'text-xs text-black-800'}>
                                            {message.text}
                                        </p>
                                    )}
                                </div>
                                {canRetry && (
                                    <Button
                                        type="button"
                                        variant="v2Button"
                                        size="sm"
                                        className="shrink-0 self-start"
                                        isLoading={retrying === delivery.id}
                                        disabled={retrying !== null}
                                        aria-label={t('REGISTRATION.DELIVERY.RETRY_NAMED', { id: delivery.responseId })}
                                        onClick={() => retryOne(delivery)}
                                    >
                                        {t('REGISTRATION.DELIVERY.RETRY')}
                                    </Button>
                                )}
                            </li>
                        ))}
                    </ul>
                    {failedTotal > failed.length && (
                        <div>
                            <Button type="button" variant="v2Button" size="sm" onClick={() => setLimit((current) => current + PAGE)}>
                                {t('REGISTRATION.DELIVERY.SHOW_MORE')}
                            </Button>
                        </div>
                    )}
                </div>
            )}
        </section>
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
