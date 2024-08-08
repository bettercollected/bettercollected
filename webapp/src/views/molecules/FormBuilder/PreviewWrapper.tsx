import { useEffect, useState } from 'react';

import { useModal } from '@app/Components/modal-views/context';
import environments from '@app/configs/environments';
import { formConstant } from '@app/constants/locales/form';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { selectWorkspace } from '@app/store/workspaces/slice';
import getFormShareURL from '@app/utils/formUtils';
import { DesktopIcon } from '@app/views/atoms/Icons/DesktopIcon';
import { MobileIcon } from '@app/views/atoms/Icons/MobileIcon';
import ShareIcon from '@app/views/atoms/Icons/ShareIcon';
import { useTranslation } from 'next-i18next';
import PublishButton from './PublishButton';
import { useAuthAtom } from '@app/store/jotai/auth';
import FloatingPopOverButton from '@app/Components/sidebar/FloatingPopOverButton';
import HelpMenuItem from '@app/Components/sidebar/HelpMenuItem';
import HelpMenuComponent from '@app/Components/sidebar/HelpMenuComponent';

const PreviewWrapper = ({ children, handleResetResponderState }: { children: React.ReactNode; handleResetResponderState: () => void }) => {
    const [key, setKey] = useState(1);
    const [isDesktopView, setIsDesktopView] = useState(true);
    const [isIframeLoaded, setIFrameLoaded] = useState(false);
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const isMobile = useIsMobile();
    const { openModal } = useModal();
    const { setResponderState, responderState } = useResponderState();
    const { authState } = useAuthAtom();

    useEffect(() => {
        setIFrameLoaded(false);
    }, [isDesktopView]);

    const mobileViewPreviewUrl = `${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}/preview`;
    return (
        <div className=" h-screen w-full bg-white">
            {isMobile && (
                <div className="bg-black-900 xs:px-16 flex h-[52px] w-full items-center justify-center px-4 py-2">
                    <span className="text-xs text-white sm:text-sm">Please use the desktop version to edit this form. Mobile editing will be available soon!</span>
                </div>
            )}
            <nav className="flex h-14 flex-row justify-between px-4 py-2" style={{ background: isMobile ? standardForm.theme?.accent : 'inherit' }}>
                <div></div>
                <div className=" hidden items-center gap-4 text-xs font-semibold lg:flex">
                    <div onClick={() => setIsDesktopView(true)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'bg-black-200 text-black-800  rounded-lg' : 'text-black-500')}>
                        <DesktopIcon />
                        Desktop
                    </div>
                    <button data-umami-event={'Preview in Mobile View Button'} data-umami-event-email={authState.email}>
                        <div onClick={() => setIsDesktopView(false)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'text-black-500' : 'bg-black-200 text-black-800 rounded-lg p-2')}>
                            <MobileIcon />
                            Mobile
                        </div>
                    </button>
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
                    <div className={`flex aspect-video max-w-full flex-col gap-2 lg:mx-auto lg:!max-h-full ${isMobile ? 'h-preview-page' : 'h-screen'}`}>
                        {/* <div className="flex justify-center gap-4">
                            {standardForm.fields.map((_, index: number) => (
                                <span
                                    key={index}
                                    onClick={() => setResponderState({ ...responderState, currentSlide: index, currentField: 0 })}
                                    className="cursor-pointer rounded px-4 py-1 text-white active:brightness-90"
                                    style={{ background: standardForm.theme?.secondary }}
                                >
                                    {index + 1}
                                </span>
                            ))}
                        </div> */}
                        {children}
                    </div>
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
            <FloatingPopOverButton content={<HelpMenuComponent />}>
                <HelpMenuItem />
            </FloatingPopOverButton>
        </div>
    );
};

export default PreviewWrapper;
