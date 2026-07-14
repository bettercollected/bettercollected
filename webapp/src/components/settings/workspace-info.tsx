import { ChangeEvent, FormEvent, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import UploadLogo from '@Components/common/upload-logo';

import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { WorkspaceDto } from '@app/models/dtos/workspace-dto';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { selectAuth } from '@app/store/auth/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useWorkspaceSettingsView } from '@app/store/jotai/workspace-settings-view';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import { useBottomSheetModal } from '@Components/modals/contexts/bottom-sheet-modal-context';

export default function WorkspaceInfo({ workspace }: { workspace: WorkspaceDto }) {
    const dispatch = useAppDispatch();
    const { t } = useTranslation();
    const { toast } = useToast();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const { closeBottomSheetModal } = useBottomSheetModal();
    const { setSettingsViewOpen } = useWorkspaceSettingsView();

    // Settings render in two containers (the Public Workspace frame and the
    // deep-link bottom sheet); saving closes whichever is open.
    const closeSettings = () => {
        closeBottomSheetModal();
        setSettingsViewOpen(false);
    };
    // Controlled inputs need strings — privacyPolicy/termsOfService are null
    // until set, and React errors on value={null}.
    const currentInfo = {
        title: workspace.title || '',
        description: workspace.description || '',
        privacy_policy: workspace.privacyPolicy || '',
        terms_of_service: workspace.termsOfService || ''
    };
    const [workspaceInfo, setWorkspaceInfo] = useState(currentInfo);
    const [urlErrors, setUrlErrors] = useState<{ privacy_policy?: string; terms_of_service?: string }>({});
    const auth = useAppSelector(selectAuth);

    const onChange = (e: ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => {
        if (e.target.name === 'description') {
            if (e.target.value.length >= 280) return;
            setWorkspaceInfo({ ...workspaceInfo, description: e.target.value });
        } else {
            if (e.target.name in urlErrors) setUrlErrors({ ...urlErrors, [e.target.name]: undefined });
            setWorkspaceInfo({ ...workspaceInfo, [e.target.name]: e.target.value });
        }
    };

    // These values render as links on the public workspace and in every form's
    // trust footer, so they must be real http(s) URLs — anything else (typos,
    // javascript: schemes) is rejected. A missing scheme is forgiven by
    // prepending https:// rather than bouncing the save.
    const normalizeUrl = (value: string): string | null => {
        const trimmed = value.trim();
        if (!trimmed) return '';
        // The URL constructor happily percent-encodes inner whitespace, which
        // would wave through paste accidents like "https://x.com/terms oops".
        if (/\s/.test(trimmed)) return null;
        const candidate = /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(trimmed) ? trimmed : `https://${trimmed}`;
        try {
            const url = new URL(candidate);
            if (url.protocol !== 'https:' && url.protocol !== 'http:') return null;
            if (!url.hostname.includes('.')) return null;
            return candidate;
        } catch {
            return null;
        }
    };

    const onSubmit = async (event: FormEvent<HTMLFormElement>) => {
        event.preventDefault();

        const urlFields = ['privacy_policy', 'terms_of_service'] as const;
        const normalized = { ...workspaceInfo };
        const errors: typeof urlErrors = {};
        urlFields.forEach((field) => {
            const result = normalizeUrl(workspaceInfo[field]);
            if (result === null) {
                errors[field] = 'Enter a full link, like https://yoursite.com/privacy';
            } else {
                normalized[field] = result;
            }
        });
        if (Object.values(errors).some(Boolean)) {
            setUrlErrors(errors);
            return;
        }
        if (normalized.privacy_policy !== workspaceInfo.privacy_policy || normalized.terms_of_service !== workspaceInfo.terms_of_service) {
            setWorkspaceInfo(normalized);
        }

        const formData = new FormData();
        // Diff against the normalised current values — the old check read
        // workspace['privacy_policy'] (snake_case) off a camelCase DTO, so
        // those fields were sent on every save whether changed or not.
        const changedKeys = (Object.keys(normalized) as Array<keyof typeof normalized>).filter((key) => normalized[key] !== currentInfo[key]);
        if (changedKeys.length === 0) {
            closeSettings();
            return;
        }
        changedKeys.forEach((key) => formData.append(key, normalized[key]));
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });

        if (response.error) {
            toast({ description: response.error.data || t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
        if (response.data) {
            dispatch(setWorkspace(response.data));
            closeSettings();
            toast({ description: t(toastMessage.workspaceUpdate).toString() });
        }
    };

    const onProfileImageUpload = async (file: File) => {
        const updateProfileImageFormData = new FormData();
        updateProfileImageFormData.append('profile_image', file);

        const response: any = await patchExistingWorkspace({
            workspace_id: workspace?.id,
            body: updateProfileImageFormData
        });

        if (response.error) {
            toast({
                description: response.error?.data || t(toastMessage.somethingWentWrong),
                variant: 'destructive'
            });
        }

        if (response.data) {
            dispatch(setWorkspace(response.data));
        }
    };

    return (
        <form onSubmit={onSubmit} className="flex w-full max-w-[540px] flex-col items-start justify-center gap-6 pb-10">
            <div className="relative -top-9 pl-6">
                <UploadLogo onUpload={onProfileImageUpload} logoImageUrl={workspace.profileImage} showRemove={false} dropdownTopPosition={80} />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.TITLE')}</div>
                <AppInput className="w-full" onChange={onChange} value={workspaceInfo.title} name="title" placeholder={t(placeHolder.workspaceTitle)} />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">{t('WORKSPACE.SETTINGS.DETAILS.DESCRIPTION')}</div>
                <Textarea
                    className="border-black-300 focus:shadow-input rounded focus:!border-[#B8E8FF] focus:outline-transparent focus:ring-transparent resize-none"
                    rows={3}
                    onChange={onChange}
                    value={workspaceInfo.description}
                    name="description"
                    placeholder={t(placeHolder.description)}
                />
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">Privacy Policy URL</div>
                <AppInput className={`w-full ${urlErrors.privacy_policy ? '!border-[#C43D3D]' : ''}`} onChange={onChange} value={workspaceInfo.privacy_policy} name="privacy_policy" placeholder={'https://yoursite.com/privacy'} />
                {urlErrors.privacy_policy && <div className="text-xs text-[#C43D3D]">{urlErrors.privacy_policy}</div>}
                <div className="p4-new text-black-600">Linked from your site and from the trust footer on every form — it tells responders how their data is used.</div>
            </div>
            <div className="flex w-full flex-col gap-2">
                <div className="body1">Terms of Service URL</div>
                <AppInput className={`w-full ${urlErrors.terms_of_service ? '!border-[#C43D3D]' : ''}`} onChange={onChange} value={workspaceInfo.terms_of_service} name="terms_of_service" placeholder={'https://yoursite.com/terms'} />
                {urlErrors.terms_of_service && <div className="text-xs text-[#C43D3D]">{urlErrors.terms_of_service}</div>}
                <div className="p4-new text-black-600">Shown alongside the privacy policy on your site.</div>
            </div>

            <Button
                data-umami-event="Update Workspace Info From Workspace Settings"
                data-umami-event-email={auth.email}
                className="mt-4 w-full"
                type="submit"
                size="medium"
                variant="primary"
                disabled={!workspaceInfo.title}
                isLoading={isLoading}
            >
                {t('BUTTON.SAVE_CHANGES')}
            </Button>
        </form>
    );
}
