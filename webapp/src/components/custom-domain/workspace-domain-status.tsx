'use client';
import { useEffect } from 'react';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { simpleDataTableStyles } from '@Components/datatable/datatable-styles';
import CopyIcon from '@Components/icons/copy';
import OpenLinkIcon from '@Components/icons/open-link';
import { RefreshCcw } from 'lucide-react';
import DataTable from 'react-data-table-component';
import { Trans, useTranslation } from 'react-i18next';

import environments from '@app/configs/environments';
import { CustomDomainCheck, CustomDomainDnsRecord, WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { Button } from '@app/shadcn/components/ui/button';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import ToolTip from '@app/shadcn/components/ui/tooltip';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useRecheckWorkspaceDomainMutation, useVerifyWorkspaceDomainQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import DeleteDomainDropdown from './delete-domain-dropdown';

/**
 * Two providers share this page. The custom-domain service answers with the
 * domain resource (`provider: 'custom-domain'`: status, the TXT + CNAME
 * records to publish, four checks with messages); the legacy certificate
 * server answers with an A/TXT record check. Both end in the "verified" view.
 */
const WorkspaceDomainStatus = () => {
    const { t } = useTranslation();
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const pathname = usePathname();

    const { data, isLoading, isFetching, refetch } = useVerifyWorkspaceDomainQuery(workspace.id, { skip: !workspace.id, refetchOnMountOrArgChange: false, refetchOnReconnect: true, refetchOnFocus: false });

    const isService = data?.provider === 'custom-domain';
    const verified = isService ? data?.status === 'ready' : Boolean(data?.domain_verified && data?.txt_verified);

    useEffect(() => {
        if (verified) {
            router.push(pathname || '');
        }
    }, [verified]);

    if (isLoading) {
        return (
            <div>
                <Skeleton className="mt-4 h-5 w-80" />
                <Skeleton className="mt-4 h-5 w-full" />

                <Skeleton className="mt-2 h-20 w-full" />

                <Skeleton className="mt-4 h-5 w-80" />
            </div>
        );
    }

    if (verified) {
        return <DomainVerifiedStatus workspace={workspace} txtRecord={isService ? data?.dns_records?.find((r: CustomDomainDnsRecord) => r.purpose === 'ownership') : undefined} />;
    }

    if (isService && (data?.status === 'removed' || data?.status === 'unregistered')) {
        return <ServiceDomainGone workspace={workspace} status={data.status} />;
    }

    if (isService) {
        return <ServiceDomainPending workspace={workspace} status={data?.status} records={data?.dns_records ?? []} checks={data?.checks ?? []} isFetching={isFetching} refetch={refetch} />;
    }

    const legacyRecords = [
        {
            name: workspace.customDomain,
            type: 'A',
            value: data?.records?.[0]?.expected,
            resolved: data?.records?.[0]?.resolved ?? [],
            status: data?.domain_verified ? <StatusPill tone="ok">{t('CUSTOM_DOMAIN_UI.SUCCESS')}</StatusPill> : <StatusPill tone="pending">{t('CUSTOM_DOMAIN_UI.PENDING')}</StatusPill>
        },
        {
            name: workspace.customDomain,
            type: 'TXT',
            value: data?.records?.[1]?.expected,
            resolved: data?.records?.[1]?.resolved ?? [],
            status: data?.txt_verified ? <StatusPill tone="ok">{t('CUSTOM_DOMAIN_UI.SUCCESS')}</StatusPill> : <StatusPill tone="pending">{t('CUSTOM_DOMAIN_UI.PENDING')}</StatusPill>
        }
    ];
    return <DomainVerificationPending workspace={workspace} dnsData={legacyRecords} isFetching={isFetching} refetch={refetch} />;
};

const StatusPill = ({ tone, children }: { tone: 'ok' | 'pending' | 'bad'; children: React.ReactNode }) => (
    <div className={cn('rounded px-2 py-1 text-xs', tone === 'ok' && 'bg-[#E7F4EE] text-success-700', tone === 'pending' && 'bg-brand-accent-100 text-brand-olive', tone === 'bad' && 'bg-red-100 text-red-700')}>{children}</div>
);

const STATUS_LABEL: Record<string, { label: string; tone: 'ok' | 'pending' | 'bad' }> = {
    pending_dns: { label: 'CUSTOM_DOMAIN_UI.STATUS_pending_dns', tone: 'pending' },
    provisioning: { label: 'CUSTOM_DOMAIN_UI.STATUS_provisioning', tone: 'pending' },
    ready: { label: 'CUSTOM_DOMAIN_UI.STATUS_ready', tone: 'ok' },
    attention_required: { label: 'CUSTOM_DOMAIN_UI.STATUS_attention_required', tone: 'bad' },
    suspended: { label: 'CUSTOM_DOMAIN_UI.STATUS_suspended', tone: 'bad' },
    deleting: { label: 'CUSTOM_DOMAIN_UI.STATUS_deleting', tone: 'bad' }
};

const CHECK_LABEL: Record<string, string> = {
    ownership: 'CUSTOM_DOMAIN_UI.CHECK_ownership',
    routing: 'CUSTOM_DOMAIN_UI.CHECK_routing',
    certificate: 'CUSTOM_DOMAIN_UI.CHECK_certificate',
    origin: 'CUSTOM_DOMAIN_UI.CHECK_origin'
};

const CopyCell = ({ value, toast }: { value: string; toast: (v: { description: string }) => void }) => {
    const { t } = useTranslation();
    return (
        <div
            className="flex cursor-pointer gap-2"
            onClick={() => {
                navigator.clipboard.writeText(value);
                toast({ description: t('CUSTOM_DOMAIN_UI.COPIED') });
            }}
        >
            <ToolTip label={value} triggerClassName="max-w-[220px]! truncate">
                <span>{value}</span>
            </ToolTip>
            <div>
                <CopyIcon className="min-w-fit" width={12} height={12} />
            </div>
        </div>
    );
};

const DomainVerifiedStatus = ({ workspace, txtRecord }: { workspace: WorkspaceDto; txtRecord?: CustomDomainDnsRecord }) => {
    const { t } = useTranslation();
    const { toast } = useToast();
    return (
        <div className="flex flex-col">
            <span className="mt-4 text-xs text-black-700">{t('CUSTOM_DOMAIN_UI.VERIFIED_INTRO')}</span>
            <div className="mt-4 flex flex-wrap gap-2">
                <div className="flex flex-1 items-center rounded-lg bg-black-100 px-3 py-2 text-xs text-black-800">
                    {environments.HTTP_SCHEME}
                    {workspace.customDomain}
                </div>
                <Link href={`${environments.HTTP_SCHEME}${workspace.customDomain}`} target={'_blank'} referrerPolicy="no-referrer">
                    <Button className="p-2!" variant={'v2Button'} icon={<OpenLinkIcon />} />
                </Link>
                <Button
                    variant={'v2Button'}
                    onClick={() => {
                        navigator.clipboard.writeText(`${environments.HTTP_SCHEME}${workspace.customDomain}`);
                        toast({ description: t('CUSTOM_DOMAIN_UI.COPIED') });
                    }}
                >
                    {' '}
                    {t('CUSTOM_DOMAIN_UI.COPY')}
                </Button>
                <DeleteDomainDropdown />
            </div>
            <div className="mt-2 flex items-center gap-2">
                {t('CUSTOM_DOMAIN_UI.STATUS')}{' '}
                <div className="flex items-center gap-1 text-green-600">
                    <div className="h-3 w-3 rounded-full bg-green-600 text-sm font-medium" />
                    {t('CUSTOM_DOMAIN_UI.PRODUCTION')}
                </div>
            </div>
            {txtRecord && (
                <div className="mt-3 text-xs text-black-700">
                    {t('CUSTOM_DOMAIN_UI.KEEP_RECORD')}{' '}
                    <span className="font-mono">
                        {txtRecord.type} {txtRecord.name}
                    </span>
                    {t('CUSTOM_DOMAIN_UI.KEEP_RECORD_AFTER')}
                </div>
            )}
        </div>
    );
};

/** The service does not hold this hostname. `removed`: it was deleted on the
 *  service side, so the only way forward is to remove it here and set it again
 *  (which registers it and shows the DNS records). `unregistered`: it was set
 *  up on the previous system and is still served there while the migration
 *  runs. The owner can wait for the DNS notice, or move it now: removing it
 *  releases it on both systems, and adding it again registers it and shows the
 *  DNS records. */
const ServiceDomainGone = ({ workspace, status }: { workspace: WorkspaceDto; status: 'removed' | 'unregistered' }) => {
    const { t } = useTranslation();
    const { toast } = useToast();
    return (
        <div className="mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">{t('CUSTOM_DOMAIN_UI.YOUR_DOMAIN')} </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                {status === 'removed' ? <StatusPill tone="bad">{t('CUSTOM_DOMAIN_UI.REMOVED')}</StatusPill> : <StatusPill tone="pending">{t('CUSTOM_DOMAIN_UI.MIGRATING')}</StatusPill>}
                <DeleteDomainDropdown />
            </div>
            {status === 'removed' ? (
                <div className="mt-4 text-xs text-black-700">{t('CUSTOM_DOMAIN_UI.REMOVED_BODY')}</div>
            ) : (
                <div className="mt-4 flex flex-col gap-2 text-xs text-black-700">
                    <span>{t('CUSTOM_DOMAIN_UI.MIGRATING_1')}</span>
                    <span>
                        <Trans i18nKey="CUSTOM_DOMAIN_UI.MIGRATING_2" values={{ domain: workspace.customDomain }} components={{ 1: <span className="font-semibold" /> }} />
                    </span>
                    <div className="flex flex-wrap gap-2">
                        <Link href={`${environments.HTTP_SCHEME}${workspace.customDomain}`} target={'_blank'} referrerPolicy="no-referrer">
                            <Button className="p-2!" variant={'v2Button'} icon={<OpenLinkIcon />} />
                        </Link>
                        <Button
                            variant={'v2Button'}
                            onClick={() => {
                                navigator.clipboard.writeText(`${environments.HTTP_SCHEME}${workspace.customDomain}`);
                                toast({ description: t('CUSTOM_DOMAIN_UI.COPIED') });
                            }}
                        >
                            {t('CUSTOM_DOMAIN_UI.COPY')}
                        </Button>
                    </div>
                </div>
            )}
        </div>
    );
};

const ServiceDomainPending = ({ workspace, status, records, checks, isFetching, refetch }: { workspace: WorkspaceDto; status?: string; records: CustomDomainDnsRecord[]; checks: CustomDomainCheck[]; isFetching: boolean; refetch: () => void }) => {
    const { t } = useTranslation();
    const { toast } = useToast();
    const [recheck, { isLoading: isRechecking }] = useRecheckWorkspaceDomainMutation();
    const statusInfo = STATUS_LABEL[status || ''] || { label: status ? '' : 'CUSTOM_DOMAIN_UI.STATUS_unknown', tone: 'pending' as const };
    const statusText = statusInfo.label ? t(statusInfo.label) : status;

    const checkAgain = async () => {
        const response: any = await recheck(workspace.id);
        if (response.error) {
            const data = response.error.data;
            const message = data?.retry_after ? t('CUSTOM_DOMAIN_UI.WAIT_SECONDS', { seconds: data.retry_after }) : data?.message || data || t('CUSTOM_DOMAIN_UI.CHECK_FAILED');
            toast({ description: String(message), variant: 'destructive' });
            return;
        }
        toast({ description: t('CUSTOM_DOMAIN_UI.CHECKING') });
        refetch();
    };

    const columns: any = [
        { name: t('CUSTOM_DOMAIN_UI.COL_TYPE'), selector: (record: CustomDomainDnsRecord) => record.type, width: '90px' },
        { name: t('CUSTOM_DOMAIN_UI.COL_NAME'), grow: 2, selector: (record: CustomDomainDnsRecord) => <CopyCell value={record.name} toast={toast} /> },
        { name: t('CUSTOM_DOMAIN_UI.COL_VALUE'), grow: 2, selector: (record: CustomDomainDnsRecord) => <CopyCell value={record.value} toast={toast} /> },
        {
            name: t('CUSTOM_DOMAIN_UI.COL_STATUS'),
            selector: (record: CustomDomainDnsRecord) => {
                const check = checks.find((c) => (record.purpose === 'ownership' ? c.type === 'ownership' : c.type === 'routing'));
                if (check?.status === 'passing') return <StatusPill tone="ok">{t('CUSTOM_DOMAIN_UI.FOUND')}</StatusPill>;
                if (check?.status === 'failing') return <StatusPill tone="bad">{t('CUSTOM_DOMAIN_UI.NOT_FOUND')}</StatusPill>;
                return <StatusPill tone="pending">{t('CUSTOM_DOMAIN_UI.PENDING')}</StatusPill>;
            }
        }
    ];

    return (
        <div className="mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">{t('CUSTOM_DOMAIN_UI.YOUR_DOMAIN')} </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <StatusPill tone={statusInfo.tone}>{statusText}</StatusPill>
                <DeleteDomainDropdown />
            </div>
            <div className="mb-2 mt-4 text-xs text-black-700">
                {t('CUSTOM_DOMAIN_UI.ADD_RECORDS')} <br />
                {t('CUSTOM_DOMAIN_UI.NO_PROXY')}
            </div>
            <DataTable className="" columns={columns} data={records} customStyles={simpleDataTableStyles} />
            {records.some((r) => r.help) && (
                <ul className="mt-2 list-disc pl-5 text-xs text-black-600">
                    {records.map((r) => (
                        <li key={r.name + r.type}>
                            <span className="font-medium">{r.type}:</span> {r.help}
                        </li>
                    ))}
                </ul>
            )}
            <div className="mt-4 flex flex-col gap-1">
                {checks.map((check) => (
                    <div key={check.type} className="flex flex-wrap items-center gap-2 text-xs">
                        <span className={cn('h-2 w-2 rounded-full', check.status === 'passing' && 'bg-success', check.status === 'failing' && 'bg-red-500', check.status === 'pending' && 'bg-brand-accent')} />
                        <span className="font-medium text-black-800">{CHECK_LABEL[check.type] ? t(CHECK_LABEL[check.type]) : check.type}</span>
                        {check.message && <span className="text-black-600">— {check.message}</span>}
                    </div>
                ))}
            </div>
            <div className="mt-4 flex items-center gap-3">
                <Button variant={'v2Button'} size="sm" isLoading={isRechecking} onClick={checkAgain}>
                    {t('CUSTOM_DOMAIN_UI.CHECK_AGAIN')}
                </Button>
                <span className="text-xs text-black-600">{t('CUSTOM_DOMAIN_UI.AUTO_CHECK')}</span>
                <RefreshCcw
                    width={20}
                    height={20}
                    className={cn(isFetching && 'rotate-180 transform animate-spin', 'cursor-pointer text-blue-500')}
                    onClick={() => {
                        if (!isFetching) {
                            refetch();
                        }
                    }}
                />
            </div>
        </div>
    );
};

const DomainVerificationPending = ({ workspace, dnsData, isFetching, refetch }: { workspace: WorkspaceDto; dnsData: Array<any>; isFetching: boolean; refetch: () => void }) => {
    const { t } = useTranslation();
    const { toast } = useToast();

    const columns: any = [
        {
            name: t('CUSTOM_DOMAIN_UI.COL_NAME'),
            grow: 2,
            selector: (record: any) => <CopyCell value={record.name} toast={toast} />
        },
        {
            name: t('CUSTOM_DOMAIN_UI.COL_TYPE'),
            selector: (record: any) => record.type
        },
        {
            name: t('CUSTOM_DOMAIN_UI.COL_VALUE'),
            selector: (record: any) => <CopyCell value={record.value} toast={toast} />,
            grow: 2
        },
        {
            name: t('CUSTOM_DOMAIN_UI.COL_RESOLVED'),
            grow: 2,
            selector: (record: any) =>
                record.resolved?.length > 0 ? (
                    <div className="flex flex-wrap gap-1">
                        {record.resolved.map((ip: string, index: number) => (
                            <span
                                key={index}
                                className="cursor-pointer rounded bg-gray-100 px-1.5 py-0.5 text-xs text-gray-700"
                                onClick={() => {
                                    navigator.clipboard.writeText(ip);
                                    toast({ description: t('CUSTOM_DOMAIN_UI.COPIED') });
                                }}
                            >
                                {ip}
                            </span>
                        ))}
                    </div>
                ) : (
                    <span className="text-xs text-black-600">—</span>
                )
        },
        {
            name: t('CUSTOM_DOMAIN_UI.COL_STATUS'),
            selector: (record: any) => record.status
        }
    ];
    return (
        <div className="mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">{t('CUSTOM_DOMAIN_UI.YOUR_DOMAIN')} </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <DeleteDomainDropdown />
            </div>
            <div className="mb-2 mt-4 text-xs text-black-700">
                {t('CUSTOM_DOMAIN_UI.LEGACY_ADD')} <br />
                {t('CUSTOM_DOMAIN_UI.LEGACY_NO_PROXY')}
            </div>
            <DataTable className="" columns={columns} data={dnsData} customStyles={simpleDataTableStyles} />
            <div className="mt-4 flex items-center gap-2">
                {t('CUSTOM_DOMAIN_UI.LEGACY_PRESS')}{' '}
                <span>
                    <RefreshCcw
                        width={24}
                        height={24}
                        className={cn(isFetching && 'rotate-180 transform animate-spin', 'cursor-pointer text-blue-500')}
                        onClick={() => {
                            if (!isFetching) {
                                refetch();
                            }
                        }}
                    />
                </span>
            </div>
        </div>
    );
};

export default WorkspaceDomainStatus;
