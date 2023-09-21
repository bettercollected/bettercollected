import { useEffect } from 'react';

import { useTranslation } from 'next-i18next';
import { NextSeo } from 'next-seo';

import FormBuilderContainerWrapper from '@Components/HOCs/FormBuilderContainerWrapper';
import FormBuilderKeyListener from '@Components/Listeners/FormBuilderKeyListener';
import HistoryKeyListener from '@Components/Listeners/HistoryKeyListener';

import environments from '@app/configs/environments';
import { metaDataTitle } from '@app/constants/locales/meta-data-title';
import FormBuilder from '@app/containers/form-builder/FormBuilder';
import Layout from '@app/layouts/_layout';
import { getAuthUserPropsWithWorkspace } from '@app/lib/serverSideProps';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm } from '@app/store/form-builder/actions';
import { selectBuilderState } from '@app/store/form-builder/selectors';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';

interface ICreateFormProps {
    workspace: WorkspaceDto;
    _nextI18Next: any;
}

export default function CreateFormPage({ workspace, _nextI18Next }: ICreateFormProps) {
    const dispatch = useAppDispatch();
    const { title } = useAppSelector(selectBuilderState);
    const { t } = useTranslation();

    useEffect(() => {
        dispatch(resetForm());
    }, []);

    return environments.ENABLE_FORM_BUILDER ? (
        <FormBuilderContainerWrapper>
            <HistoryKeyListener>
                <FormBuilderKeyListener>
                    <NextSeo title={title || t(metaDataTitle.createForm)} noindex={true} nofollow={true} />
                    <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col !min-h-calc-68">
                        <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} />
                    </Layout>
                </FormBuilderKeyListener>
            </HistoryKeyListener>
        </FormBuilderContainerWrapper>
    ) : (
        <></>
    );
}

export async function getServerSideProps(_context: any) {
    if (!environments.ENABLE_FORM_BUILDER)
        return {
            notFound: true
        };
    const globalProps = await getAuthUserPropsWithWorkspace(_context);
    return {
        props: { ...globalProps.props }
    };
}
