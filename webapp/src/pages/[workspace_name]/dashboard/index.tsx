import React, { useState } from 'react';

import Image from 'next/image';
import Link from 'next/link';
import { useRouter } from 'next/router';

import { PushPin } from '@mui/icons-material';

import ImportFormsMenu from '@app/components/dashboard/import-forms-menu';
import { Google } from '@app/components/icons/brands/google';
import { useModal } from '@app/components/modal-views/context';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import environments from '@app/configs/environments';
import useUser from '@app/lib/hooks/use-authuser';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function CreatorDashboard({ workspace, hasCustomDomain }: { workspace: any; hasCustomDomain: boolean }) {
    const { openModal } = useModal();
    const router = useRouter();

    const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

    const open = Boolean(anchorEl);

    const workspaceQuery = {
        workspace_id: workspace.id
    };

    const workspaceForms = useGetWorkspaceFormsQuery<any>(workspaceQuery, { pollingInterval: 30000 });

    const breakpoint = useBreakpoint();

    const forms = workspaceForms?.data?.payload?.content;

    const handleImportForms = () => {
        openModal('IMPORT_TYPE_FORMS_VIEW');
        // openModal('IMPORT_GOOGLE_FORMS_VIEW');
    };

    const handleConnectWithGoogle = () => {
        router.push(`${environments.API_ENDPOINT_HOST}/auth/google/connect`);
    };

    const getWorkspaceUrl = () => {
        const protocol = environments.CLIENT_HOST.includes('localhost') ? 'http://' : 'https://';
        const domain = !!workspace.customDomain ? workspace.customDomain : environments.CLIENT_HOST;
        const w_name = !!workspace.customDomain ? '' : workspace.workspaceName;
        return `${protocol}${domain}/${w_name}`;
    };

    const Header = () => (
        <div className="flex flex-col w-full sm:flex-row justify-between items-start sm:items-center mb-10 md:py-4 border-b-[1px] border-b-gray-200">
            <div className="flex flex-col">
                <h1 className="font-extrabold text-3xl mb-3">Welcome to {workspace.title}!</h1>
            </div>
            <div className="flex items-center flex-col md:flex-row w-full md:w-auto md:space-x-5 space-y-5 md:space-y-0 mb-3 md:mb-0">
                <a href={getWorkspaceUrl()} className="rounded-xl w-full text-center text-sm  bg-blue-500 text-white px-5 py-3">
                    Go to Workspace
                </a>
                <ImportFormsMenu />
            </div>
        </div>
    );

    // UI for forms
    const MyRecentForms = () => {
        return (
            <div>
                <h1 className="font-semibold text-2xl mb-4">My Recent Forms</h1>
                <div className="grid grid-cols-1 pb-4 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto) => {
                            const slug = form.settings.customUrl;
                            let shareUrl = '';
                            if (window && typeof window !== 'undefined') {
                                shareUrl = hasCustomDomain ? `${window.location.origin}/forms/${slug}` : `https://`;
                            }
                            return (
                                <Link key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                    <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                                        <div className="flex flex-col w-full justify-between h-full">
                                            <div className="w-full ">
                                                <div className="flex mb-4 w-full items-center space-x-4">
                                                    <div>
                                                        {form?.settings.provider === 'typeform' ? (
                                                            <div className="rounded-full border h-[24px] w-[28px] border-white relative">
                                                                <Image src="/tf.png" className="rounded-full" layout="fill" alt={'T'} />
                                                            </div>
                                                        ) : (
                                                            <div className="rounded-full bg-white p-1">
                                                                <Google />
                                                            </div>
                                                        )}
                                                    </div>
                                                    <p className="text-xl text-grey  p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.title, 15) : toEndDottedStr(form.title, 30)}</p>
                                                </div>
                                                {form?.description && (
                                                    <p className="text-base text-softBlue m-0 p-0 w-full">
                                                        {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                                    </p>
                                                )}
                                                {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
                                            </div>

                                            <div className="flex pt-3 justify-between">
                                                {<div className="rounded space-x-2 text-xs px-2 flex py-1 items-center text-gray-500 bg-gray-100">{form?.settings.private ? 'Hidden' : 'Public'}</div>}
                                                {form.settings.pinned && <PushPin className="rotate-45" />}
                                            </div>
                                        </div>
                                    </div>
                                </Link>
                            );
                        })}
                </div>
            </div>
        );
    };

    return (
        <Layout>
            <Header />
            <MyRecentForms />
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    return await getAuthUserPropsWithWorkspace(_context);
}
