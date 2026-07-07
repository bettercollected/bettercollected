import { formConstant } from '@app/constants/locales/form';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/form-utils';
import BackButton from '@app/views/molecules/form-builder/back-button';
import PublishButton from '@app/views/molecules/form-builder/publish-button';
import Form from '@app/views/organism/form/form';
import ShareIcon from '@Components/icons/share-icon';
import { useTranslation } from 'next-i18next';
import { useModal } from '../context';
import { useFullScreenModal } from '../full-screen-modal-context';

/**
 * Full-screen form preview. One quiet header names what this is (Preview),
 * states the honest fact (answers aren't saved), and offers the next step
 * (Share / Publish). The stage letterboxes the form to a 16:9 card that fits
 * BOTH viewport dimensions on desktop — the old modal opened with a "use the
 * desktop version to edit" banner (this is a preview, on any device) above an
 * empty nav strip, and its `aspect-video h-full` stage clipped off the bottom
 * of the screen.
 */
export const PreviewFullModalView = () => {
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useModal();
    const { resetResponderState } = useResponderState();
    const { resetFormResponseAnswer } = useFormResponse();
    const { closeModal } = useFullScreenModal();
    const isMobile = useIsMobile();

    const handleClickClose = () => {
        resetResponderState();
        resetFormResponseAnswer();
        closeModal();
    };

    return (
        <div className="flex h-screen w-full flex-col bg-[#F6F8FC]">
            <header className="border-black-300 z-10 flex h-14 w-full shrink-0 items-center justify-between gap-2 border-b bg-white px-4">
                <BackButton handleClick={handleClickClose} />
                <div className="flex min-w-0 items-center gap-2 text-sm">
                    <span className="text-black-800 max-w-[200px] truncate font-medium sm:max-w-[320px]">{standardForm?.title || 'Untitled'}</span>
                    <span className="rounded-full bg-[#E9EFFC] px-2 py-0.5 text-xs font-semibold text-[#2456CC]">Preview</span>
                    <span className="text-black-600 hidden text-xs md:inline">Answers aren&apos;t saved</span>
                </div>
                <div className="flex items-center gap-2">
                    {standardForm?.isPublished ? (
                        <Button
                            variant="v2Button"
                            icon={<ShareIcon className="h-4 w-4" />}
                            disabled={standardForm?.settings?.hidden}
                            onClick={() =>
                                openModal('SHARE_VIEW', {
                                    url: getFormShareURL(standardForm, workspace),
                                    title: t(formConstant.shareThisForm)
                                })
                            }
                        >
                            <span className="hidden text-xs font-medium sm:inline">Share</span>
                        </Button>
                    ) : (
                        <PublishButton refresh />
                    )}
                </div>
            </header>
            {/* Mobile fills the screen (that IS the responder experience);
                desktop letterboxes a 16:9 card whose width is capped so the
                derived height also fits: min(full width, available-height ×
                16/9). 104px = 56px header + 48px stage padding. */}
            <div className="flex min-h-0 w-full flex-1 items-center justify-center lg:p-6">
                <div className="border-black-300 relative h-full w-full overflow-hidden bg-white lg:aspect-video lg:h-auto lg:w-[min(100%,calc((100vh-104px)*16/9))] lg:rounded-lg lg:border lg:shadow-lg">
                    <Form isPreviewMode showDesktopLayout={!isMobile} />
                </div>
            </div>
        </div>
    );
};
