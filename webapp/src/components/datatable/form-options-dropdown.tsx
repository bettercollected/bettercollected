"use client";
import Link from 'next/link';

import { Copy, Download, Eye, MoreVertical, Pencil, Pin, QrCode, Trash2 } from 'lucide-react';
import { useTranslation } from 'react-i18next';

import { LinkIcon } from '@app/components/icons/link-icon';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { formConstant } from '@app/constants/locales/form';
import { toastMessage } from '@app/constants/locales/toast-message';
import { toolTipConstant } from '@app/constants/locales/tooltip';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@app/shadcn/components/ui/dropdown-menu';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { setFormSettings } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';
import { useDuplicateFormMutation, useExportFormForOpenFormulierenMutation, usePatchFormSettingsMutation } from '@app/store/workspaces/api';
import { exportRefusalIsTooLarge, saveExport } from '@app/utils/open-formulieren-export';
import { useOpenFormulierenExportOn } from '@app/lib/hooks/use-open-formulieren-export-mode';
import getFormShareURL from '@app/utils/form-utils';
import { getEditFormURL } from '@app/utils/url-utils';
import { validateFormOpen } from '@app/utils/vvalidation-utils';
import { useWorkspacePermissions } from '@app/lib/hooks/use-workspace-permissions';
import { WorkspacePermission } from '@app/models/enums/workspace-permission';

interface IFormOptionsDropdownMenuProps {
    workspace: WorkspaceDto;
    form: StandardFormDto;
    hasCustomDomain: boolean;
    className?: string;
    redirectToDashboard?: boolean;
    showShare?: boolean;
    /** Shown in the form page's own header: it is already on the form, so "Open" and "Edit" (the header has an Edit button) are left out. */
    inHeader?: boolean;
}

export default function FormOptionsDropdownMenu({ workspace, form, hasCustomDomain, className = '', redirectToDashboard = false, showShare = false, inHeader = false }: IFormOptionsDropdownMenuProps) {
    const { openModal } = useModal();
    const { toast } = useToast();

    const { can } = useWorkspacePermissions();
    const canEdit = can(WorkspacePermission.FORM_EDIT);
    const canCreate = can(WorkspacePermission.FORM_CREATE);
    const canDelete = can(WorkspacePermission.FORM_DELETE);

    const [_, copyToClipboard] = useCopyToClipboard();

    const dispatch = useAppDispatch();
    const [patchFormSettings] = usePatchFormSettingsMutation();
    const [duplicateForm] = useDuplicateFormMutation();
    const [exportForOpenFormulieren] = useExportFormForOpenFormulierenMutation();
    const { on: openFormulierenExportOn } = useOpenFormulierenExportOn();
    const { t } = useTranslation();

    const isCustomDomain = !!workspace.customDomain;
    const isMobile = useIsMobile();

    const clientHost = `${window.PUBLIC_CONFIG?.FORM_DOMAIN.includes('localhost') ? 'http' : 'https'}://${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}/forms`;
    const customDomain = `${window.PUBLIC_CONFIG?.FORM_DOMAIN.includes('localhost') ? 'http' : 'https'}://${workspace.customDomain}/forms`;

    const isFormOpen = validateFormOpen(form?.settings?.formCloseDate);

    const patchSettings = async (body: any, f: StandardFormDto) => {
        const response: any = await patchFormSettings({
            workspaceId: workspace.id,
            formId: f.formId,
            body: body
        });
        if (response.data) {
            const settings = response.data.settings;
            dispatch(setFormSettings(settings));
        } else {
            toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
            return response.error;
        }
    };

    const onPinnedChange = (f?: StandardFormDto) => {
        if (!f) return toast({ description: t(toastMessage.formSettingUpdateError).toString(), variant: 'destructive' });
        patchSettings({ pinned: !f?.settings?.pinned }, f)
            .then((res) => { })
            .catch((e) => {
                toast({ description: e.data, variant: 'destructive' });
            });
    };

    const handleDuplicateFrom = () => {
        duplicateForm({ workspaceId: workspace.id, formId: form.formId })
            .then()
            .catch((e: any) => {
                toast({ description: t(formConstant.menu.duplicateError).toString(), variant: 'destructive' });
            });
    };

    // The form as an Open Formulieren import archive (only when the instance
    // offers it); the toast tells how many things the archive's README lists.
    const handleOpenFormulierenExport = () => {
        exportForOpenFormulieren({ workspaceId: workspace.id, formId: form.formId })
            .unwrap()
            .then((result) => {
                saveExport(result);
                toast({ description: result.unmapped ? t(formConstant.menu.openFormulierenExportUnmapped, { count: result.unmapped }).toString() : t(formConstant.menu.openFormulierenExportClean).toString() });
            })
            .catch((error) => toast({ description: t(exportRefusalIsTooLarge(error) ? formConstant.menu.openFormulierenExportTooLarge : formConstant.menu.openFormulierenExportError).toString(), variant: 'destructive' }));
    };

    // Pinning needs a public form; the item then says why it is off.
    const pinOff = !!form?.settings?.private || !!form?.settings?.hidden;
    const canShare = form?.isPublished && !form?.settings?.hidden && isFormOpen;

    return (
        <DropdownMenu>
            <DropdownMenuTrigger asChild>
                <button
                    type="button"
                    data-testid="form-menu-trigger"
                    aria-label={form?.title ? t(localesCommon.moreActionsFor, { name: form.title }) : t(localesCommon.moreActions)}
                    className={`${className} text-black-900! cursor-pointer rounded-md p-2 hover:bg-gray-100`}
                    // Call sites sit inside clickable cards and rows: opening the menu must not also open them.
                    onClick={(e) => {
                        e.stopPropagation();
                        e.preventDefault();
                    }}
                >
                    <MoreVertical className="h-4 w-4" aria-hidden="true" />
                </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent className="w-[256px] bg-white p-0" align="end" onClick={(e) => e.stopPropagation()}>
                {canEdit && form?.isPublished && isFormOpen && (
                    <Item icon={<Pin width={20} height={20} />} disabled={pinOff} hint={pinOff ? t(toolTipConstant.visibility) : undefined} onSelect={() => onPinnedChange(form)}>
                        {form?.settings?.pinned ? t(formConstant.unPinForm) : t(formConstant.menu.pinForm)}
                    </Item>
                )}
                {!inHeader && (
                    <LinkItem icon={<Eye width={20} height={20} />} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                        {t(buttonConstant.open)}
                    </LinkItem>
                )}
                {!inHeader && canEdit && form?.settings?.provider === 'self' && form?.builderVersion === 'v2' && !isMobile && (
                    <LinkItem icon={<Pencil width={20} height={20} />} href={getEditFormURL(workspace, form)}>
                        {t(buttonConstant.edit)}
                    </LinkItem>
                )}
                {canShare && (
                    <Item
                        icon={<LinkIcon width={20} height={20} />}
                        onSelect={() => {
                            const shareUrl = getFormShareURL(form, workspace);
                            if (shareUrl) {
                                copyToClipboard(shareUrl);
                                toast({ description: t(toastMessage.formUrlCopied).toString() });
                            }
                        }}
                    >
                        {t(buttonConstant.copyLink)}
                    </Item>
                )}
                {canEdit && canShare && (
                    <Item icon={<Pencil width={20} height={20} />} onSelect={() => openModal('CUSTOMIZE_URL', { url: isCustomDomain ? customDomain : clientHost, form: form })}>
                        {t(buttonConstant.customizeLink)}
                    </Item>
                )}
                {canShare && (
                    <Item icon={<QrCode size={20} />} onSelect={() => openModal('GENERATE_QR', { form })}>
                        {t(formConstant.menu.generateQr)}
                    </Item>
                )}
                {canCreate && form?.settings?.provider === 'self' && (
                    <Item icon={<Copy width={20} height={20} />} onSelect={handleDuplicateFrom}>
                        {t(formConstant.menu.duplicateForm)}
                    </Item>
                )}
                {openFormulierenExportOn && form?.settings?.provider === 'self' && (
                    <Item icon={<Download width={20} height={20} />} onSelect={handleOpenFormulierenExport}>
                        {t(formConstant.menu.openFormulierenExport)}
                    </Item>
                )}
                {canDelete && (
                    <Item icon={<Trash2 width={20} height={20} />} onSelect={() => openModal('DELETE_FORM_MODAL', { form, redirectToDashboard })}>
                        {t(formConstant.menu.deleteForm)}
                    </Item>
                )}
            </DropdownMenuContent>
        </DropdownMenu>
    );
}

const ITEM = 'hover:bg-brand-100 focus:bg-brand-100 body4 flex min-h-[36px] cursor-pointer items-center gap-2 rounded-none px-[20px] py-[10px]';

/** A menu item that acts (a real menu item: arrow keys, Enter and Space, closes the menu); `hint` is why it is off. */
function Item({ icon, children, onSelect, disabled, hint }: { icon: React.ReactNode; children: React.ReactNode; onSelect: () => void; disabled?: boolean; hint?: string }) {
    return (
        <DropdownMenuItem className={ITEM} disabled={disabled} onSelect={onSelect}>
            <span className="text-black-600 flex shrink-0 items-center justify-center" aria-hidden="true">
                {icon}
            </span>
            <span className="flex flex-col">
                <span>{children}</span>
                {hint && <span className="text-black-600 text-xs">{hint}</span>}
            </span>
        </DropdownMenuItem>
    );
}

/** A menu item that goes somewhere: a real link, so it also opens in a new tab. */
function LinkItem({ icon, children, href }: { icon: React.ReactNode; children: React.ReactNode; href: string }) {
    return (
        <DropdownMenuItem asChild className={ITEM}>
            <Link href={href}>
                <span className="text-black-600 flex shrink-0 items-center justify-center" aria-hidden="true">
                    {icon}
                </span>
                {children}
            </Link>
        </DropdownMenuItem>
    );
}
