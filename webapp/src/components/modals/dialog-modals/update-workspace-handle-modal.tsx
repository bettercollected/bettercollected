"use client";
import { useEffect, useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import HeaderModalWrapper from '@Components/modals/modal-wrapper/header-modal-wrapper';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';

import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { onBoarding } from '@app/constants/locales/onboarding-screen';
import { toastMessage } from '@app/constants/locales/toast-message';
import { updateWorkspace } from '@app/constants/locales/update-workspace';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { checkErrorForWorkspaceName, checkIfPredefinedWorkspaceName } from '@app/utils/workspace-utils';
import { useBottomSheetModal } from '../contexts/bottom-sheet-modal-context';

export default function UpdateWorkspaceHandle() {
    const { toast } = useToast();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

    const { closeModal } = useModal();
    const { t } = useTranslation();
    const router = useRouter();

    const { openBottomSheetModal } = useBottomSheetModal();

    const workspace = useAppSelector(selectWorkspace);
    const [updateText, setUpdateText] = useState(workspace.workspaceName);

    const [error, setError] = useState(false);
    const [errorMessage, setErrorMessage] = useState('');
    const handleUpdateChange = (event: any) => {
        setUpdateText(event.target.value.toLowerCase());
    };

    useEffect(() => {
        if (checkErrorForWorkspaceName(updateText)) {
            if (!updateText) {
                setErrorMessage(t(onBoarding.fillHandleName));
            } else if (updateText.includes(' ')) {
                setErrorMessage(t(onBoarding.spaceNotAllowed));
            } else if (!updateText.match(/^(?![_-])(?!.*[_-]{2})[a-zA-Z0-9_-]+(?![_-])$/)) {
                setErrorMessage(t(onBoarding.allowedCharacters));
            } else if (checkIfPredefinedWorkspaceName(updateText)) {
                setErrorMessage('It is predefined name. Please use another one.');
            }
            setError(true);
        } else {
            setError(false);
        }
    }, [updateText]);

    const handleSubmit = async (e: any) => {
        e.preventDefault();
        if (error || !updateText) return;
        if (updateText === workspace.workspaceName) {
            closeModal();
            return;
        }
        const formData = new FormData();
        formData.append('workspace_name', updateText);
        const body = {
            workspace_id: workspace.id,
            body: formData
        };
        const response: any = await patchExistingWorkspace(body);
        if (response.data) {
            // dispatch(setWorkspace(response.data));
            toast({ description: t(updateWorkspace.handle).toString() });
            router.replace(`/${response.data.workspaceName}/dashboard`);
            openBottomSheetModal('WORKSPACE_SETTINGS', { initialIndex: 1 });
            closeModal();
        } else if (response.error) {
            toast({ description: response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), variant: 'destructive' });
        }
    };
    return (
        <HeaderModalWrapper headerTitle="Update Workspace handle">
            <form className="flex flex-col gap-2" onSubmit={handleSubmit}>
                <div className="h4-new">Enter Slug</div>
                <div className="p2-new text-black-700">Avoid using spaces or special characters. Only “-” and “_” is accepted.</div>
                <div className="p2-new">
                    {window.PUBLIC_CONFIG?.HTTP_SCHEME}
                    {window.PUBLIC_CONFIG?.FORM_DOMAIN}/<span className="p2-new text-pink">{updateText}</span>
                </div>
                <AppInput value={updateText} onChange={handleUpdateChange} />
                {errorMessage && <span className={'text-sm text-red-500 font-normal'}>{errorMessage}</span>}
                {error && <span className={'text-sm text-red-500 font-normal'}>{errorMessage}</span>}
                <Button className="w-full mt-2" disabled={error || isLoading} data-testid="save-button" type="submit" >
                    {t(buttonConstant.updateNow)}
                </Button>
            </form>
        </HeaderModalWrapper>
    );
}
