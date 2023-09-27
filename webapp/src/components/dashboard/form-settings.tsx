import React from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import Pro from '@Components/Common/Icons/Pro';
import LockIcon from '@Components/Common/Icons/lock';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { Button, Drawer, FormControlLabel, Radio, RadioGroup } from '@mui/material';
import Switch from '@mui/material/Switch';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { customize } from '@app/constants/locales/customize';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import ProPlanHoc from '../hoc/pro-plan-hoc';
import Globe from '../icons/flags/globe';
import { useFullScreenModal } from '../modal-views/full-screen-modal-context';
import FormLinkUpdateView from '../ui/form-link-update-view';
import AnchorLink from '../ui/links/anchor-link';
import UpgradeToPro from '../ui/upgrade-to-pro';

interface IFormSettingsTabProps {
    view?: FormSettingsTabView;
}

export type FormSettingsTabView = 'VISIBILITY' | 'LINKS' | 'DEFAULT';

export default function FormSettingsTab({ view='DEFAULT' }: IFormSettingsTabProps) {
    const { t } = useTranslation();
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const dispatch = useAppDispatch();
    const { openModal } = useModal();
    const fullScreenModal = useFullScreenModal();
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
            toast(t(localesCommon.updated).toString(), { type: 'success' });
        } else {
            if (response.error.status === 409) {
                toast(t('TOAST.SLUG_ALREADY_EXISTS').toString(), { type: 'error' });
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error' });
            }
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        console.log(f);
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

    const onDisableBrandingChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        patchSettings({ disableBranding: !f?.settings?.disableBranding }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const isProPlan = useAppSelector(selectWorkspace).isPro;
    const isAdmin = useAppSelector(selectIsAdmin);

    const showSettingsTabView = (view: FormSettingsTabView) => {
        switch (view) {
            case 'VISIBILITY':
                return (
                    <FormSettingsCard>
                        <Divider />
                        {/* <p className="sh3">{t(formConstant.settings.visibility.title)}</p> */}
                        <RadioGroup className="flex flex-col gap-6" defaultValue={form?.settings?.private ? 'Private' : 'Public'}>
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onPrivateChanged({ f: form })}
                                    value="Public"
                                    control={<Radio />}
                                    label={
                                        <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                            <Globe className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.public)}
                                        </div>
                                    }
                                />
                                <span className="ml-8 body4 !text-black-700">Everyone can see this form.</span>
                            </div>
                            <Divider />

                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onPrivateChanged({ isPrivate: true, f: form })}
                                    value="Private"
                                    control={<Radio />}
                                    label={
                                        <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                            <LockIcon className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.private)}
                                        </div>
                                    }
                                />
                                <span className="ml-8 body4 !text-black-700">Only you can see this form.</span>
                            </div>
                            <Divider />
                        </RadioGroup>
                    </FormSettingsCard>
                );
            case 'LINKS':
                return (
                    <div className="flex flex-col gap-8">
                        <FormSettingsCard>
                            <FormLinkUpdateView link={isCustomDomain ? customDomainUrl : clientHostUrl} isDisable={!isProPlan && isAdmin} />

                            <FormLinkUpdateView link={clientHostUrl} isLinkChangable />
                        </FormSettingsCard>
                    </div>
                );
            case 'DEFAULT':
                return (
                    <div className=" flex flex-col gap-7 mb-10 ">
                        {form?.isPublished && (
                            <>
                                {!form?.settings?.private && (
                                    <FormSettingsCard>
                                        <div className=" flex flex-col items-start w-full">
                                            <div className="h5-new !text-black-800">Pin Form</div>
                                            <hr className="h-0.5 w-full bg-black-200 my-2" />
                                            <div className="flex flex-row md:gap-4 justify-between items-center">
                                                <div className="body4 !text-black-700 w-3/4">
                                                    When you pin a form in bettercollected, the form will be added to the top of the form so that it is the first thing that your audience can see from your form page.
                                                </div>
                                                <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned} onClick={(e) => onPinnedChange(e, form)} />
                                            </div>
                                            <hr className="h-0.5 w-full bg-black-200 my-2" />
                                        </div>
                                    </FormSettingsCard>
                                )}
                                <FormSettingsCard className={cn('', !isProPlan && isAdmin && '')}>
                                    <div className=" flex items-start flex-col w-full">
                                        <div className="h5-new !text-black-800 flex flex-row gap-4 justify-between">
                                            <h1>bettercolleceted branding</h1>
                                            <div className="flex items-center rounded h-5 sm:h-6 p-1 sm:p-[6px] text-[10px] sm:body5 uppercase !leading-none !font-semibold !text-white bg-brand-500">
                                                <Pro width={12} height={12} />
                                                <span className="leading-none">Pro</span>
                                            </div>
                                        </div>
                                        <hr className="h-0.5 w-full bg-black-200 my-2" />
                                        <div className="flex flex-row w-full md:gap-4 justify-between items-center">
                                            <div className="body4 !text-black-700 w-3/4">Show Powered by: bettercollected in your form.</div>
                                            <Switch disabled={!isProPlan} data-testid="disable-branding-switch" checked={!form?.settings?.disableBranding} onClick={(e) => onDisableBrandingChange(e, form)} />
                                        </div>
                                        <hr className="h-0.5 w-full bg-black-200 my-2" />
                                    </div>
                                    {/* {!isProPlan && isAdmin && <UpgradeToPro />} */}
                                </FormSettingsCard>
                            </>
                        )}
                        <FormSettingsCard>
                            <div className="flex flex-col items-start w-full">
                                <div className="body1">Form Purpose and Data Usage</div>
                                <hr className="h-0.5 w-full bg-black-200 my-2" />

                                <div className=" w-full flex flex-row justify-between items-center gap-4">
                                    <div className="text-sm !text-black-700">{`This page is to help you to provide you with a clear understanding of how how your information is handled in our form. Our aim is to ensure you're fully informed and comfortable with how we handle your data.`}</div>
                                    <AppButton
                                        variant={ButtonVariant.Ghost}
                                        className="h5-new !text-new-blue-500 w-60 cursor-pointer"
                                        onClick={() => {
                                            fullScreenModal.openModal('CREATE_CONSENT_FULL_MODAL_VIEW', { form, isPreview: true });
                                        }}
                                    >
                                        See Details
                                    </AppButton>
                                </div>
                                <hr className="h-0.5 w-full bg-black-200 my-2" />
                            </div>
                        </FormSettingsCard>
                        <div className="mt-6">
                            <AppButton
                                onClick={() => {
                                    openModal('DELETE_FORM_MODAL', { form, redirectToDashboard: true });
                                }}
                                variant={ButtonVariant.Danger}
                            >
                                {t(buttonConstant.deleteForm)}
                            </AppButton>
                        </div>
                    </div>
                );
            default:
                return <></>;
        }
    };

    return showSettingsTabView(view);
}
