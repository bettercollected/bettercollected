'use client';
import { useEffect } from 'react';

import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';

import { simpleDataTableStyles } from '@Components/datatable/datatable-styles';
import CopyIcon from '@Components/icons/copy';
import OpenLinkIcon from '@Components/icons/open-link';
import { RefreshCcw } from 'lucide-react';
import DataTable from 'react-data-table-component';

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

    if (isService) {
        return <ServiceDomainPending workspace={workspace} status={data?.status} records={data?.dns_records ?? []} checks={data?.checks ?? []} isFetching={isFetching} refetch={refetch} />;
    }

    const legacyRecords = [
        {
            name: workspace.customDomain,
            type: 'A',
            value: data?.records?.[0]?.expected,
            resolved: data?.records?.[0]?.resolved ?? [],
            status: data?.domain_verified ? <StatusPill tone="ok">Success</StatusPill> : <StatusPill tone="pending">Pending</StatusPill>
        },
        {
            name: workspace.customDomain,
            type: 'TXT',
            value: data?.records?.[1]?.expected,
            resolved: data?.records?.[1]?.resolved ?? [],
            status: data?.txt_verified ? <StatusPill tone="ok">Success</StatusPill> : <StatusPill tone="pending">Pending</StatusPill>
        }
    ];
    return <DomainVerificationPending workspace={workspace} dnsData={legacyRecords} isFetching={isFetching} refetch={refetch} />;
};

const StatusPill = ({ tone, children }: { tone: 'ok' | 'pending' | 'bad'; children: React.ReactNode }) => (
    <div className={cn('rounded-xl px-2 py-1 text-xs', tone === 'ok' && 'bg-green-100 text-green-600', tone === 'pending' && 'bg-yellow-100 text-yellow-600', tone === 'bad' && 'bg-red-100 text-red-600')}>{children}</div>
);

const STATUS_LABEL: Record<string, { label: string; tone: 'ok' | 'pending' | 'bad' }> = {
    pending_dns: { label: 'Waiting for DNS records', tone: 'pending' },
    provisioning: { label: 'DNS verified, issuing certificate', tone: 'pending' },
    ready: { label: 'Production', tone: 'ok' },
    attention_required: { label: 'Needs attention', tone: 'bad' },
    suspended: { label: 'Suspended', tone: 'bad' },
    deleting: { label: 'Removed', tone: 'bad' }
};

const CHECK_LABEL: Record<string, string> = {
    ownership: 'Ownership (TXT record)',
    routing: 'Routing (CNAME record)',
    certificate: 'HTTPS certificate',
    origin: 'Serving your workspace'
};

const CopyCell = ({ value, toast }: { value: string; toast: (v: { description: string }) => void }) => (
    <div
        className="flex cursor-pointer gap-2"
        onClick={() => {
            navigator.clipboard.writeText(value);
            toast({ description: 'Copied' });
        }}
    >
        <ToolTip label={value} triggerClassName="!max-w-[220px] truncate">
            <span>{value}</span>
        </ToolTip>
        <div>
            <CopyIcon className="min-w-fit" width={12} height={12} />
        </div>
    </div>
);

const DomainVerifiedStatus = ({ workspace, txtRecord }: { workspace: WorkspaceDto; txtRecord?: CustomDomainDnsRecord }) => {
    const { toast } = useToast();
    return (
        <div className="flex flex-col">
            <span className="mt-4 text-xs text-black-700">You can use your own domain name to have a custom URL for your published forms. Consider using a subdomain, such as : forms.yourdomain.com</span>
            <div className="mt-4 flex flex-wrap gap-2">
                <div className="flex flex-1 items-center rounded-lg bg-black-100 px-3 py-2 text-xs text-black-800">
                    {environments.HTTP_SCHEME}
                    {workspace.customDomain}
                </div>
                <Link href={`${environments.HTTP_SCHEME}${workspace.customDomain}`} target={'_blank'} referrerPolicy="no-referrer">
                    <Button className="!p-2" variant={'v2Button'} icon={<OpenLinkIcon />} />
                </Link>
                <Button
                    variant={'v2Button'}
                    onClick={() => {
                        navigator.clipboard.writeText(`${environments.HTTP_SCHEME}${workspace.customDomain}`);
                        toast({ description: 'Copied' });
                    }}
                >
                    {' '}
                    Copy
                </Button>
                <DeleteDomainDropdown />
            </div>
            <div className="mt-2 flex items-center gap-2">
                Status:{' '}
                <div className="flex items-center gap-1 text-green-600">
                    <div className="h-3 w-3 rounded-full bg-green-600 text-sm font-medium" />
                    Production
                </div>
            </div>
            {txtRecord && (
                <div className="mt-3 text-xs text-black-700">
                    Keep the ownership record in place:{' '}
                    <span className="font-mono">
                        {txtRecord.type} {txtRecord.name}
                    </span>
                    . If it is removed, the domain stops serving after 24 hours.
                </div>
            )}
        </div>
    );
};

const ServiceDomainPending = ({ workspace, status, records, checks, isFetching, refetch }: { workspace: WorkspaceDto; status?: string; records: CustomDomainDnsRecord[]; checks: CustomDomainCheck[]; isFetching: boolean; refetch: () => void }) => {
    const { toast } = useToast();
    const [recheck, { isLoading: isRechecking }] = useRecheckWorkspaceDomainMutation();
    const statusInfo = STATUS_LABEL[status || ''] || { label: status || 'Unknown', tone: 'pending' as const };

    const checkAgain = async () => {
        const response: any = await recheck(workspace.id);
        if (response.error) {
            const data = response.error.data;
            const message = data?.retry_after ? `Please wait ${data.retry_after} seconds before checking again.` : data?.message || data || 'Could not check the domain right now.';
            toast({ description: String(message), variant: 'destructive' });
            return;
        }
        toast({ description: 'Checking your DNS records. Results appear here within a minute.' });
        refetch();
    };

    const columns: any = [
        { name: 'Type', selector: (record: CustomDomainDnsRecord) => record.type, width: '90px' },
        { name: 'Name', grow: 2, selector: (record: CustomDomainDnsRecord) => <CopyCell value={record.name} toast={toast} /> },
        { name: 'Value', grow: 2, selector: (record: CustomDomainDnsRecord) => <CopyCell value={record.value} toast={toast} /> },
        {
            name: 'Status',
            selector: (record: CustomDomainDnsRecord) => {
                const check = checks.find((c) => (record.purpose === 'ownership' ? c.type === 'ownership' : c.type === 'routing'));
                if (check?.status === 'passing') return <StatusPill tone="ok">Found</StatusPill>;
                if (check?.status === 'failing') return <StatusPill tone="bad">Not found</StatusPill>;
                return <StatusPill tone="pending">Pending</StatusPill>;
            }
        }
    ];

    return (
        <div className="mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">Your domain: </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <StatusPill tone={statusInfo.tone}>{statusInfo.label}</StatusPill>
                <DeleteDomainDropdown />
            </div>
            <div className="mb-2 mt-4 text-xs text-black-700">
                Visit the admin console of your DNS provider (eg. Cloudflare) and add these two records exactly as shown. The TXT record proves you own the name; the CNAME sends traffic to us. <br />
                Note: turn off proxying (the orange cloud on Cloudflare) for the CNAME record.
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
                        <span className={cn('h-2 w-2 rounded-full', check.status === 'passing' && 'bg-green-600', check.status === 'failing' && 'bg-red-500', check.status === 'pending' && 'bg-yellow-500')} />
                        <span className="font-medium text-black-800">{CHECK_LABEL[check.type] || check.type}</span>
                        {check.message && <span className="text-black-600">— {check.message}</span>}
                    </div>
                ))}
            </div>
            <div className="mt-4 flex items-center gap-3">
                <Button variant={'v2Button'} size="sm" isLoading={isRechecking} onClick={checkAgain}>
                    Check again
                </Button>
                <span className="text-xs text-black-600">Records are checked automatically; DNS changes can take up to an hour to be seen.</span>
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
    const { toast } = useToast();

    const columns: any = [
        {
            name: 'Name',
            grow: 2,
            selector: (record: any) => <CopyCell value={record.name} toast={toast} />
        },
        {
            name: 'Type',
            selector: (record: any) => record.type
        },
        {
            name: 'Value',
            selector: (record: any) => <CopyCell value={record.value} toast={toast} />,
            grow: 2
        },
        {
            name: 'Resolved',
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
                                    toast({ description: 'Copied' });
                                }}
                            >
                                {ip}
                            </span>
                        ))}
                    </div>
                ) : (
                    <span className="text-xs text-gray-400">—</span>
                )
        },
        {
            name: 'Status',
            selector: (record: any) => record.status
        }
    ];
    return (
        <div className="mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">Your domain: </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <DeleteDomainDropdown />
            </div>
            <div className="mb-2 mt-4 text-xs text-black-700">
                Visit the admin console of your DNS Provider (eg. Cloudflare) and add the following DNS entries. <br />
                Note: Proxied DNS is not supported
            </div>
            <DataTable className="" columns={columns} data={dnsData} customStyles={simpleDataTableStyles} />
            <div className="mt-4 flex items-center gap-2">
                Once you are done press here to check the status.{' '}
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
