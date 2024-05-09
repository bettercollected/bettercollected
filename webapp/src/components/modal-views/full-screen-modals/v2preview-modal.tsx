import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import BackButton from '@app/views/molecules/FormBuilder/BackButton';
import PreviewWrapper from '@app/views/molecules/FormBuilder/PreviewWrapper';
import Form from '@app/views/organism/Form/Form';
import { useFullScreenModal } from '../full-screen-modal-context';
import { Separator } from '@app/shadcn/components/ui/separator';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import ShareIcon from '@app/views/atoms/Icons/ShareIcon';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';
import { useModal } from '../context';
import getFormShareURL from '@app/utils/formUtils';
import { useTranslation } from 'next-i18next';
import { formConstant } from '@app/constants/locales/form';

export const PreviewFullModalView = () => {
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openDialogModal } = useDialogModal();
    const { openModal } = useModal();
    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const handleResetResponderState = () => {
        resetResponderState();
        resetFormResponseAnswer();
    };
    const { closeModal } = useFullScreenModal();
    const isMobile = useIsMobile();

    return (
        <div className="relative h-full w-full">
            <div className="absolute left-4 top-16 z-50 " onClick={closeModal}>
                <BackButton hideForSmallScreen />
            </div>
            <div className=" h-full w-full bg-white">
                <div className="bg-black-900 xs:px-16 flex h-[52px] w-full items-center justify-center px-4 py-2">
                    <span className="text-sm text-white">Please use the desktop version to edit this form. Mobile editing will be available soon!</span>
                </div>
                <nav className="flex h-14 flex-row justify-between px-4 py-2" style={{ background: isMobile ? standardForm.theme?.accent : 'inherit' }}>
                    <div></div>
                    <div className="flex gap-2 lg:hidden">
                        <Button
                            variant={'primary'}
                            icon={<ShareIcon className="h-4 w-4" />}
                            className=""
                            disabled={standardForm?.settings?.hidden}
                            onClick={() =>
                                openModal('SHARE_VIEW', {
                                    url: getFormShareURL(standardForm, workspace),
                                    title: t(formConstant.shareThisForm)
                                })
                            }
                        >
                            <span className="text-xs font-medium">Share</span>
                        </Button>
                    </div>
                </nav>
                <Separator />
                <div className="  drop-shadow-xl lg:mx-10 lg:py-10 lg:pb-24 ">
                    <div className={`h-preview-page aspect-video max-w-full`}>
                        <Form isPreviewMode />
                    </div>
                </div>
            </div>
        </div>
    );
};
