import { useRef, useState } from 'react';

import { useTranslation } from 'react-i18next';

import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';
import AuthAccountProfileImage from '../auth/account-profile-image';


export default function ProfileImageComponent(props: { workspace: any; isFormCreator?: boolean; size?: number; className?: string }) {
    const { workspace, isFormCreator, size } = props;
    const { t } = useTranslation();
    const { toast } = useToast();
    const [uploadImage, setUploadImage] = useState(workspace.profileImage);
    const [selectedFile, setSelectedFile] = useState<File | null>(null);
    const profileInputRef = useRef<HTMLInputElement>(null);
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const dispatch = useAppDispatch();

    const onUploadFileChange = (e: any) => {
        if (!!e.target.files.length) {
            const file = e.target.files[0];
            setSelectedFile(file);
            setUploadImage(URL.createObjectURL(file));
        }
    };

    const onClickSaveButton = async () => {
        if (!selectedFile) return;

        const formData = new FormData();
        formData.append('profile_image', selectedFile);

        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast({ description: t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
        if (response.data) {
            toast({ description: t(toastMessage.workspaceUpdate).toString() });

            dispatch(setWorkspace(response.data));
            setUploadImage(response.data.profileImage);
            setSelectedFile(null);
            // await router.push(router.asPath, undefined);
        }
    };

    const onClickCancelButton = () => {
        setUploadImage(workspace.profileImage);
        setSelectedFile(null);
    };

    return (
        <div className={props?.className ?? ''}>
            <div className="flex flex-col items-center">
                <div
                    onClick={() => {
                        if (isFormCreator) {
                            profileInputRef.current?.click();
                        }
                    }}
                    className={`w-min ${isFormCreator ? 'cursor-pointer' : ''} `}
                >
                    <AuthAccountProfileImage image={uploadImage} name={workspace.title} size={size ? size : 163} typography="h2" />
                    <input data-testid="file-upload-profile" type="file" accept="image/*" ref={profileInputRef} className="hidden" onClick={(event: any) => (event.target.value = null)} onChange={onUploadFileChange} />
                </div>
                {selectedFile && isFormCreator && (
                    <div className="flex justify-between mt-2">
                        <Button className="!text-white flex !bg-black-600 hover:!bg-black-700 mr-2" onClick={onClickCancelButton}>
                            {t(buttonConstant.cancel)}
                        </Button>
                        <Button isLoading={isLoading} onClick={onClickSaveButton}>
                            {isLoading ? t(buttonConstant.saving) : t(buttonConstant.save)}
                        </Button>
                    </div>
                )}
            </div>
        </div>
    );
}