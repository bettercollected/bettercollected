import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import FormBuilderKeyListener from '@Components/Listeners/FormBuilderKeyListener';
import HistoryKeyListener from '@Components/Listeners/HistoryKeyListener';

import environments from '@app/configs/environments';
import FormBuilder from '@app/containers/form-builder/FormBuilder';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, setEditForm } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import { getServerSideAuthHeaderConfig } from '@app/utils/serverSidePropsUtils';


export default function EditFromPage(props: any) {
    const {
        form,
        workspace,
        _nextI18Next,
        templateId,
        template
    }: {
        form: StandardFormDto;
        workspace: WorkspaceDto;
        _nextI18Next: any;
        templateId: string;
        template: any;
    } = props;
    const dispatch = useAppDispatch();
    const { t } = useTranslation();

    useEffect(() => {
        dispatch(setEditForm(convertFormTemplateToStandardForm(template)));
        return () => {
            dispatch(resetForm());
        };
    }, [form]);

    return (
        <HistoryKeyListener>
            <FormBuilderKeyListener>
                <NextSeo title={`${template.title ? template.title + ' | ' : ''} ${t('BUTTON.EDIT')}`} noindex={true} nofollow={true} />
                <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col " childClassName={'h-screen md:h-full'}>
                    <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} templateId={templateId} isTemplate />
                </Layout>
            </FormBuilderKeyListener>
        </HistoryKeyListener>
    );
}

export async function getServerSideProps(_context: any) {
    const props = await getAuthUserPropsWithWorkspace(_context);
    const { template_id } = _context.params;
    if (!props.props) {
        return props;
    }
    const globalProps = props.props;
    const config = getServerSideAuthHeaderConfig(_context);
    try {
        const template_response = await fetch(`${environments.INTERNAL_DOCKER_API_ENDPOINT_HOST}/templates/${template_id}?workspace_id=${globalProps?.workspace?.id}`, config);
        const template = (await template_response?.json().catch((e: any) => e)) ?? null;
        if (!template) {
            return {
                notFound: true
            };
        }
        return {
            props: {
                template,
                templateId: template_id,
                ...globalProps
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