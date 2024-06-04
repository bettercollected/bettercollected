import { simpleDataTableStyles } from '@app/components/datatable/form/datatable-styles';
import { Refresh } from '@app/components/icons/refresh';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import DashboardLayout from '@app/components/sidebar/dashboard-layout';
import { ProLogo } from '@app/components/ui/logo';
import environments from '@app/configs/environments';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ButtonVariant } from '@app/models/enums/button';
import { Button } from '@app/shadcn/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation, useVerifyWorkspaceDomainQuery } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import CopyIcon from '@app/views/atoms/Icons/Copy copy';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import EllipsisOption from '@app/views/atoms/Icons/EllipsisOption';
import OpenLinkIcon from '@app/views/atoms/Icons/OpenLink';
import { RefreshCcw } from 'lucide-react';
import { useTranslation } from 'next-i18next';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import DataTable from 'react-data-table-component';
import { toast } from 'react-toastify';

export default function CustomDomainSettings() {
    return (
        <>
            <DashboardLayout boxClassName="px-5 pt-10 lg:px-10">
                <div className="max-w-[664px] rounded-2xl bg-white p-8">
                    <CustomDomainCard />
                </div>
            </DashboardLayout>
        </>
    );
}

export const CustomDomainCard = () => {
    const workspace = useAppSelector(selectWorkspace);
    return (
        <div className="flex max-w-[664px] flex-col">
            <div className="text-black-900  flex gap-2 text-sm font-semibold ">
                {' '}
                Custom Domain <ProLogo />
            </div>
            <hr className="text-black-200 mt-2" />
            {!workspace?.customDomain && <AddWorkspaceDomainForm />}
            {workspace?.customDomain && <WorkspaceDomainStatus />}
        </div>
    );
};

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

    const columns: any = [
        {
            name: 'Name',
            grow: 2,
            selector: (record: any) => (
                <div className="flex gap-2">
                    {record.name}
                    <CopyIcon
                        className="cursor-pointer"
                        width={12}
                        height={12}
                        onClick={() => {
                            navigator.clipboard.writeText(record.name);
                            toast('Copied', { type: 'info' });
                        }}
                    />
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
                <div className="flex gap-2">
                    <div className={'max-w-[100px] truncate'}>{record.value}</div>
                    <CopyIcon
                        className="cursor-pointer"
                        width={12}
                        height={12}
                        onClick={() => {
                            navigator.clipboard.writeText(record.value);
                            toast('Copied', { type: 'info' });
                        }}
                    />
                </div>
            ),
            grow: 2
        },
        {
            name: 'Status',
            selector: (record: any) => record.status
        }
    ];

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
    }

    return (
        <div className=" mt-4 flex flex-col text-sm">
            <div className="flex items-center gap-2">
                <span className="text-black-600">Your domain: </span>
                <span className="font-semibold text-blue-500">{workspace.customDomain}</span>
                <DeleteDomainDropdown />
            </div>
            <div className="text-black-700 mb-2 mt-4  text-xs">Visit the admin console of your DNS Provider (eg. Cloudflare) and add the following DNS entries.</div>
            <DataTable className="" columns={columns} data={getDNSRecordData()} customStyles={simpleDataTableStyles} />
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

const DeleteDomainDropdown = () => {
    const { openModal } = useModal();

    return (
        <div>
            <DropdownMenu>
                <DropdownMenuTrigger className="outline-none">
                    <Button className="!p-1 outline-none" variant={'v2GhostButton'} icon={<EllipsisOption width={24} height={24} className="text-black-700" />}></Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="bg-white">
                    <DropdownMenuItem
                        className="hover:bg-black-200 flex cursor-pointer items-center gap-2 outline-none"
                        onClick={() => {
                            openModal('DELETE_CUSTOM_DOMAIN');
                        }}
                    >
                        <DeleteIcon />
                        Delete
                    </DropdownMenuItem>
                </DropdownMenuContent>
            </DropdownMenu>
        </div>
    );
};

const AddWorkspaceDomainForm = () => {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useFullScreenModal();

    const [warned, setWarned] = useState(false);

    const [domain, setDomain] = useState('');
    const dispatch = useAppDispatch();
    const { t } = useTranslation();

    const [message, setMessage] = useState({
        error: false,
        message: ''
    });

    const addDomain = async () => {
        if (!workspace.isPro) {
            openModal('UPGRADE_TO_PRO');
            return;
        }
        if (domain.match(/^[a-zA-Z0-9-]+\.[a-zA-Z]{2,63}$/) && !warned) {
            setMessage({ error: false, message: 'This looks like a root domain. This might break your existing site. We recommend using subdomain that is not used elsewhere.' });
            setWarned(true);
            return;
        }
        if (!domain.match(/^(?!:\/\/)([a-zA-Z0-9-_]+\.)+[a-zA-Z]{2,63}$/)) {
            setMessage({ error: true, message: 'Invalid Domain' });
        } else {
            const formData = new FormData();
            formData.append('custom_domain', domain);
            const body = {
                workspace_id: workspace.id,
                body: formData
            };
            const response: any = await patchExistingWorkspace(body);
            if (response.data) {
                dispatch(setWorkspace(response.data));
            } else if (response.error) {
                toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
            }
        }
    };
    return (
        <div className="mt-4 flex flex-col  gap-2">
            <span className="text-black-700 text-xs">You can use your own domain name to have a custom URL for your published forms. Consider using a subdomain, such as : forms.yourdomain.com</span>
            <div className="text-black-800 mt-4 text-xs font-medium">Enter a domain you own</div>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    addDomain();
                }}
                className="flex items-center gap-4"
            >
                <AppInput
                    className={cn('max-w-[400px]', message.message && (message.error ? 'border-red-500' : ''))}
                    value={domain}
                    onChange={(event) => {
                        setDomain(event.target.value);
                        setWarned(false);
                        if (message.message) {
                            setMessage({ error: false, message: '' });
                        }
                    }}
                    placeholder="eg. forms.yoursite.com"
                />
                <Button variant={'v2Button'} type="submit" disabled={warned} isLoading={isLoading}>
                    {' '}
                    Add Domain
                </Button>
            </form>
            <div className="max-w-[400px]">
                {message.message && <div className={cn(message.error ? 'text-red-500' : 'text-[#FFA716]', 'whitespace-pre-wrap text-wrap text-xs	')}>{message.message}</div>}
                {warned && (
                    <Button variant={ButtonVariant.Ghost} isLoading={isLoading} className="mt-2 cursor-pointer text-xs text-blue-500" onClick={addDomain}>
                        Add Anyway
                    </Button>
                )}
            </div>
        </div>
    );
};

export { getServerSidePropsForWorkspaceAdmin as getServerSideProps } from '@app/lib/serverSideProps';
