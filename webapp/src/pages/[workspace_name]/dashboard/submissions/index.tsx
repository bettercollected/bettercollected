import { useEffect, useState } from 'react';

import Router, { useRouter } from 'next/router';

import { toast } from 'react-toastify';

import EmptyFormsView from '@app/components/dashboard/empty-form';
import FormRenderer from '@app/components/form-renderer/FormRenderer';
import Layout from '@app/components/sidebar/layout';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getGlobalServerSidePropsByWorkspaceName } from '@app/lib/serverSideProps';
import { useGetWorkspaceAllSubmissionsQuery, useLazyGetWorkspaceSubmissionQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function MySubmissions({ workspace }: { workspace: any }) {
    const submissionsQuery = useGetWorkspaceAllSubmissionsQuery(workspace?.id || '');
    const breakpoint = useBreakpoint();
    const [trigger, { isLoading, isError, data }] = useLazyGetWorkspaceSubmissionQuery();

    const [responseObject, setResponseObject] = useState({});
    const [form, setForm] = useState([]);

    const [responseId, setResponseId] = useState('');

    const router = useRouter();

    const submissionId = router.query.sub_id;

    const convertToClientForm = (formsArray: Array<any>) => {
        const responseMap = formsArray.reduce(function (accumulator, value) {
            if (!accumulator[value.formId]) {
                accumulator[value.formId] = {
                    title: value.formTitle,
                    responses: [value]
                };
            } else {
                accumulator[value.formId].responses.push(value);
            }
            return accumulator;
        }, Object.create(null));

        return responseMap;
    };

    const handleSubmissionClick = (responseId: any) => {
        router.push({
            pathname: router.pathname,
            query: {
                ...router.query,
                sub_id: responseId
            }
        });
    };

    useEffect(() => {
        if (!!submissionId) {
            const submissionQuery = {
                workspace_id: workspace.id,
                submission_id: submissionId
            };
            trigger(submissionQuery)
                .then((d: any) => {
                    setForm(d.data?.payload?.content);
                })
                .catch((e) => {
                    toast.error('Error fetching submission data.');
                });
        }
    }, [submissionId]);

    const handleRemoveSubmissionId = () => {
        const updatedQuery = { ...router.query };
        delete updatedQuery.sub_id;
        router.push({
            pathname: router.pathname,
            query: updatedQuery
        });
    };

    useEffect(() => {
        if (!submissionsQuery?.isLoading && !!submissionsQuery?.data?.payload?.content) {
            const responseMapObject = convertToClientForm(submissionsQuery?.data?.payload?.content);
            setResponseObject(responseMapObject);
        }
    }, [submissionsQuery]);

    const CardRenderer = () => {
        return (
            <>
                {Object.values(responseObject).length === 0 && <EmptyFormsView />}
                {!!Object.values(responseObject).length &&
                    Object.values(responseObject).map((response: any, idx: any) => {
                        return (
                            <div key={idx} className="mb-4">
                                <h1 className="text-xl font-semibold text-gray-700 mb-6 mt-6 inline-block pb-3 border-b-[1px] border-gray-300">
                                    {response.title} ({response.responses.length})
                                </h1>
                                <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                                    {response.responses.map((form: any) => {
                                        return (
                                            <div
                                                onClick={() => handleSubmissionClick(form.responseId)}
                                                key={form.responseId}
                                                className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]"
                                            >
                                                <div className="flex flex-col justify-start h-full overflow-hidden">
                                                    <p className="text-sm text-gray-400 italic ">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.responseId, 15) : toEndDottedStr(form.responseId, 30)}</p>
                                                    <p className="text-xl text-grey mb-4 p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.formTitle, 15) : toEndDottedStr(form.formTitle, 30)}</p>
                                                    {form?.description && (
                                                        <p className="text-base text-softBlue m-0 p-0 w-full">
                                                            {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                                        </p>
                                                    )}
                                                    {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
                                                    <p className="italic w-fit bg-blue-100 text-gray-700 text-[10px] px-2 py-1 rounded-lg">{!form.dataOwnerIdentifier ? 'Anonymous' : form.dataOwnerIdentifier}</p>
                                                </div>
                                            </div>
                                        );
                                    })}
                                </div>
                            </div>
                        );
                    })}
            </>
        );
    };

    // UI for forms
    const MyRecentSubmissions = () => {
        return (
            <div>
                <h1 className="font-semibold text-2xl mb-4">Submissions</h1>
            </div>
        );
    };

    const BreadCrumbRenderer = () => {
        return (
            <div className="max-h-[100vh] overflow-auto mb-4">
                <nav className="flex mt-3 px-0 md:px-0" aria-label="Breadcrumb">
                    <ol className="inline-flex items-center space-x-1 md:space-x-3">
                        <li className="inline-flex items-center">
                            <span aria-hidden onClick={handleRemoveSubmissionId} className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
                                </svg>
                                Responses
                            </span>
                        </li>
                        <li aria-current="page">
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"></path>
                                </svg>
                                {!!submissionId && <span className="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">{['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(submissionId, 10) : submissionId}</span>}
                            </div>
                        </li>
                    </ol>
                </nav>
            </div>
        );
    };

    if (isLoading) return <FullScreenLoader />;

    return (
        <Layout>
            {!submissionId && (
                <>
                    <MyRecentSubmissions />
                    <CardRenderer />
                </>
            )}
            {!!submissionId && <BreadCrumbRenderer />}
            {!!submissionId && <FormRenderer form={form} />}
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const { cookies } = _context.req;
    const globalProps = (await getGlobalServerSidePropsByWorkspaceName(_context)).props;
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
        props: {
            ...globalProps
        }
    };
}
