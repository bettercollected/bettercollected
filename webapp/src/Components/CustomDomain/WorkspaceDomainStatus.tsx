import { simpleDataTableStyles } from '@app/components/datatable/form/datatable-styles';
import environments from '@app/configs/environments';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { Button } from '@app/shadcn/components/ui/button';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { useAppSelector } from '@app/store/hooks';
import { useVerifyWorkspaceDomainQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import CopyIcon from '@app/views/atoms/Icons/Copy copy';
import OpenLinkIcon from '@app/views/atoms/Icons/OpenLink';
import { RefreshCcw } from 'lucide-react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect } from 'react';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';
import DeleteDomainDropdown from './DeleteDomainDropdown';

const WorkspaceDomainStatus = () => {
    const workspace = useAppSelector(selectWorkspace);
    const router = useRouter();
    const pathname = usePathname();

    const { data, isLoading, isFetching, refetch } = useVerifyWorkspaceDomainQuery(workspace.id, { skip: !workspace.id, refetchOnMountOrArgChange: false, refetchOnReconnect: true, refetchOnFocus: false });

    useEffect(() => {
        if (data?.domain_verified && data?.txt_verified) {
            console.log(pathname);
            router.push(pathname || '');
        }
    }, [data]);

    const getDNSRecordData = () => {
        const dnsData: any[] = [];
        dnsData.push({
            name: workspace.customDomain,
            type: 'A',
            value: environments.CUSTOM_DOMAIN_IP,
            status: data?.domain_verified ? <div className="rounded-xl bg-green-100 px-2 py-1 text-xs text-green-500">Success</div> : <div className="rounded-xl bg-yellow-100 px-2 py-1 text-xs text-yellow-600">Pending</div>
        });
        dnsData.push({
            name: workspace.customDomain,
            type: 'TXT',
            value: data?.records?.[1].value,
            status: data?.txt_verified ? <div className="rounded-xl bg-green-100 px-2 py-1 text-xs text-green-500">Success</div> : <div className="rounded-xl bg-yellow-100 px-2 py-1  text-xs text-yellow-600">Pending</div>
        });
        return dnsData;
    };

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

    if (data?.domain_verified && data?.txt_verified) {
        return <DomainVerifiedStatus workspace={workspace} />;
    }

    return <DomainVerificationPending workspace={workspace} dnsData={getDNSRecordData()} isFetching={isFetching} refetch={refetch} />;
};

const DomainVerifiedStatus = ({ workspace }: { workspace: WorkspaceDto }) => {
    return (
        <div className=" flex flex-col">
            <span className="text-black-700 mt-4 text-xs">You can use your own domain name to have a custom URL for your published forms. Consider using a subdomain, such as : forms.yourdomain.com</span>
            <div className="mt-4 flex flex-wrap gap-2">
                <div className="bg-black-100 text-black-800 flex flex-1  items-center rounded-lg px-3 py-2 text-xs">
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
                        toast('Copied', { type: 'success' });
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
        </div>
    );
};

const DomainVerificationPending = ({ workspace, dnsData, isFetching, refetch }: { workspace: WorkspaceDto; dnsData: Array<any>; isFetching: boolean; refetch: () => void }) => {
    const columns: any = [
        {
            name: 'Name',
            grow: 2,
            selector: (record: any) => (
                <div
                    className="flex cursor-pointer gap-2"
                    onClick={() => {
                        navigator.clipboard.writeText(record.name);
                        toast('Copied', { type: 'info' });
                    }}
                >
                    <div className="min-w-fit">{record.name}</div>
                    <div>
                        <CopyIcon className="" width={12} height={12} />
                    </div>
                </div>
            )
        },
        {
            name: 'Type',
            selector: (record: any) => record.type
        },
        {
            name: 'Value',
            selector: (record: any) => (
                <div
                    className="flex cursor-pointer gap-2"
                    onClick={() => {
                        navigator.clipboard.writeText(record.value);
                        toast('Copied', { type: 'info' });
                    }}
                >
                    <div className={'max-w-[100px] truncate'}>{record.value}</div>
                    <div>
                        <CopyIcon
                            className="min-w-fit"
                            width={12}
                            height={12}
                            onClick={() => {
                                navigator.clipboard.writeText(record.value);
                                toast('Copied', { type: 'info' });
                            }}
                        />
                    </div>
                </div>
            ),
            grow: 2
        },
        {
            name: 'Status',
            selector: (record: any) => record.status
        }
    ];
    return (
        <div className=" mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">Your domain: </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <DeleteDomainDropdown />
            </div>
            <div className="text-black-700 mb-2 mt-4  text-xs">
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
