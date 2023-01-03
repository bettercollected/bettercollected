import React from 'react';

import Link from 'next/link';

import { Feed, Settings } from '@mui/icons-material';

import { FormTabContent } from '@app/components/dashboard/form-overview';
import FormSubmissionsTab from '@app/components/dashboard/form-responses';
import FormSettingsTab from '@app/components/dashboard/form-settings';
import { HistoryIcon } from '@app/components/icons/history';
import Layout from '@app/components/sidebar/layout';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import environments from '@app/configs/environments';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import Error from '@app/pages/_error';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';

export default function FormPage(props: any) {
    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }

    console.log(props);
    const { formId, form } = props;

    const tabs = [
        {
            icon: <Feed />,
            path: 'form',
            title: 'Form'
        },
        {
            icon: <HistoryIcon className="w-[20px] h-[20px]" />,
            title: 'Responses',
            path: 'response'
        },
        {
            icon: <Settings />,
            title: 'Settings',
            path: 'settings'
        }
    ];

    return (
        <Layout>
            <div className="max-h-[100vh] overflow-auto mb-4">
                <nav className="flex mt-3 px-0 md:px-0" aria-label="Breadcrumb">
                    <ol className="inline-flex items-center space-x-1 md:space-x-3">
                        <li className="inline-flex items-center">
                            <Link href={`/${props?.workspace?.workspaceName}/dashboard`}>
                                <span aria-hidden className="cursor-pointer inline-flex items-center text-sm font-medium text-gray-700 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white">
                                    <svg className="w-4 h-4 mr-2" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                        <path d="M10.707 2.293a1 1 0 00-1.414 0l-7 7a1 1 0 001.414 1.414L4 10.414V17a1 1 0 001 1h2a1 1 0 001-1v-2a1 1 0 011-1h2a1 1 0 011 1v2a1 1 0 001 1h2a1 1 0 001-1v-6.586l.293.293a1 1 0 001.414-1.414l-7-7z"></path>
                                    </svg>
                                    Forms
                                </span>
                            </Link>
                        </li>
                        <li aria-current="page">
                            <div className="flex items-center">
                                <svg className="w-6 h-6 text-gray-400" fill="currentColor" viewBox="0 0 20 20" xmlns="http://www.w3.org/2000/svg">
                                    <path fillRule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clipRule="evenodd"></path>
                                </svg>
                                <span className="ml-1 text-sm font-medium text-gray-500 md:ml-2 dark:text-gray-400">{formId}</span>
                            </div>
                        </li>
                    </ol>
                </nav>
            </div>
            <div className="flex flex-col w-full m-auto justify-center">
                <ParamTab tabMenu={tabs}>
                    <TabPanel className="focus:outline-none" key="form">
                        <FormTabContent form={form} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="submissions">
                        <FormSubmissionsTab workspace={props.workspace} workspaceName={props?.workspace?.workspaceName} workspaceId={props?.workspace?.id ?? ''} formId={formId} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="settings">
                        <FormSettingsTab formId={formId} form={form} />
                    </TabPanel>
                </ParamTab>
            </div>
        </Layout>
    );
}

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    if (!props.props) {
        return props;
    }
    const globalProps = props.props;
    const { form_id } = _context.query;
    let form = null;
    try {
        const formResponse = await fetch(`${environments.API_ENDPOINT_HOST}/workspaces/${globalProps.workspace.id}/forms?form_id=${form_id}`);
        form = (await formResponse?.json().catch((e: any) => e))?.payload?.content ?? null;
        if (!form) {
            return {
                notFound: true
            };
        }

        return {
            props: {
                formId: form_id,
                ...globalProps,
                form
            }
        };
    } catch (e) {
        return {
            props: {
                error: true
            }
        };
    }
}
