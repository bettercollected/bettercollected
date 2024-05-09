import { useEffect, useState } from 'react';

import { useModal } from '@app/components/modal-views/context';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';
import { DesktopIcon } from '@app/views/atoms/Icons/DesktopIcon';
import { MobileIcon } from '@app/views/atoms/Icons/MobileIcon';
import { useTranslation } from 'next-i18next';
import PublishButton from './PublishButton';
import ShareIcon from '@app/views/atoms/Icons/ShareIcon';
import { useDialogModal } from '@app/lib/hooks/useDialogModal';

const PreviewWrapper = ({ children, handleResetResponderState }: { children: React.ReactNode; handleResetResponderState: () => void }) => {
    const [key, setKey] = useState(1);
    const [isDesktopView, setIsDesktopView] = useState(true);
    const [isIframeLoaded, setIFrameLoaded] = useState(false);
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const isMobile = useIsMobile();
    const { openDialogModal } = useDialogModal();
    const { openModal } = useModal();

    useEffect(() => {
        setIFrameLoaded(false);
    }, [isDesktopView]);

    const mobileViewPreviewUrl = `${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}/preview`;
    return (
        <div className=" h-full w-full bg-white">
            {isMobile && (
                <div className="bg-black-900 xs:px-16 flex h-[52px] w-full items-center justify-center px-4 py-2">
                    <span className="text-sm text-white">Please use the desktop version to edit this form. Mobile editing will be available soon!</span>
                </div>
            )}
            <nav className="flex h-14 flex-row justify-between px-4 py-2" style={{ background: isMobile ? standardForm.theme?.accent : 'inherit' }}>
                <div></div>
                <div className=" hidden items-center gap-4 text-xs font-semibold lg:flex">
                    <div onClick={() => setIsDesktopView(true)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'bg-black-200 text-black-800  rounded-lg' : 'text-black-500')}>
                        <DesktopIcon />
                        Desktop
                    </div>
                    <div onClick={() => setIsDesktopView(false)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'text-black-500' : 'bg-black-200 text-black-800 rounded-lg p-2')}>
                        <MobileIcon />
                        Mobile
                    </div>
                </div>
                <div className=" hidden gap-2 lg:flex">
                    <Button
                        variant={'v2Button'}
                        onClick={() => {
                            setKey(key + 1);
                            handleResetResponderState();
                            setIFrameLoaded(false);
                        }}
                    >
                        Restart
                    </Button>
                    <PublishButton />
                </div>
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
            <div className=" h-full drop-shadow-xl lg:mx-10 lg:py-10 lg:pb-24 ">
                {isDesktopView ? (
                    <div className={`aspect-video max-w-full lg:mx-auto lg:!max-h-full ${isMobile ? 'h-preview-page' : 'h-screen'}`}>{children}</div>
                ) : (
                    <div className="relative mx-auto aspect-[9/16] h-full rounded-lg drop-shadow-xl">
                        <iframe
                            onLoad={() => {
                                setIFrameLoaded(true);
                            }}
                            key={key.toString()}
                            className="absolute inset-0 aspect-[9/16] h-full"
                            title="responder-mobile-view"
                            src={mobileViewPreviewUrl}
                        />
                        {!isIframeLoaded && <Skeleton className="absolute inset-0 h-full pb-10" />}
                    </div>
                )}
            </div>
        </div>
    );
};

export default PreviewWrapper;
