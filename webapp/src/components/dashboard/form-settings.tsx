import React from 'react';

import {useTranslation} from 'next-i18next';

import Pro from '@Components/Common/Icons/Pro';
import LockIcon from '@Components/Common/Icons/lock';
import {Button, FormControlLabel, Radio, RadioGroup} from '@mui/material';
import Switch from '@mui/material/Switch';
import cn from 'classnames';
import {toast} from 'react-toastify';

import {useModal} from '@app/components/modal-views/context';
import {FormSettingsCard} from '@app/components/settings/card';
import environments from '@app/configs/environments';
import {buttonConstant} from '@app/constants/locales/button';
import {localesCommon} from '@app/constants/locales/common';
import {customize} from '@app/constants/locales/customize';
import {formConstant} from '@app/constants/locales/form';
import {toastMessage} from '@app/constants/locales/toast-message';
import {updateWorkspace} from '@app/constants/locales/update-workspace';
import {StandardFormDto} from '@app/models/dtos/form';
import {selectIsAdmin, selectIsProPlan} from '@app/store/auth/slice';
import {setFormSettings} from '@app/store/forms/slice';
import {useAppDispatch, useAppSelector} from '@app/store/hooks';
import {usePatchFormSettingsMutation} from '@app/store/workspaces/api';

import Globe from '../icons/flags/globe';
import {useFullScreenModal} from '../modal-views/full-screen-modal-context';
import FormLinkUpdateView from '../ui/form-link-update-view';
import AnchorLink from '../ui/links/anchor-link';
import UpgradeToPro from '../ui/upgrade-to-pro';

export default function FormSettingsTab() {
    const {t} = useTranslation();
    const form = useAppSelector((state) => state.form);
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const workspace = useAppSelector((state) => state.workspace);
    const dispatch = useAppDispatch();
    const {openModal} = useModal();
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
            toast(t(localesCommon.updated).toString(), {type: 'success'});
        } else {
            if (response.error.status === 409) {
                toast(t('TOAST.SLUG_ALREADY_EXISTS').toString(), {type: 'error'});
            } else {
                toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error'});
            }
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error', toastId: 'errorToast'});
        patchSettings({pinned: !f?.settings?.pinned}, f)
            .then((res) => {
            })
            .catch((e) => {
                toast(e.data, {type: 'error', toastId: 'errorToast'});
            });
    };

    const onPrivateChanged = ({isPrivate = false, f}: { isPrivate?: boolean; f?: StandardFormDto }) => {
        if (!f) return toast(t(toastMessage.formSettingUpdateError).toString(), {type: 'error', toastId: 'errorToast'});
        const patchBody = {private: isPrivate, pinned: false};
        patchSettings(patchBody, f)
            .then((res) => {
            })
            .catch((e: any) => {
                toast(e.data, {type: 'error', toastId: 'errorToast'});
            });
    };
    const isProPlan = useAppSelector(selectIsProPlan);
    const isAdmin = useAppSelector(selectIsAdmin);

    return (
        <div>
            {
                form?.settings?.isPublished && <>
                    <FormSettingsCard>
                        <p className="sh3">{t(formConstant.settings.formLink.title)}</p>
                        <p className="body4 !text-black-700 mt-4 !mb-6">{t(formConstant.settings.formLink.description)}</p>
                        <FormLinkUpdateView link={clientHostUrl} isLinkChangable/>
                    </FormSettingsCard>
                    <FormSettingsCard className={cn('relative !py-6', !isProPlan && isAdmin && '!bg-brand-200')}>
                        <p className="sh3">{t(formConstant.settings.customizeFormLink.title)}</p>
                        <p className="body4 !text-black-700 mt-4 mb-10">{t(formConstant.settings.customizeFormLink.description)}</p>
                        <p className="w-full body6 mb-4 !font-semibold text-black-900">{t(formConstant.settings.customizeFormLink.List.title)}</p>
                        <ul className="list-disc body4 ml-10 !mb-6">
                            <li className="mb-4">{t(formConstant.settings.customizeFormLink.List.point1)}</li>
                            <li>{t(formConstant.settings.customizeFormLink.List.point2)}</li>
                        </ul>
                        <FormLinkUpdateView link={isCustomDomain ? customDomainUrl : clientHostUrl}
                                            isDisable={!isProPlan && isAdmin}/>
                        {!isProPlan && isAdmin && <UpgradeToPro/>}
                    </FormSettingsCard>

                    <FormSettingsCard>
                        <p className="sh3">{t(formConstant.settings.visibility.title)}</p>
                        <RadioGroup className="flex flex-col gap-6"
                                    defaultValue={form?.settings?.private ? 'Private' : 'Public'}>
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onPrivateChanged({f: form})}
                                    value="Public"
                                    control={<Radio/>}
                                    label={
                                        <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                            <Globe className="h-[18px] w-[18px]"/>
                                            {t(formConstant.settings.visibility.public)}
                                        </div>
                                    }
                                />
                                <span
                                    className="ml-8 body4 !text-black-700">{t(formConstant.settings.visibility.description)}</span>
                            </div>
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onPrivateChanged({isPrivate: true, f: form})}
                                    value="Private"
                                    control={<Radio/>}
                                    label={
                                        <div className="flex body6 !text-black-800 items-center gap-[6px]">
                                            <LockIcon className="h-[18px] w-[18px]"/>
                                            {t(formConstant.settings.visibility.private)}
                                        </div>
                                    }
                                />
                                <span
                                    className="ml-8 body4 !text-black-700">{t(formConstant.settings.visibility.description)}</span>
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
                                <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned}
                                        onClick={(e) => onPinnedChange(e, form)}/>
                            </div>
                        </FormSettingsCard>
                    )}
                </>
            }

            <FormSettingsCard>
                <div className="flex items-center space-x-5">
                    <div className="space-y-2">
                        <div className="body1">Form Purpose and Data Usage</div>
                        <div
                            className="text-sm !text-black-700">{`This page is to help you to provide you with a clear understanding of how how your information is handled in our form. Our aim is to ensure you're fully informed and comfortable with how we handle your data.`}</div>
                    </div>
                    <span
                        className="h5-new !text-new-blue-500 w-60 cursor-pointer"
                        onClick={() => {
                            fullScreenModal.openModal('CREATE_CONSENT_FULL_MODAL_VIEW', {form, isPreview: true});
                        }}
                    >
                        See Details
                    </span>
                </div>
            </FormSettingsCard>
            <div className="my-6">
                <Button
                    style={{textTransform: 'none'}}
                    className="  bg-red-100 px-4 py-3 body6 rounded hover:bg-red-200 hover:drop-shadow-sm leading-none !text-red-500"
                    size="medium"
                    onClick={() => {
                        openModal('DELETE_FORM_MODAL', {form, redirectToDashboard: true});
                    }}
                >
                    {t(buttonConstant.deleteForm)}
                </Button>
            </div>
        </div>
    );
}
