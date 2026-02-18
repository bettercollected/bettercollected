'use client';

import React, { useEffect } from 'react';
import { useTranslation } from 'react-i18next';

import FormBuilderKeyListener from '@Components/Listeners/FormBuilderKeyListener';
import HistoryKeyListener from '@Components/Listeners/HistoryKeyListener';

import FormBuilder from '@app/containers/form-builder/FormBuilder';
import Layout from '@app/layouts/_layout';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { resetForm, setEditForm } from '@app/store/form-builder/actions';
import { useAppDispatch } from '@app/store/hooks';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';

export default function EditTemplateClient({ workspace, templateId, template, _nextI18Next }: { workspace: WorkspaceDto, templateId: string, template: any, _nextI18Next?: any }) {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();

    useEffect(() => {
        dispatch(setEditForm(convertFormTemplateToStandardForm(template)));
        return () => {
            dispatch(resetForm());
        };
    }, [template, dispatch]);

    return (
        <HistoryKeyListener>
            <FormBuilderKeyListener>
                <Layout isCustomDomain={false} isClientDomain={false} showNavbar={true} hideMenu={false} showAuthAccount={true} className="!p-0 !bg-white flex flex-col " childClassName={'h-screen md:h-full'}>
                    <FormBuilder workspace={workspace} _nextI18Next={_nextI18Next} templateId={templateId} isTemplate />
                </Layout>
            </FormBuilderKeyListener>
        </HistoryKeyListener>
    );
}
