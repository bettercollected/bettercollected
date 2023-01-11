import Link from 'next/link';
import { useRouter } from 'next/router';

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

    const { user } = useUser();

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
                {user?.data?.payload?.content?.user?.services?.length === 0 ? (
                    <Button variant="solid" className="!px-8 !rounded-xl !bg-blue-500" onClick={handleConnectWithGoogle}>
                        Authorize Google
                    </Button>
                ) : (
                    <Button variant="solid" className="md:ml-3 w-full sm:w-auto !px-8 !rounded-xl !bg-blue-500" onClick={handleImportForms}>
                        Import Forms
                    </Button>
                )}
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
                                        <div className="flex flex-col justify-start h-full">
                                            <p className="text-xl text-grey mb-4 p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.title, 15) : toEndDottedStr(form.title, 30)}</p>
                                            {form?.description && (
                                                <p className="text-base text-softBlue m-0 p-0 w-full">
                                                    {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                                </p>
                                            )}
                                            {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
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
