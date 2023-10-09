import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import EditIcon from '@Components/Common/Icons/Edit';
import Pro from '@Components/Common/Icons/Pro';
import LockIcon from '@Components/Common/Icons/lock';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { FormControlLabel, Radio, RadioGroup } from '@mui/material';
import Switch from '@mui/material/Switch';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { GroupIcon } from '@app/components/icons/group-icon';
import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';

import Globe from '../icons/flags/globe';
import { useFullScreenModal } from '../modal-views/full-screen-modal-context';
import FormLinkUpdateView from '../ui/form-link-update-view';

interface IFormSettingsTabProps {
    view?: FormSettingsTabView;
}

export type FormSettingsTabView = 'VISIBILITY' | 'LINKS' | 'DEFAULT';

export default function FormSettingsTab({ view = 'DEFAULT' }: IFormSettingsTabProps) {
    const { t } = useTranslation();
    const form = useAppSelector(selectForm);
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
    const defaultValueForVisibility = () => {
        if (form?.settings?.hidden) return 'Private';
        else if (form?.settings?.private) return 'Group';
        else return 'Public';
    };

    const [currentVisibility, setCurrentVisibility] = useState(defaultValueForVisibility());

    useEffect(() => {
        setCurrentVisibility(defaultValueForVisibility());
    }, [form?.settings?.hidden, form?.settings?.private]);

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
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), { type: 'error', toastId: 'errorToast' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => {})
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onVisibilityChanged = ({ isPrivate = false, isHidden = false, f }: { isPrivate?: boolean; isHidden?: boolean; f?: StandardFormDto }) => {
        const visibilityType = () => {
            if (isHidden) return 'Private';
            else if (isPrivate) return 'Group';
            else return 'Public';
        };
        const handleOnConfirm = () => {
            if (!f)
                return toast(t(toastMessage.formSettingUpdateError).toString(), {
                    type: 'error',
                    toastId: 'errorToast'
                });
            const patchBody = { private: isPrivate, pinned: false, hidden: isHidden };
            patchSettings(patchBody, f)
                .then((res) => {})
                .catch((e: any) => {
                    toast(e.data, { type: 'error', toastId: 'errorToast' });
                });
        };
        openModal('VISIBILITY_CONFIRMATION_MODAL_VIEW', { visibilityType: visibilityType(), handleOnConfirm });
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
                    <FormSettingsCard className={'mb-4'}>
                        <Divider />
                        {/* <p className="sh3">{t(formConstant.settings.visibility.title)}</p> */}
                        <RadioGroup className="flex flex-col gap-6" value={currentVisibility}>
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onVisibilityChanged({ f: form })}
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
                                    onChange={() => onVisibilityChanged({ isHidden: true, f: form })}
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
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => patchSettings({ hidden: false, pinned: false, private: true }, form)}
                                    value="Group"
                                    control={<Radio />}
                                    label={
                                        <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                            <GroupIcon className="h-[18px] w-[18px]" />
                                            Only For Certain Groups
                                        </div>
                                    }
                                />
                                <span className="ml-8 body4 !text-black-700">{!(form?.groups.length === 0) ? 'Only members in this group can see this form.' : 'No Groups Selected.'}</span>
                                {currentVisibility === 'Group' && <FormGroups groups={form?.groups} />}
                            </div>
                            <Divider />
                        </RadioGroup>
                    </FormSettingsCard>
                );
            case 'LINKS':
                return (
                    <FormSettingsCard className={'!space-y-0 !mt-0'}>
                        <p className="w-full body4 !text-black-700 lg:w-[564px]">Create personalized form links that align with their branding or specific requirements. A link slug is a brief, descriptive part of a URL that identifies web page content.</p>
                        <div className={'flex flex-row gap-2 items-start py-1 '}>
                            <p className="body4 !text-black-700 mt-1 mb-11 truncate">
                                {isCustomDomain ? customDomain : clientHost}/<span className={'text-pink-500'}>{customUrl}</span>
                            </p>
                            <AppButton
                                className={'!py-0'}
                                icon={<EditIcon className="h-6 w-6" />}
                                onClick={() => {
                                    fullScreenModal.openModal('FORM_CREATE_SLUG_VIEW', {
                                        link: isCustomDomain ? customDomain : clientHost,
                                        customSlug: customUrl
                                    });
                                }}
                                variant={ButtonVariant.Ghost}
                            >
                                Change Slug
                            </AppButton>
                        </div>
                        <div className={'flex flex-col gap-16'}>
                            {isCustomDomain && <FormLinkUpdateView isCustomDomain={isCustomDomain} link={customDomainUrl} />}
                            <FormLinkUpdateView isCustomDomain={isCustomDomain} link={isCustomDomain ? customDomainUrl : clientHostUrl} isDisable={!isProPlan && !isAdmin} isProUser={isProPlan} />
                        </div>
                    </FormSettingsCard>
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
                        {form?.settings?.provider === 'self' && (
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
                                                fullScreenModal.openModal('CREATE_CONSENT_FULL_MODAL_VIEW', {
                                                    form,
                                                    isPreview: true
                                                });
                                            }}
                                        >
                                            See Details
                                        </AppButton>
                                    </div>
                                    <hr className="h-0.5 w-full bg-black-200 my-2" />
                                </div>
                            </FormSettingsCard>
                        )}
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

    return <>{showSettingsTabView(view)}</>;
}

const FormGroups = ({ groups }: { groups: ResponderGroupDto[] }) => {
    const fullScreenModal = useFullScreenModal();

    return (
        <div className={'flex flex-col gap-0.5 mt-2'}>
            {groups.map((group: ResponderGroupDto) => {
                return (
                    <div key={group.id} className={'flex flex-row bg-black-200 px-6 py-[18px]'}>
                        <div className={'w-full md:w-[400px]'}>
                            <h1 className={'text-base font-semibold text-black-800'}>{group.name}</h1>
                            <p className={'text-sm font-normal text-black-700'}>{group.description}</p>
                        </div>
                    </div>
                );
            })}
            <div className={'mt-2'}>
                <AppButton onClick={() => fullScreenModal.openModal('SELECT_GROUP_FULL_MODAL_VIEW')} icon={<GroupIcon />} variant={ButtonVariant.Secondary}>
                    Add or Remove Group
                </AppButton>
            </div>
        </div>
    );
};
