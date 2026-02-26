import { useEffect, useRef, useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import cn from 'classnames';

import { useToast } from '@app/shadcn/components/ui/use-toast';

import Image from '@app/components/ui/image';
import { buttonConstant } from '@app/constants/locales/button';
import { toastMessage } from '@app/constants/locales/toast-message';
import { useAppDispatch } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { setWorkspace } from '@app/store/workspaces/slice';

export default function BannerImageComponent(props: { workspace: any; isFormCreator: boolean; className?: string }) {
    const { workspace, isFormCreator, className } = props;
    const { toast } = useToast();
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const [image, setImage] = useState('');
    const selectedFile = useRef<File | null>(null);
    const imageInputRef = useRef<HTMLInputElement>(null);
    const { t } = useTranslation();

    const dispatch = useAppDispatch();

    useEffect(() => {
        return () => {
            if (image) {
                URL.revokeObjectURL(image);
            }
        };
    }, [image]);

    const onUploadFileChange = (e: any) => {
        if (!e.target.files.length) return;
        const file = e.target.files[0];
        selectedFile.current = file;
        if (image) {
            URL.revokeObjectURL(image);
        }
        setImage(URL.createObjectURL(file));
    };

    const onClickFileUploadButton = () => {
        if (!!imageInputRef.current) {
            imageInputRef.current.click();
        }
    };

    const onClickCancelButton = () => {
        setImage('');
        selectedFile.current = null;
    };

    const onClickFileSaveButton = async () => {
        if (!selectedFile.current) return;

        const formData = new FormData();
        formData.append('banner_image', selectedFile.current);
        const response: any = await patchExistingWorkspace({ workspace_id: workspace.id, body: formData });
        if (response.error) {
            toast({ description: response.error.data || t(toastMessage.somethingWentWrong).toString(), variant: 'destructive' });
        }
        if (response.data) {
            toast({ description: t(toastMessage.workspaceUpdate).toString() });
            setImage('');
            selectedFile.current = null;
            dispatch(setWorkspace(response.data));
        }
    };

    const getUpdateOptionsClassName = () => {
        if (!image && !workspace.bannerImage) {
            return '';
        }
        return '!block';
    };

    return (
        <div className={cn('relative w-full bannerdiv rounded-t-xl overflow-hidden max-w-[540px] md:max-w-[320px]  aspect-banner', className)}>
            {!!image ? (
                <img style={{ width: '100%', height: '100%', objectFit: 'cover' }} src={image} alt="test" />
            ) : (
                <>
                    {!!workspace.bannerImage ? (
                        // codeql[js/xss-through-dom]: False positive - src is always a safe blob: URL from createObjectURL
                        <Image src={workspace?.bannerImage ?? ''} priority layout="fill" objectFit="cover" objectPosition="center" alt={workspace?.title} />
                    ) : (
                        <div className="bg-new-black-200 hover:bg-new-black-300 h-full align-center cursor-pointer flex flex-col items-center justify-center" onClick={onClickFileUploadButton}>
                            <div className="p2-new ml-10 !text-black-700">Add banner image</div>
                        </div>
                    )}
                    <input ref={imageInputRef} data-testid="file-upload" type="file" accept="image/*" className="hidden" onClick={(event: any) => (event.target.value = null)} onChange={onUploadFileChange} />
                </>
            )}
            {isFormCreator && (
                <UpdateImageOptions
                    t={t}
                    getUpdateOptionsClassName={getUpdateOptionsClassName}
                    isLoading={isLoading}
                    onClickFileUploadButton={onClickFileUploadButton}
                    onClickFileSaveButton={onClickFileSaveButton}
                    image={image}
                    onCLickCancelButton={onClickCancelButton}
                />
            )}
        </div>
    );
}

function UpdateImageOptions({ getUpdateOptionsClassName, isLoading, onClickFileUploadButton, onClickFileSaveButton, image, onCLickCancelButton, t }: any) {
    return (
        <div className={`absolute bottom-2 right-2 hidden ${getUpdateOptionsClassName()}`}>
            <div className="flex justify-between">
                {!isLoading && !image && <Button onClick={onClickFileUploadButton}>{t(buttonConstant.update)}</Button>}
                {!isLoading && image && (
                    <Button className="!text-white flex !bg-black-600 hover:!bg-black-700 mr-2" onClick={onCLickCancelButton}>
                        {t(buttonConstant.cancel)}
                    </Button>
                )}
                {!!image && (
                    <>
                        <Button isLoading={isLoading} onClick={onClickFileSaveButton}>
                            {isLoading ? t(buttonConstant.saving) : t(buttonConstant.save)}
                        </Button>
                    </>
                )}
            </div>
        </div>
    );
}
