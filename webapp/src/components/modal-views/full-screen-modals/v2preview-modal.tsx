import { formConstant } from '@app/constants/locales/form';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';
import ShareIcon from '@app/views/atoms/Icons/ShareIcon';
import BackButton from '@app/views/molecules/FormBuilder/BackButton';
import Form from '@app/views/organism/Form/Form';
import { useTranslation } from 'next-i18next';
import { useModal } from '../context';
import { useFullScreenModal } from '../full-screen-modal-context';

export const PreviewFullModalView = () => {
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const handleClickClose = () => {
        resetResponderState();
        resetFormResponseAnswer();
        closeModal();
    };
    const { closeModal } = useFullScreenModal();
    const isMobile = useIsMobile();

    return (
        <div className="relative h-screen w-full">
            <div className="absolute left-4 top-16 z-50 " onClick={handleClickClose}>
                <BackButton hideForSmallScreen />
            </div>
            <div className=" h-full w-full bg-white">
                <div className="bg-black-900 xs:px-16 flex h-[52px] w-full items-center justify-center px-1 py-2">
                    <span className="text-center text-xs text-white sm:text-sm">Please use the desktop version to edit this form. Mobile editing will be available soon!</span>
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
                <div className="h-full  drop-shadow-xl lg:mx-10 lg:py-10 lg:pb-24 ">
                    <div className={`aspect-video h-full max-w-full`}>
                        <Form isPreviewMode />
                    </div>
                </div>
            </div>
        </div>
    );
};
