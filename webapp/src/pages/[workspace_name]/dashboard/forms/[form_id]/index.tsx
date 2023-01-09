import React, { useEffect } from 'react';

import Link from 'next/link';
import Router from 'next/router';

import { Feed, Settings } from '@mui/icons-material';

import { FormTabContent } from '@app/components/dashboard/form-overview';
import FormSubmissionsTab from '@app/components/dashboard/form-responses';
import FormSettingsTab from '@app/components/dashboard/form-settings';
import BreadcrumbsRenderer from '@app/components/form/renderer/breadcrumbs-renderer';
import { HistoryIcon } from '@app/components/icons/history';
import { HomeIcon } from '@app/components/icons/home';
import Layout from '@app/components/sidebar/layout';
import ParamTab from '@app/components/ui/param-tab';
import { TabPanel } from '@app/components/ui/tab';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import Error from '@app/pages/_error';
import { initialFormState, setForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { toEndDottedStr } from '@app/utils/stringUtils';

export default function FormPage(props: any) {
    const { formId, form } = props;
    const dispatch = useAppDispatch();

    useEffect(() => {
        dispatch(setForm(form));
        return () => {
            dispatch(setForm(initialFormState));
        };
    }, []);

    const breakpoint = useBreakpoint();
    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }
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

    const breadcrumbsItem = [
        {
            title: 'Forms',
            icon: <HomeIcon className="w-4 h-4 mr-2" />,
            onClick: () => Router.push(`/${props?.workspace?.workspaceName}/dashboard`)
        },
        {
            title: ['xs'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.title, 30) : form.title
        }
    ];

    return (
        <Layout>
            <BreadcrumbsRenderer breadcrumbsItem={breadcrumbsItem} />
            <div className="flex flex-col w-full m-auto justify-center">
                <ParamTab tabMenu={tabs}>
                    <TabPanel className="focus:outline-none" key="form">
                        <FormTabContent form={form} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="submissions">
                        <FormSubmissionsTab workspace={props.workspace} workspaceName={props?.workspace?.workspaceName} workspaceId={props?.workspace?.id ?? ''} formId={formId} />
                    </TabPanel>
                    <TabPanel className="focus:outline-none" key="settings">
                        <FormSettingsTab />
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
