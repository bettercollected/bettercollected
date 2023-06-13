import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import Switch from '@mui/material/Switch';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
import Button from '@app/components/ui/button';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { customize } from '@app/constants/locales/customize';
import { formConstant } from '@app/constants/locales/form';
import { localesGlobal } from '@app/constants/locales/global';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectIsProPlan } from '@app/store/auth/slice';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';

import FormLinkUpdateView from '../ui/form-link-update-view';

export default function FormSettingsTab() {
    const { t } = useTranslation();
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const dispatch = useAppDispatch();
    const isProPlan = useAppSelector(selectIsProPlan);
    const [_, copyToClipboard] = useCopyToClipboard();
    const { openModal } = useModal();
    const isCustomDomain = !!workspace.customDomain;
    const customUrl = form?.settings?.customUrl || '';
    const clientHost = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.CLIENT_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;
    const clientHostUrl = `${clientHost}/${customUrl}`;
    const customDomainUrl = `${customDomain}/${customUrl}`;

    const patchSettings = async (body: any, f: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: f.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setFormSettings(settings));
            toast(t(localesGlobal.updated).toString(), { type: 'success' });
        } else {
            toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onPrivateChanged = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: !f?.settings?.private, pinned: false };
        patchSettings(patchBody, f)
            .then((res) => {})
            .catch((e: any) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    return (
        <div>
            <FormSettingsCard>
                <p className="sh3">Default Link</p>
                <p className="body4 !text-black-700 mt-4 !mb-6">{t(customize.link.description)}</p>
                <FormLinkUpdateView link={clientHostUrl} />
            </FormSettingsCard>
            <FormSettingsCard>
                <p className="sh3">Customize Form Link</p>
                <p className="body4 !text-black-700 mt-4 mb-10">{t(customize.link.description)}</p>
                <p className="w-full body6 mb-4 !font-semibold text-black-900">{t(updateWorkspace.common.consequence)}</p>
                <ul className="list-disc body4 ml-10 !mb-6">
                    <li className="mb-4">{t(updateWorkspace.handles.point1)}</li>
                    <li>{t(updateWorkspace.handles.point2)}</li>
                </ul>
                <FormLinkUpdateView link={isCustomDomain ? customDomainUrl : clientHostUrl} isLinkChangable />
            </FormSettingsCard>
            <FormSettingsCard>
                <div className=" flex items-center justify-between">
                    <div>
                        <div className="body1">{t(formConstant.hide)}</div>
                        <div className="body3">{t(formConstant.hideDescription)}</div>
                    </div>
                    <Switch data-testid="private-switch" checked={!!form?.settings?.private} onClick={(e) => onPrivateChanged(e, form)} />
                </div>
            </FormSettingsCard>
            {!form?.settings?.private && (
                <FormSettingsCard>
                    <div className=" flex items-center justify-between">
                        <div>
                            <div className="body1">{t(formConstant.pinned)}</div>
                            <div className="body3">{t(formConstant.pinnedDescription)}</div>
                        </div>
                        <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned} onClick={(e) => onPinnedChange(e, form)} />
                    </div>
                </FormSettingsCard>
            )}

            <FormSettingsCard>
                <div className="flex flex-col sm:flex-row items-end justify-between gap-5">
                    <div className="">
                        <div className="body1">{t(formConstant.delete)}</div>
                        <div className="body3">
                            <div>{t(formConstant.deleteDescription)}</div>
                        </div>
                    </div>
                    <Button
                        data-testid="logout-button"
                        variant="solid"
                        size="medium"
                        color="danger"
                        onClick={() => {
                            openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                        }}
                    >
                        {t(buttonConstant.delete)}
                    </Button>
                </div>
            </FormSettingsCard>
        </div>
    );
}
