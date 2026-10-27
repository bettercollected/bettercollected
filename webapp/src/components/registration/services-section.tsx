'use client';

import React, { useState } from 'react';

import { Plus, ServerCog } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import ServiceDialog from '@app/components/registration/service-dialog';
import { Button } from '@app/shadcn/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@app/shadcn/components/ui/dialog';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppSelector } from '@app/store/hooks';
import { RegistrationService, RegistrationTestResult, useDeleteRegistrationServiceMutation, useGetRegistrationServicesQuery, useTestRegistrationServiceMutation } from '@app/store/workspaces/registration-api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { workspaceDisplayName } from '@app/utils/workspace-display-name';
import { errorCodeOf, errorKey, formatDay, testKey } from '@app/utils/registration';

/**
 * Workspace settings, "Case system": the services submissions can be sent
 * to. Admins add, change, test and delete them. A service's secret is never
 * shown, only whether one is set.
 */
export default function ServicesSection() {
    const { t, i18n } = useTranslation('builder');
    const { toast } = useToast();
    const workspace = useAppSelector(selectWorkspace);
    const workspaceId: string | undefined = workspace?.id;
    const { data, isLoading, isError, refetch } = useGetRegistrationServicesQuery(workspaceId as string, { skip: !workspaceId });
    const [testService] = useTestRegistrationServiceMutation();
    const [deleteService, { isLoading: deleting }] = useDeleteRegistrationServiceMutation();

    const [editing, setEditing] = useState<RegistrationService | null>(null);
    const [dialogOpen, setDialogOpen] = useState(false);
    const [results, setResults] = useState<Record<string, RegistrationTestResult | 'testing' | 'failed'>>({});
    const [toDelete, setToDelete] = useState<RegistrationService | null>(null);
    const [deleteError, setDeleteError] = useState<string | null>(null);

    const openDialog = (service: RegistrationService | null) => {
        setEditing(service);
        setDialogOpen(true);
    };

    const runTest = async (service: RegistrationService) => {
        setResults((current) => ({ ...current, [service.id]: 'testing' }));
        const response: any = await testService({ workspaceId: workspaceId as string, serviceId: service.id });
        setResults((current) => ({ ...current, [service.id]: response.data ?? 'failed' }));
    };

    const confirmDelete = async () => {
        if (!toDelete) return;
        const response: any = await deleteService({ workspaceId: workspaceId as string, serviceId: toDelete.id });
        if (response.error) {
            setDeleteError(t(errorKey(errorCodeOf(response.error))));
            return;
        }
        toast({ description: t('REGISTRATION.SERVICES.DELETED', { name: toDelete.name }) });
        setToDelete(null);
    };

    const authLabel = (service: RegistrationService) => {
        if (service.auth === 'header') return t('REGISTRATION.SERVICES.AUTH_HEADER', { name: service.authName });
        if (service.auth === 'basic') return t('REGISTRATION.SERVICES.AUTH_BASIC', { name: service.authName });
        return t('REGISTRATION.SERVICES.AUTH_NONE');
    };

    const resultText = (result: RegistrationTestResult | 'testing' | 'failed' | undefined) => {
        if (!result) return '';
        if (result === 'testing') return t('REGISTRATION.SERVICES.TESTING');
        if (result === 'failed') return t('REGISTRATION.TEST.unknown');
        return t(testKey(result.ok, result.code), { status: result.httpStatus ?? '' });
    };

    return (
        <div className="flex w-full max-w-[860px] flex-col gap-6 pb-10">
            <div className="flex flex-col gap-3">
                <p className="max-w-[62ch] text-sm leading-relaxed text-black-700">{t('REGISTRATION.SERVICES.INTRO')}</p>
                <p className="max-w-[62ch] rounded-md border border-black-300 bg-black-100 px-3 py-2 text-xs leading-relaxed text-black-700">{t('REGISTRATION.NOTICE')}</p>
            </div>

            <section className="flex flex-col gap-3" aria-labelledby="registration-services-title">
                <div className="flex flex-wrap items-center justify-between gap-3">
                    <h2 id="registration-services-title" className="text-sm font-semibold text-black-900">
                        {t('REGISTRATION.SERVICES.TITLE')}
                    </h2>
                    <Button type="button" variant="v2Button" icon={<Plus className="h-4 w-4" aria-hidden="true" />} onClick={() => openDialog(null)}>
                        {t('REGISTRATION.SERVICES.ADD')}
                    </Button>
                </div>

                {isLoading && <p className="text-sm text-black-600">{t('REGISTRATION.LOADING')}</p>}
                {isError && (
                    <p role="alert" className="text-sm text-[#A83434]">
                        {t('REGISTRATION.SERVICES.LOAD_ERROR')}{' '}
                        <button type="button" className="font-medium underline" onClick={() => refetch()}>
                            {t('REGISTRATION.TRY_AGAIN')}
                        </button>
                    </p>
                )}
                {!isLoading && !isError && data && data.length === 0 && (
                    <div className="flex flex-col items-start gap-1 rounded-lg border border-dashed border-black-300 p-6">
                        <p className="text-sm font-semibold text-black-900">{t('REGISTRATION.SERVICES.EMPTY_TITLE')}</p>
                        <p className="text-sm text-black-700">{t('REGISTRATION.SERVICES.EMPTY_TEXT')}</p>
                    </div>
                )}
                {data && data.length > 0 && (
                    <ul className="flex flex-col gap-3" aria-label={t('REGISTRATION.SERVICES.TITLE')}>
                        {data.map((service) => {
                            const result = results[service.id];
                            return (
                                <li key={service.id} className="flex flex-col gap-3 rounded border border-black-300 bg-white p-4" data-testid={`registration-service-${service.id}`}>
                                    <div className="flex flex-wrap items-start justify-between gap-3">
                                        <div className="flex min-w-0 flex-col gap-1">
                                            <div className="flex items-center gap-2">
                                                <ServerCog className="h-4 w-4 shrink-0 text-black-600" aria-hidden="true" />
                                                <h3 className="text-sm font-semibold break-words text-black-900">{service.name}</h3>
                                            </div>
                                            <dl className="grid gap-x-6 gap-y-0.5 text-xs text-black-700 sm:grid-cols-[max-content_1fr]">
                                                <dt className="font-medium text-black-600">{t('REGISTRATION.SERVICES.ADDRESS')}</dt>
                                                <dd className="break-all">{service.baseUrl}</dd>
                                                <dt className="font-medium text-black-600">{t('REGISTRATION.SERVICES.ORGANISATION')}</dt>
                                                <dd className="break-words">{service.organisationName}</dd>
                                                <dt className="font-medium text-black-600">{t('REGISTRATION.SERVICES.SIGN_IN')}</dt>
                                                <dd className="break-words">{authLabel(service)}</dd>
                                                {service.auth !== 'none' && (
                                                    <>
                                                        <dt className="font-medium text-black-600">{t('REGISTRATION.SERVICES.SECRET')}</dt>
                                                        <dd>{service.hasSecret ? t('REGISTRATION.SERVICES.SECRET_SET', { date: formatDay(service.secretSetAt, i18n.language) }) : t('REGISTRATION.SERVICES.SECRET_NOT_SET')}</dd>
                                                    </>
                                                )}
                                            </dl>
                                        </div>
                                        <div className="flex flex-wrap gap-2">
                                            <Button type="button" variant="v2Button" size="sm" disabled={result === 'testing'} aria-label={t('REGISTRATION.SERVICES.TEST_NAMED', { name: service.name })} onClick={() => runTest(service)}>
                                                {t('REGISTRATION.SERVICES.TEST')}
                                            </Button>
                                            <Button type="button" variant="v2Button" size="sm" aria-label={t('REGISTRATION.SERVICES.EDIT_NAMED', { name: service.name })} onClick={() => openDialog(service)}>
                                                {t('REGISTRATION.SERVICES.EDIT')}
                                            </Button>
                                            <Button
                                                type="button"
                                                variant="dangerGhost"
                                                size="sm"
                                                aria-label={t('REGISTRATION.SERVICES.DELETE_NAMED', { name: service.name })}
                                                onClick={() => {
                                                    setDeleteError(null);
                                                    setToDelete(service);
                                                }}
                                            >
                                                {t('REGISTRATION.SERVICES.DELETE')}
                                            </Button>
                                        </div>
                                    </div>
                                    <p role="status" className={result && result !== 'testing' && (result === 'failed' || !result.ok) ? 'text-sm font-medium text-[#A83434]' : 'text-sm text-black-800'} data-testid={`registration-test-${service.id}`}>
                                        {resultText(result)}
                                    </p>
                                </li>
                            );
                        })}
                    </ul>
                )}
                {data && data.length > 0 && <p className="max-w-[62ch] text-xs leading-relaxed text-black-600">{t('REGISTRATION.SERVICES.TEST_WARNING')}</p>}
            </section>

            <ServiceDialog open={dialogOpen} onOpenChange={setDialogOpen} workspaceId={workspaceId as string} workspaceTitle={workspaceDisplayName(workspace)} service={editing} />

            <Dialog
                open={!!toDelete}
                onOpenChange={(open) => {
                    if (!open) setToDelete(null);
                }}
            >
                <DialogContent className="max-w-md bg-white" title={t('REGISTRATION.SERVICES.DELETE_TITLE', { name: toDelete?.name })}>
                    <DialogHeader>
                        <DialogTitle>{t('REGISTRATION.SERVICES.DELETE_TITLE', { name: toDelete?.name })}</DialogTitle>
                        <DialogDescription>{t('REGISTRATION.SERVICES.DELETE_TEXT')}</DialogDescription>
                    </DialogHeader>
                    {deleteError && (
                        <p role="alert" className="rounded-md border border-[#E5B9B9] bg-[#FBEFEF] px-3 py-2 text-sm text-[#7A2525]">
                            {deleteError}
                        </p>
                    )}
                    <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                        <Button type="button" variant="v2Button" onClick={() => setToDelete(null)}>
                            {t('REGISTRATION.DIALOG.CANCEL')}
                        </Button>
                        <Button type="button" variant="danger" isLoading={deleting} disabled={deleting} onClick={confirmDelete}>
                            {t('REGISTRATION.SERVICES.DELETE')}
                        </Button>
                    </div>
                </DialogContent>
            </Dialog>
        </div>
    );
}
