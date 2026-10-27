"use client";
import { useEffect, useState } from 'react';

import { useModal } from '@app/components/modal-views/context';
import { formConstant } from '@app/constants/locales/form';
import { useIsMobile } from '@app/lib/hooks/use-breakpoint';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { Skeleton } from '@app/shadcn/components/ui/skeleton';
import { cn } from '@app/shadcn/util/lib';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { ownerProps } from '@app/utils/workspace-display-name';
import getFormShareURL from '@app/utils/form-utils';
import { DesktopIcon } from '@Components/icons/desktop-icon';
import { MobileIcon } from '@Components/icons/mobile-icon';
import TrustLayer from '@app/views/molecules/form/trust-layer';
import { layoutOfPage } from '@app/views/organism/layout/form-column';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import ShareIcon from '@Components/icons/share-icon';
import FloatingPopOverButton from '@Components/sidebar/floating-pop-over-button';
import HelpMenuComponent from '@Components/sidebar/help-menu-component';
import HelpMenuItem from '@Components/sidebar/help-menu-item';
import { useTranslation } from 'react-i18next';
import PublishButton from './publish-button';

const PreviewWrapper = ({ children, handleResetResponderState }: { children: React.ReactNode; handleResetResponderState: () => void }) => {
    const [key, setKey] = useState(1);
    const [isDesktopView, setIsDesktopView] = useState(true);
    const [isIframeLoaded, setIFrameLoaded] = useState(false);
    const { t } = useTranslation();
    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);
    const isMobile = useIsMobile();
    const { openModal } = useModal();
    const { currentSlide, endingId } = useResponderState();

    useEffect(() => {
        setIFrameLoaded(false);
    }, [isDesktopView]);

    const mobileViewPreviewUrl = `${window.PUBLIC_CONFIG?.HTTP_SCHEME}${window.PUBLIC_CONFIG?.FORM_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}/preview`;
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
                    <div onClick={() => setIsDesktopView(true)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'bg-black-200 text-black-800  rounded-lg' : 'text-black-600')}>
                        <DesktopIcon />
                        Desktop
                    </div>
                    <button data-umami-event={'Preview in Mobile View Button'}>
                        <div onClick={() => setIsDesktopView(false)} className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'text-black-600' : 'bg-black-200 text-black-800 rounded-lg p-2')}>
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
            <div className=" h-full lg:mx-10 lg:py-10 lg:pb-24 ">
                {isDesktopView ? (
                    <div className={`relative flex aspect-video max-w-full flex-col lg:mx-auto lg:max-h-full! ${isMobile ? 'h-preview-page' : 'h-screen'}`}>
                        <div className="relative min-h-0 flex-1">{children}</div>
                        {/* Preview must show exactly what responders will see —
                            including the trust strip, in flow below the form as
                            on the live page. Hiding it here would make the
                            drawer's "responders will see" promise a lie. */}
                        <div className="relative z-40 shrink-0">
                            <TrustLayer {...ownerProps(workspace)} ownerImage={workspace?.profileImage} settings={standardForm?.settings} layout={layoutOfPage(standardForm, currentSlide, endingId)} />
                        </div>
                    </div>
                ) : (
                    <div className="relative mx-auto aspect-9/16 h-full rounded-lg border border-black-300">
                        <iframe
                            onLoad={() => {
                                setIFrameLoaded(true);
                            }}
                            key={key.toString()}
                            className="absolute inset-0 aspect-9/16 h-full"
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
