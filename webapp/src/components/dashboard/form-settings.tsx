import React, { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import Tooltip from '@Components/Common/DataDisplay/Tooltip';
import EditIcon from '@Components/Common/Icons/Common/Edit';
import Pro from '@Components/Common/Icons/Dashboard/Pro';
import LockIcon from '@Components/Common/Icons/lock';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';
import { QrCode } from '@mui/icons-material';
import { FormControlLabel, Radio, RadioGroup } from '@mui/material';
import Switch from '@mui/material/Switch';
import cn from 'classnames';
import moment from 'moment/moment';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { Close } from '@app/components/icons/close';
import { GroupIcon } from '@app/components/icons/group-icon';
import { useModal } from '@app/components/modal-views/context';
import { FormSettingsCard } from '@app/components/settings/card';
import environments from '@app/configs/environments';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectIsAdmin } from '@app/store/auth/slice';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTIme } from '@app/utils/dateUtils';
import getFormShareURL from '@app/utils/formUtils';
import { validateFormOpen } from '@app/utils/validationUtils';

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
    const { openModal, closeModal } = useModal();
    const { openBottomSheetModal } = useBottomSheetModal();
    const fullScreenModal = useFullScreenModal();
    const isCustomDomain = workspace?.isPro && !!workspace.customDomain;
    const customUrl = form?.settings?.customUrl || '';
    const clientHost = `${environments.HTTP_SCHEME}${environments.CLIENT_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${environments.HTTP_SCHEME}${workspace.customDomain}/forms`;
    const V2FormDomain = `${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}`;

    const [_, copyToClipboard] = useCopyToClipboard();

    const handleOnCopy = () => {
        const link = getFormShareURL(form, workspace);
        copyToClipboard(link);
        toast(t(toastMessage.copied).toString(), {
            type: 'info'
        });
    };

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

    const onCollectEmailsChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ requireVerifiedIdentity: !f?.settings?.requireVerifiedIdentity }, f)
            .then()
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onShowSubmissionNumberChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ showSubmissionNumber: !f?.settings?.showSubmissionNumber }, f)
            .then()
            .catch((e) => {
                toast(e.data, { type: 'error', toastId: 'errorToast' });
            });
    };

    const onAllowResponseEditingChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ allowEditingResponse: !f?.settings?.allowEditingResponse }, f)
            .then()
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

    const onFormClosedChange = (date: moment.Moment | string) => {
        const patchBody = { formCloseDate: date };
        patchSettings(patchBody, form)
            .then(() => {})
            .catch(() => {
                toast('Something went wrong!!!', { type: 'error' });
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

    const closeFormChecked = !!form?.settings?.formCloseDate && moment.utc().isAfter(moment.utc(form?.settings?.formCloseDate));

    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);

    const closeForm = () => {
        onFormClosedChange(moment.utc());
        closeModal();
    };
    const reopenForm = () => {
        onFormClosedChange('');
        closeModal();
    };

    const showSettingsTabView = (view: FormSettingsTabView) => {
        switch (view) {
            case 'VISIBILITY':
                return (
                    <FormSettingsCard className={'mb-4'}>
                        <Divider />
                        <RadioGroup className="flex flex-col gap-6" value={currentVisibility}>
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onVisibilityChanged({ f: form })}
                                    value="Public"
                                    control={<Radio />}
                                    label={
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <Globe className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.public)}
                                        </div>
                                    }
                                />
                                <span className="body4 !text-black-700 ml-8">{t(formPage.visibilityPublic)}</span>
                            </div>
                            <Divider />
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => onVisibilityChanged({ isHidden: true, f: form })}
                                    value="Private"
                                    control={<Radio />}
                                    label={
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <LockIcon className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.private)}
                                        </div>
                                    }
                                />
                                <span className="body4 !text-black-700 ml-8">{t(formPage.visibilityPrivate)}</span>
                            </div>
                            <Divider />
                            <div className="flex flex-col">
                                <FormControlLabel
                                    onChange={() => patchSettings({ hidden: false, pinned: false, private: true }, form)}
                                    value="Group"
                                    control={<Radio />}
                                    label={
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <GroupIcon className="h-[18px] w-[18px]" />
                                            {t(formPage.visibilityGroupsTitle)}
                                        </div>
                                    }
                                />
                                <span className="body4 !text-black-700 ml-8">{!(form?.groups?.length === 0) ? t(formPage.visibilityGroups1) : t(formPage.visibilityGroups0)}</span>
                                {currentVisibility === 'Group' && <FormGroups groups={form?.groups || []} />}
                            </div>
                            <Divider />
                        </RadioGroup>
                    </FormSettingsCard>
                );
            case 'LINKS':
                const url = getFormShareURL(form, workspace);
                let parts = url.split('/');
                let lastPart = parts.pop();
                let firstPart = parts.join('/');
                return (
                    <FormSettingsCard className={'!mt-0 !space-y-0'}>
                        <p className="body4 !text-black-700 w-full lg:max-w-[564px]">{t(formPage.linksDescription)}</p>
                        <div className={'mt-1 flex flex-col items-start  gap-2 py-1 '}>
                            <Tooltip title={t('CLICK_TO_COPY')}>
                                <p className="body4 !text-black-700 max-w-full cursor-pointer truncate" onClick={handleOnCopy}>
                                    {firstPart}/ <span className="text-pink-500">{lastPart}</span>
                                </p>
                            </Tooltip>
                            <div className={'flex gap-8'}>
                                <AppButton
                                    className={'!py-0'}
                                    icon={<EditIcon className="h-4 w-4" />}
                                    onClick={() => {
                                        openBottomSheetModal('FORM_CREATE_SLUG_VIEW', {
                                            link: isCustomDomain ? customDomain : form?.builderVersion === 'v2' ? V2FormDomain : clientHost,
                                            customSlug: customUrl
                                        });
                                    }}
                                    variant={ButtonVariant.Ghost}
                                >
                                    {t(formPage.linksChangeSlug)}
                                </AppButton>
                                {environments.ENABLE_FORM_QR && !form?.settings?.hidden && (
                                    <AppButton
                                        className={'!py-0'}
                                        icon={<QrCode className="h-5 w-5" />}
                                        onClick={() => {
                                            openModal('GENERATE_QR');
                                        }}
                                        variant={ButtonVariant.Ghost}
                                    >
                                        Generate QR Code
                                    </AppButton>
                                )}
                            </div>
                        </div>
                        <div className="flex flex-col gap-16 pt-10">
                            {isCustomDomain && <FormLinkUpdateView isCustomDomain={isCustomDomain} link={getFormShareURL(form, workspace)} isProUser={!isAdmin || workspace?.isPro} isPrivate={form?.settings?.hidden} />}
                            <FormLinkUpdateView isCustomDomain={false} link={getFormShareURL(form, workspace, true)} isDisable={!isProPlan && !isAdmin} isProUser={!isAdmin || workspace?.isPro} isPrivate={form?.settings?.hidden} />
                        </div>
                    </FormSettingsCard>
                );
            case 'DEFAULT':
                return (
                    <div className=" mb-10 flex flex-col gap-7 ">
                        {environments.ENABLE_COLLECT_EMAILS && form?.settings?.provider === 'self' && (
                            <FormSettingsCard>
                                <div className=" flex w-full flex-col items-start">
                                    {/*<div className="h5-new !text-black-800">{t('FORM_PAGE.SETTINGS.DEFAULT.COLLECT_EMAILS.TITLE')}</div>*/}
                                    <div className="h5-new !text-black-800">Require Verified Identity</div>
                                    <Divider className={'my-2 w-full'} />
                                    <div className="flex w-full flex-row items-center justify-between md:gap-4">
                                        <div className="body4 !text-black-700 w-3/4 flex-1">If this is enabled the user needs to verify his email identity before filling this form</div>
                                        {/*<div className="body4 !text-black-700 w-3/4">{t('FORM_PAGE.SETTINGS.DEFAULT.COLLECT_EMAILS.DESCRIPTION')}</div>*/}
                                        <Switch
                                            data-testid="pinned-switch"
                                            checked={!!form?.settings?.requireVerifiedIdentity}
                                            onClick={(e) => {
                                                onCollectEmailsChange(e, form);
                                            }}
                                        />
                                    </div>
                                    <Divider className={'my-2 w-full'} />
                                </div>
                            </FormSettingsCard>
                        )}

                        {form?.settings?.provider === 'self' && (
                            <FormSettingsCard>
                                <div className=" flex w-full flex-col items-start">
                                    <div className="h5-new !text-black-800">Show Submission Number</div>
                                    <Divider className={'my-2 w-full'} />
                                    <div className="flex w-full flex-row items-center justify-between md:gap-4">
                                        <div className="body4 !text-black-700 w-3/4">When this is enabled the responder will br shown a submission ID which the user can use to view his response and also request for deletion of his response</div>
                                        <Switch
                                            data-testid="pinned-switch"
                                            checked={!!form?.settings?.showSubmissionNumber}
                                            onClick={(e) => {
                                                onShowSubmissionNumberChange(e, form);
                                            }}
                                        />
                                    </div>
                                    <Divider className={'my-2 w-full'} />
                                </div>
                            </FormSettingsCard>
                        )}

                        {environments.ENABLE_RESPONSE_EDITING && form?.settings?.provider === 'self' && form?.settings?.requireVerifiedIdentity && (
                            <FormSettingsCard>
                                <div className=" flex w-full flex-col items-start">
                                    <div className="h5-new !text-black-800">Allow Response Editing</div>
                                    <Divider className={'my-2 w-full'} />
                                    <div className="flex w-full flex-row items-center justify-between md:gap-4">
                                        <div className="body4 !text-black-700 w-3/4">The verified responder can change their response if this is enabled</div>
                                        <Switch
                                            data-testid="pinned-switch"
                                            checked={!!form?.settings?.allowEditingResponse}
                                            onClick={(e) => {
                                                onAllowResponseEditingChange(e, form);
                                            }}
                                        />
                                    </div>
                                    <Divider className={'my-2 w-full'} />
                                </div>
                            </FormSettingsCard>
                        )}
                        {form?.isPublished && isFormOpen && (
                            <>
                                {!form?.settings?.private && (
                                    <FormSettingsCard>
                                        <div className=" flex w-full flex-col items-start">
                                            <div className="h5-new !text-black-800">{t(formPage.pinFormTitle)}</div>
                                            <Divider className={'my-2 w-full'} />
                                            <div className="flex flex-row items-center justify-between md:gap-4">
                                                <div className="body4 !text-black-700 w-3/4">{t(formPage.pinFormDescription)}</div>
                                                <Switch data-testid="pinned-switch" checked={!!form?.settings?.pinned} onClick={(e) => onPinnedChange(e, form)} />
                                            </div>
                                            <Divider className={'my-2 w-full'} />
                                        </div>
                                    </FormSettingsCard>
                                )}
                                <FormSettingsCard className={cn('', !isProPlan && isAdmin && '')}>
                                    <div className=" flex w-full flex-col items-start">
                                        <div className="h5-new !text-black-800 flex flex-row justify-between gap-4">
                                            <h1>{t(formPage.brandingTitle)}</h1>
                                            <div className="sm:body5 bg-brand-500 flex h-5 items-center rounded p-1 text-[10px] !font-semibold uppercase !leading-none !text-white sm:h-6 sm:p-[6px]">
                                                <Pro width={12} height={12} />
                                                <span className="leading-none">{t(formPage.pro)}</span>
                                            </div>
                                        </div>
                                        <Divider className={'my-2 w-full'} />
                                        <div className="flex w-full flex-row items-center justify-between md:gap-4">
                                            <div className="body4 !text-black-700 w-3/4">{t(formPage.brandingDescription)}</div>
                                            <Switch disabled={!isProPlan} data-testid="disable-branding-switch" checked={!form?.settings?.disableBranding} onClick={(e) => onDisableBrandingChange(e, form)} />
                                        </div>
                                        <Divider className={'my-2 w-full'} />
                                    </div>
                                </FormSettingsCard>
                            </>
                        )}

                        {form?.settings?.provider === 'self' && (
                            <FormSettingsCard>
                                <div className="flex w-full flex-col items-start">
                                    <div className="body1">{t(formPage.formPurposeTitle)}</div>
                                    <Divider className={'my-2 w-full'} />
                                    <div className=" flex w-full flex-row items-center justify-between gap-4">
                                        <div className="!text-black-700 text-sm">{t(formPage.formPurposeDescription)}</div>
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
                                            {t(formPage.formPurposeSeeDetails)}
                                        </AppButton>
                                    </div>
                                    <Divider className={'my-2 w-full'} />
                                </div>
                            </FormSettingsCard>
                        )}
                        {form?.settings?.provider === 'self' && form?.isPublished && (
                            <FormSettingsCard>
                                <div className="flex w-full flex-col items-start">
                                    <div className="body1">{t(formPage.closeForm)}</div>
                                    <Divider className={'my-2 w-full'} />
                                    {(!form?.settings?.formCloseDate || moment.utc(form?.settings?.formCloseDate).isBefore(moment.utc())) && (
                                        <>
                                            <div className=" flex w-full flex-row items-center justify-between gap-4">
                                                <div className="!text-black-700 text-sm">{t(formPage.closeFormDescription)}</div>
                                                <Switch
                                                    data-testid="close-form-switch"
                                                    // checked={false}
                                                    checked={closeFormChecked}
                                                    onClick={(event) => {
                                                        if (closeFormChecked) {
                                                            openModal('REOPEN_FORM_CONFIRMATION_MODAL', { reopenForm });
                                                        } else {
                                                            openModal('CLOSE_FORM_CONFIRMATION_MODAL', { closeForm });
                                                        }
                                                    }}
                                                />
                                            </div>
                                            {!closeFormChecked && !moment(form?.settings?.formCloseDate).isAfter(moment.utc()) && (
                                                <AppButton
                                                    className="mt-2"
                                                    variant={ButtonVariant.Ghost}
                                                    onClick={() => {
                                                        openBottomSheetModal('SELECT_FORM_CLOSE_DATE', {
                                                            onFormClosedChange: onFormClosedChange,
                                                            closeDate: form?.settings?.formCloseDate
                                                        });
                                                    }}
                                                >
                                                    {t(formPage.schedule)}
                                                </AppButton>
                                            )}
                                        </>
                                    )}

                                    {form?.settings?.formCloseDate && moment(form?.settings?.formCloseDate).isAfter(moment.utc()) && (
                                        <div className="bg-black-200 my-2 flex w-full justify-between rounded-md p-5">
                                            <div>
                                                {t(formPage.automaticallyCloseOn)} {utcToLocalDateTIme(form?.settings?.formCloseDate)}
                                            </div>
                                            <div>
                                                <div onClick={reopenForm}>
                                                    <Close width="24px" height="24px" className="text-black-800" />
                                                </div>
                                            </div>
                                        </div>
                                    )}
                                    <Divider className={'my-2 w-full'} />
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
    const { openBottomSheetModal } = useBottomSheetModal();
    const { t } = useTranslation();

    return (
        <div className={'mt-2 flex flex-col gap-0.5'}>
            {groups.map((group: ResponderGroupDto) => {
                return (
                    <div key={group.id} className={'bg-black-200 flex flex-row px-6 py-[18px]'}>
                        <div className={'w-full md:w-[400px]'}>
                            <h1 className={'text-black-800 text-base font-semibold'}>{group.name}</h1>
                            <p className={'text-black-700 text-sm font-normal'}>{group.description}</p>
                        </div>
                    </div>
                );
            })}
            <div className={'mt-2'}>
                <AppButton onClick={() => openBottomSheetModal('SELECT_GROUP_FULL_MODAL_VIEW')} icon={<GroupIcon />} variant={ButtonVariant.Secondary}>
                    {t(formPage.visibilityAddOrRemove)}
                </AppButton>
            </div>
        </div>
    );
};
