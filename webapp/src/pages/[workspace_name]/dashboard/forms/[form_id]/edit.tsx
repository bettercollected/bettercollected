import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import FormBuilderContainerWrapper from '@Components/HOCs/FormBuilderContainerWrapper';
import FormBuilderKeyListener from '@Components/Listeners/FormBuilderKeyListener';

import environments from '@app/configs/environments';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import FormBuilder from '@app/containers/form-builder/FormBuilder';
import Layout from '@app/layouts/_layout';
import { getServerSidePropsForDashboardFormPage } from '@app/lib/serverSideProps';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, setEditForm } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

export default function EditFromPage(props: any) {
    const {
        form,
        workspace,
        _nextI18Next
    }: {
        form: StandardFormDto;
        workspace: WorkspaceDto;
        _nextI18Next: any;
    } = props;
    const dispatch = useAppDispatch();
    const { title } = useAppSelector(selectBuilderState);
    const { t } = useTranslation();

    useEffect(() => {
        return () => {
            dispatch(resetForm());
        };
    }, []);

    useEffect(() => {
        dispatch(setEditForm(form));
    }, [form]);

    return (
        <FormBuilderContainerWrapper>
            <FormBuilderKeyListener>
                <NextSeo title={title || t(metaDataTitle.editForm)} noindex={true} nofollow={true} />
                <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col !min-h-calc-68">
                    <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} isEditMode />
                </Layout>
            </FormBuilderKeyListener>
        </FormBuilderContainerWrapper>
    );
}

export async function getServerSideProps(_context: any) {
    if (!environments.ENABLE_FORM_BUILDER)
        return {
            notFound: true
        };
    const globalProps = await getServerSidePropsForDashboardFormPage(_context);
    if (globalProps?.props?.form?.settings?.provider !== 'self') {
        return {
            notFound: true
        };
    }

    return {
        ...globalProps
    };
}
