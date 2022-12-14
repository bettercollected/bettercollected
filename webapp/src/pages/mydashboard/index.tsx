import { useEffect, useMemo } from 'react';

import { ShareIcon } from '@app/components/icons/share-icon';
import { useModal } from '@app/components/modal-views/context';
import Layout from '@app/components/sidebar/layout';
import Button from '@app/components/ui/button/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import ActiveLink from '@app/components/ui/links/active-link';
import useUser from '@app/lib/hooks/use-authuser';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { StandardFormDto } from '@app/models/dtos/form';
import { useGetWorkspaceFormsQuery } from '@app/store/google/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function CreatorDashboard() {
    const { openModal } = useModal();

    const { user, isLoading } = useUser();

    const workspaceForms = useGetWorkspaceFormsQuery(null);
    const breakpoint = useBreakpoint();

    if (isLoading) return <FullScreenLoader />;
    const forms = workspaceForms?.data?.payload?.content;

    const email = user?.data?.payload?.content?.user?.sub;

    const handleImportForms = () => {
        openModal('IMPORT_FORMS_VIEW');
    };

    const Header = () => (
        <div className="flex justify-between items-center mb-10">
            <div className="flex flex-col">
                <h1 className="font-extrabold text-3xl">Hello {email?.replaceAll('@gmail.com', '')}!</h1>
                <p className="text-gray-600">Here you have the summary of the week</p>
            </div>

            <Button variant="solid" className="ml-3 !px-3 !rounded-xl !bg-blue-500" onClick={handleImportForms}>
                Import Forms
            </Button>
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
                                <ActiveLink
                                    key={form.formId}
                                    href={{
                                        pathname: `/forms/[slug]`,
                                        query: { slug }
                                    }}
                                >
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
                                </ActiveLink>
                            );
                        })}
                </div>
            </div>
        );
    };

    // {
    //     !!user && !isLoading ? (
    //         <Layout>
    //             <Header />
    //             <MyRecentForms />
    //         </Layout>
    //     ) : (
    //         <></>
    //     );
    // }

    return (
        <Layout>
            <Header />
            <MyRecentForms />
        </Layout>
    );
}

// export const getServerSideProps = async (context: any) => {
//     const cookies = context.req.headers.cookie;
//     console.log('cookies:', cookies);

//     return {
//         props: {}
//     };
// };
