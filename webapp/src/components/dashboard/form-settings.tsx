import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';

import LockIcon from '@Components/Common/Icons/lock';
import { Lock } from '@mui/icons-material';
import { Button, FormControlLabel, Radio, RadioGroup } from '@mui/material';
import FormControlContext from '@mui/material/FormControl/FormControlContext';
import Switch from '@mui/material/Switch';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
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

import Globe from '../icons/flags/globe';
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

    const onPrivateChanged = ({ isPrivate = false, f }: { isPrivate?: boolean; f?: StandardFormDto }) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        const patchBody = { private: isPrivate, pinned: false };
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
                <p className="sh3">Form Visibility</p>
                <RadioGroup className="flex flex-col gap-6" defaultValue={form?.settings?.private ? 'Private' : 'Public'}>
                    <div className="flex flex-col">
                        <FormControlLabel
                            onChange={() => onPrivateChanged({ f: form })}
                            value="Public"
                            control={<Radio />}
                            label={
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <Globe className="h-[18px] w-[18px]" />
                                    Public
                                </div>
                            }
                        />
                        <span className="ml-8 body4 !text-black-700">Forms will only be hidden from your workspace.</span>
                    </div>
                    <div className="flex flex-col">
                        <FormControlLabel
                            onChange={() => onPrivateChanged({ isPrivate: true, f: form })}
                            value="Private"
                            control={<Radio />}
                            label={
                                <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                    <LockIcon className="h-[18px] w-[18px]" />
                                    Private
                                </div>
                            }
                        />
                        <span className="ml-8 body4 !text-black-700">Forms will only be hidden from your workspace.</span>
                    </div>
                </RadioGroup>
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

            <div className="my-6">
                <Button
                    style={{ textTransform: 'none' }}
                    className="  bg-red-100 px-4 py-3 body6 rounded hover:bg-red-50 hover:drop-shadow-sm leading-none !text-red-500"
                    size="medium"
                    onClick={() => {
                        openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                    }}
                >
                    Delete Form
                </Button>
            </div>
        </div>
    );
}
