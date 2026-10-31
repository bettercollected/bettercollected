'use client';

import { useState } from 'react';

import { useTranslation } from 'react-i18next';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { InspectorSection, SettingSwitch } from '@app/views/molecules/form-builder/inspector-controls';

/**
 * "Review answers before sending": respondents get a page after the last one
 * that lists their answers, with a way back to each page, and send from it.
 * Off by default. A form setting like the trust settings: saved at once
 * with the settings request, and the preview follows. The page itself is
 * drawn in the respondent's browser; nothing is stored before they send.
 */
export default function ReviewPageSetting() {
    const { t } = useTranslation('builder');
    const { toast } = useToast();
    const form = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const dispatch = useAppDispatch();
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const [saving, setSaving] = useState(false);

    const change = async (checked: boolean) => {
        setSaving(true);
        const response: any = await patchFormSettings({ workspaceId: workspace.id, formId: form.formId, body: { showReviewPage: checked } });
        setSaving(false);
        if (response.data) dispatch(setFormSettings(response.data.settings));
        else toast({ description: t('REVIEW_PAGE.ERROR'), variant: 'destructive' });
    };

    return (
        <InspectorSection title={t('REVIEW_PAGE.TITLE')}>
            <SettingSwitch label={t('REVIEW_PAGE.LABEL')} checked={!!form?.settings?.showReviewPage} disabled={saving} onCheckedChange={change} hint={t('REVIEW_PAGE.HINT')} />
        </InspectorSection>
    );
}
