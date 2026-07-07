"use client";
import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';


import { Button } from '@app/shadcn/components/ui/button';
import { Label } from '@app/shadcn/components/ui/label';
import { RadioGroup, RadioGroupItem } from '@app/shadcn/components/ui/radio-group';
import { Switch } from '@app/shadcn/components/ui/switch';
import Tooltip from '@app/shadcn/components/ui/tooltip';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import Divider from '@Components/common/divider';
import cn from 'classnames';
import { Lock, Pencil, QrCode } from 'lucide-react';
import moment from 'moment/moment';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

import { Close } from '@app/components/icons/close';
import Globe from "@app/components/icons/flags/globe";
import { GroupIcon } from '@app/components/icons/group-icon';
import { useModal } from '@app/components/modal-views/context';
import { useFullScreenModal } from "@app/components/modal-views/full-screen-modal-context";
import { FormSettingsCard } from '@app/components/settings/card';
import FormLinkUpdateView from "@app/components/ui/form-link-update-view";
import { ProLogo } from "@app/components/ui/logo";
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { formPage } from '@app/constants/locales/form-page';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { selectAuth, selectIsAdmin } from '@app/store/auth/slice';
import { selectForm, setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { utcToLocalDateTIme } from '@app/utils/date-utils';
import getFormShareURL from '@app/utils/form-utils';
import { validateFormOpen } from '@app/utils/vvalidation-utils';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';

interface IFormSettingsTabProps {
    view?: FormSettingsTabView;
}

type FormSettingsTabView = 'VISIBILITY' | 'LINKS' | 'DEFAULT';

export default function FormSettingsTab({ view = 'DEFAULT' }: IFormSettingsTabProps) {
    const { toast } = useToast();
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
    const clientHost = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${workspace.customDomain}/forms`;
    const V2FormDomain = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}/forms`;

    const [_, copyToClipboard] = useCopyToClipboard();

    const handleOnCopy = () => {
        const link = getFormShareURL(form, workspace);
        copyToClipboard(link);
        toast({ description: t(toastMessage.copied).toString() });
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
            toast({ description: t(localesCommon.updated).toString() });
        } else {
            if (response.error.status === 409) {
                toast({ description: t('TOAST.SLUG_ALREADY_EXISTS').toString(), variant: 'destructive' });
            } else {
                toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
            }
            return response.error;
        }
    };

    const onPinnedChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => { })
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const onCollectEmailsChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ requireVerifiedIdentity: !f?.settings?.requireVerifiedIdentity }, f)
            .then()
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const onShowOriginalFormChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ showOriginalForm: !f?.settings?.showOriginalForm }, f);
    };

    const onShowSubmissionNumberChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ showSubmissionNumber: !f?.settings?.showSubmissionNumber }, f)
            .then()
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const onAllowResponseEditingChange = (event: any, f: StandardFormDto = form) => {
        patchSettings({ allowEditingResponse: !f?.settings?.allowEditingResponse }, f)
            .then()
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
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
                return toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
            const patchBody = { private: isPrivate, pinned: false, hidden: isHidden };
            patchSettings(patchBody, f)
                .then((res) => { })
                .catch((e: any) => {
                    toast({ description: e.data, variant: 'destructive' });
                });
        };
        openModal('VISIBILITY_CONFIRMATION_MODAL_VIEW', { visibilityType: visibilityType(), handleOnConfirm });
    };

    const onFormClosedChange = (date: moment.Moment | string) => {
        const patchBody = { formCloseDate: date };
        patchSettings(patchBody, form)
            .then(() => { })
            .catch(() => {
                toast({ description: 'Something went wrong!!!', variant: 'destructive' });
            });
    };

    const onDisableBrandingChange = (event: any, f?: StandardFormDto) => {
        if (!f) return toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
        patchSettings({ disableBranding: !f?.settings?.disableBranding }, f)
            .then((res) => { })
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const isProPlan = useAppSelector(selectWorkspace).isPro;
    const isAdmin = useAppSelector(selectIsAdmin);
    const auth = useAppSelector(selectAuth);

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
                        <RadioGroup className="flex flex-col gap-6" value={currentVisibility} onValueChange={(val) => {
                            if (val === 'Public') onVisibilityChanged({ f: form });
                            if (val === 'Private') onVisibilityChanged({ isHidden: true, f: form });
                            if (val === 'Group') patchSettings({ hidden: false, pinned: false, private: true }, form);
                        }}>
                            <div className="flex flex-col">
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="Public" id="public" />
                                    <Label htmlFor="public" className="cursor-pointer">
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <Globe className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.public)}
                                        </div>
                                    </Label>
                                </div>
                                <span className="body4 !text-black-700 ml-6 mt-1">{t(formPage.visibilityPublic)}</span>
                            </div>
                            <Divider />
                            <div className="flex flex-col">
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="Private" id="private" />
                                    <Label htmlFor="private" className="cursor-pointer">
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <Lock className="h-[18px] w-[18px]" />
                                            {t(formConstant.settings.visibility.private)}
                                        </div>
                                    </Label>
                                </div>
                                <span className="body4 !text-black-700 ml-6 mt-1">{t(formPage.visibilityPrivate)}</span>
                            </div>
                            <Divider />
                            <div className="flex flex-col">
                                <div className="flex items-center space-x-2">
                                    <RadioGroupItem value="Group" id="group" />
                                    <Label htmlFor="group" className="cursor-pointer">
                                        <div className="body6 !text-black-800 flex items-center gap-[6px]">
                                            <GroupIcon className="h-[18px] w-[18px]" />
                                            {t(formPage.visibilityGroupsTitle)}
                                        </div>
                                    </Label>
                                </div>
                                <span className="body4 !text-black-700 ml-6 mt-1">{!(form?.groups?.length === 0) ? t(formPage.visibilityGroups1) : t(formPage.visibilityGroups0)}</span>
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
                            <Tooltip label={t('CLICK_TO_COPY')}>
                                <p className="body4 !text-black-700 max-w-full cursor-pointer truncate" onClick={handleOnCopy}>
                                    {firstPart}/ <span className="text-pink-500">{lastPart}</span>
                                </p>
                            </Tooltip>
                            <div className={'flex gap-8'}>
                                <Button
                                    data-umami-event="Customize Form Link Button"
                                    data-umami-event-email={auth.email}
                                    className={'!py-0'}
                                    icon={<Pencil className="h-4 w-4" />}
                                    onClick={() => {
                                        openBottomSheetModal('FORM_CREATE_SLUG_VIEW', {
                                            link: isCustomDomain ? customDomain : form?.builderVersion === 'v2' ? V2FormDomain : clientHost,
                                            customSlug: customUrl
                                        });
                                    }}
                                    variant="ghost"
                                >
                                    {t(formPage.linksChangeSlug)}
                                </Button>
                                {!form?.settings?.hidden && (
                                    <Button
                                        data-umami-event="Generate QR button"
                                        data-umami-event-email={auth.email}
                                        className={'!py-0'}
                                        icon={<QrCode className="h-5 w-5" />}
                                        onClick={() => {
                                            openModal('GENERATE_QR');
                                        }}
                                        variant="ghost"
                                    >
                                        Generate QR Code
                                    </Button>
                                )}
                            </div>
                        </div>
                        <div className="flex flex-col gap-16 pt-10">
                            <FormLinkUpdateView isCustomDomain={false} link={getFormShareURL(form, workspace, true)} isDisable={!isProPlan && !isAdmin} isProUser={!isAdmin || workspace?.isPro} isPrivate={form?.settings?.hidden} />
                            {isCustomDomain && <FormLinkUpdateView isCustomDomain={isCustomDomain} link={getFormShareURL(form, workspace)} isProUser={!isAdmin || workspace?.isPro} isPrivate={form?.settings?.hidden} />}
                        </div>
                    </FormSettingsCard>
                );
            case 'DEFAULT':
                return (
                    <div className="divide-black-200 flex flex-col divide-y">
                        {form?.importedFormId && (
                            <SettingRow title="Show original form" description="Show the original Google Form in embed mode instead of the bettercollected renderer.">
                                <Switch
                                    data-umami-event="Show Original Google Form Switch"
                                    data-umami-event-email={auth.email}
                                    data-testid="show-original-form-switch"
                                    checked={!!form?.settings?.showOriginalForm}
                                    onCheckedChange={(checked) => {
                                        onShowOriginalFormChange(checked, form);
                                    }}
                                />
                            </SettingRow>
                        )}
                        {form?.settings?.provider === 'self' && (
                            <SettingRow title="Require verified identity" description="Respondents must verify their email before they can fill out this form.">
                                <Switch
                                    data-umami-event="Require Verified Identity Switch"
                                    data-umami-event-email={auth.email}
                                    data-testid="require-verified-identity-switch"
                                    checked={!!form?.settings?.requireVerifiedIdentity}
                                    onCheckedChange={(checked) => {
                                        onCollectEmailsChange(checked, form);
                                    }}
                                />
                            </SettingRow>
                        )}
                        {form?.settings?.provider === 'self' && (
                            <SettingRow title="Show submission number" description="Respondents get a submission ID they can use to view their response and request its deletion.">
                                <Switch
                                    data-umami-event="Show Submission Number Switch"
                                    data-umami-event-email={auth.email}
                                    data-testid="show-submission-number-switch"
                                    checked={!!form?.settings?.showSubmissionNumber}
                                    onCheckedChange={(checked) => {
                                        onShowSubmissionNumberChange(checked, form);
                                    }}
                                />
                            </SettingRow>
                        )}
                        {form?.settings?.provider === 'self' && form?.settings?.requireVerifiedIdentity && (
                            <SettingRow title="Allow response editing" description="Verified responders can change their response after submitting.">
                                <Switch
                                    data-umami-event="Allow Response Editing Switch"
                                    data-umami-event-email={auth.email}
                                    data-testid="allow-response-editing-switch"
                                    checked={!!form?.settings?.allowEditingResponse}
                                    onCheckedChange={(checked) => {
                                        onAllowResponseEditingChange(checked, form);
                                    }}
                                />
                            </SettingRow>
                        )}
                        {form?.isPublished && isFormOpen && (
                            <>
                                {!form?.settings?.private && (
                                    <SettingRow title={t(formPage.pinFormTitle)} description={t(formPage.pinFormDescription)}>
                                        <Switch data-umami-event="Pin Form Switch" data-umami-event-email={auth.email} data-testid="pinned-switch" checked={!!form?.settings?.pinned} onCheckedChange={(checked) => onPinnedChange(checked, form)} />
                                    </SettingRow>
                                )}
                                <SettingRow
                                    title={t(formPage.brandingTitle)}
                                    titleExtra={<ProLogo />}
                                    description={t(formPage.brandingDescription)}
                                    hint={
                                        !isProPlan ? (
                                            <span className="text-black-600 flex items-center gap-1 text-xs">
                                                <Lock className="h-3 w-3" /> Available on Pro — the control is locked on your current plan.
                                            </span>
                                        ) : undefined
                                    }
                                >
                                    <Switch
                                        disabled={!isProPlan}
                                        data-umami-event="Disable Branding Switch"
                                        data-umami-event-email={auth.email}
                                        data-testid="disable-branding-switch"
                                        checked={!form?.settings?.disableBranding}
                                        onCheckedChange={(checked) => onDisableBrandingChange(checked, form)}
                                    />
                                </SettingRow>
                            </>
                        )}
                        {form?.settings?.provider === 'self' && form?.isPublished && (
                            <div className="flex w-full flex-col">
                                <SettingRow title={t(formPage.closeForm)} description={t(formPage.closeFormDescription)}>
                                    <Switch
                                        data-umami-event="Close Form Switch"
                                        data-umami-event-email={auth.email}
                                        data-testid="close-form-switch"
                                        checked={closeFormChecked}
                                        onCheckedChange={(checked) => {
                                            if (closeFormChecked) {
                                                openModal('REOPEN_FORM_CONFIRMATION_MODAL', { reopenForm });
                                            } else {
                                                openModal('CLOSE_FORM_CONFIRMATION_MODAL', { closeForm });
                                            }
                                        }}
                                    />
                                </SettingRow>
                                {!closeFormChecked && !moment(form?.settings?.formCloseDate).isAfter(moment.utc()) && (
                                    <Button
                                        data-umami-event="Select Form Close Date Button"
                                        data-umami-event-email={auth.email}
                                        className="mb-4 w-fit"
                                        variant="ghost"
                                        onClick={() => {
                                            openBottomSheetModal('SELECT_FORM_CLOSE_DATE', {
                                                onFormClosedChange: onFormClosedChange,
                                                closeDate: form?.settings?.formCloseDate
                                            });
                                        }}
                                    >
                                        {t(formPage.schedule)}
                                    </Button>
                                )}
                                {form?.settings?.formCloseDate && moment(form?.settings?.formCloseDate).isAfter(moment.utc()) && (
                                    <div className="bg-black-200 mb-4 flex w-full justify-between rounded-md p-5">
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
                            </div>
                        )}
                    </div>
                );
            default:
                return <></>;
        }
    };

    return <>{showSettingsTabView(view)}</>;
}

/**
 * One settings row: label + description on the left, control on the right.
 * Rows are separated by the parent's divide-y — a divider never cuts a
 * setting in half (the old layout drew the hairline between a setting's
 * label and its own control).
 */
export const SettingRow = ({ title, titleExtra, description, children, hint }: { title: React.ReactNode; titleExtra?: React.ReactNode; description: React.ReactNode; children: React.ReactNode; hint?: React.ReactNode }) => (
    <div className="flex w-full items-start justify-between gap-6 py-5">
        <div className="flex max-w-[560px] flex-col gap-1">
            <div className="text-black-900 flex items-center gap-2 text-[15px] font-semibold">
                {title}
                {titleExtra}
            </div>
            <div className="text-black-700 text-sm leading-relaxed">{description}</div>
            {hint}
        </div>
        <div className="pt-1">{children}</div>
    </div>
);

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
                <Button onClick={() => openBottomSheetModal('SELECT_GROUP_FULL_MODAL_VIEW')} icon={<GroupIcon />} variant="secondary">
                    {t(formPage.visibilityAddOrRemove)}
                </Button>
            </div>
        </div>
    );
};
