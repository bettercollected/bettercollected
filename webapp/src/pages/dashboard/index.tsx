import Link from 'next/link';
import { useRouter } from 'next/router';

import { ShareIcon } from '@app/components/icons/share-icon';
import { useModal } from '@app/components/modal-views/context';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import environments from '@app/configs/environments';
import useUser from '@app/lib/hooks/use-authuser';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import globalServerProps from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function CreatorDashboard() {
    const { openModal } = useModal();
    const router = useRouter();

    const { user } = useUser();

    const workspaceForms = useGetWorkspaceFormsQuery<any>(environments.WORKSPACE_ID);

    const breakpoint = useBreakpoint();

    const forms = workspaceForms?.data?.payload?.content;

    const email = user?.data?.payload?.content?.user?.sub;

    console.log(user?.data?.payload?.content);

    const handleImportForms = () => {
        openModal('IMPORT_FORMS_VIEW');
    };

    const handleConnectWithGoogle = () => {
        router.push(`${environments.API_ENDPOINT_HOST}/auth/google/connect`);
    };

    const Header = () => (
        <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center mb-10 py-4 pt-4 border-b-[1px] border-b-gray-200">
            <div className="flex flex-col">
                <h1 className="font-extrabold text-3xl">Hello {email?.replaceAll('@gmail.com', '')}!</h1>
                <p className="text-gray-600">Here are your forms</p>
            </div>

            {user?.data?.payload?.content?.user?.services?.length === 0 ? (
                <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleConnectWithGoogle}>
                    Authorize Google
                </Button>
            ) : (
                <Button variant="solid" className="ml-3 !px-8 !rounded-xl !bg-blue-500" onClick={handleImportForms}>
                    Import Forms
                </Button>
            )}
        </div>
    );

    // UI for forms
    const MyRecentForms = () => {
        return (
            <div>
                <h1 className="font-semibold text-2xl mb-4">My Recent Forms</h1>
                <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto) => {
                            const slug = form.settings.customUrl;
                            let shareUrl = '';
                            if (window && typeof window !== 'undefined') {
                                shareUrl = `${window.location.origin}/forms/${slug}`;
                            }
                            return (
                                <Link key={form.formId} href={`/dashboard/forms/${form.formId}`}>
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
                                        <div
                                            aria-hidden
                                            onClick={(event) => {
                                                event.preventDefault();
                                                // handlePinnedForms(form.formId);
                                                // copyToClipboard(shareUrl);
                                                // setIsOpen(true);
                                            }}
                                            className="flex flex-col border-white hover:border-neutral-100 rounded-md"
                                        >
                                            <ShareIcon width={19} height={19} />
                                            {/* <PinOutlinedIcon width={40} height={40} clickButton={() => console.log('clicked')} /> */}
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
    const { cookies } = _context.req;
    const globalProps = (await globalServerProps(_context)).props;
    if (globalProps.hasCustomDomain) {
        return {
            redirect: {
                permanent: false,
                destination: '/'
            }
        };
    }
    const auth = !!cookies.Authorization ? `Authorization=${cookies.Authorization}` : '';
    const refresh = !!cookies.RefreshToken ? `RefreshToken=${cookies.RefreshToken}` : '';

    const config = {
        method: 'GET',
        headers: {
            cookie: `${auth};${refresh}`
        }
    };

    try {
        const userStatus = await fetch(`${environments.API_ENDPOINT_HOST}/auth/status`, config);
        const user = (await userStatus?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (!user?.user?.roles?.includes('FORM_CREATOR')) {
            return {
                redirect: {
                    permanent: false,
                    destination: '/login'
                }
            };
        }
    } catch (e) {
        return {
            redirect: {
                permanent: false,
                destination: '/login'
            }
        };
    }
    return {
        props: {}
    };
}
