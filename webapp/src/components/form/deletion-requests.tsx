import React from 'react';

import { useTranslation } from 'next-i18next';

import FormResponsesTable from '@app/components/datatable/form/form-responses';
import { formConstant } from '@app/constants/locales/form';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';

export default function FormDeletionRequests() {
    const { t } = useTranslation();
    const requestForDeletion = true;
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    return (
        <>
            <p className="body1">
                {t(formConstant.deletionRequests)} ({form.deletionRequests})
            </p>
            <FormResponsesTable props={{ formId: form.formId, workspace, requestForDeletion }} />
        </>
    );
}
