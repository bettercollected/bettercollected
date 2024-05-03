import {useEffect, useState} from 'react';

import environments from '@app/configs/environments';
import {Button} from '@app/shadcn/components/ui/button';
import {Separator} from '@app/shadcn/components/ui/separator';
import {cn} from '@app/shadcn/util/lib';
import {selectForm} from '@app/store/forms/slice';
import {useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';
import {DesktopIcon} from '@app/views/atoms/Icons/DesktopIcon';
import {MobileIcon} from '@app/views/atoms/Icons/MobileIcon';
import PublishButton from './PublishButton';
import {Skeleton} from '@app/shadcn/components/ui/skeleton';

const PreviewWrapper = ({children, handleResetResponderState}: {
    children: React.ReactNode;
    handleResetResponderState: () => void
}) => {
    const [key, setKey] = useState(1);
    const [isDesktopView, setIsDesktopView] = useState(true);
    const [isIframeLoaded, setIFrameLoaded] = useState(false);

    const standardForm = useAppSelector(selectForm);
    const workspace = useAppSelector(selectWorkspace);

    useEffect(() => {
        setIFrameLoaded(false);
    }, [isDesktopView]);

   

    const mobileViewPreviewUrl = `${environments.HTTP_SCHEME}${environments.FORM_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}/preview`;
    return (
        <div className=" h-full w-full bg-white">
            <nav className="flex h-14 flex-row justify-between px-4 py-2">
                <div></div>
                <div className="flex items-center gap-4 text-xs font-semibold">
                    <div onClick={() => setIsDesktopView(true)}
                         className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'bg-black-200 text-black-800  rounded-lg' : 'text-black-500')}>
                        <DesktopIcon/>
                        Desktop
                    </div>
                    <div onClick={() => setIsDesktopView(false)}
                         className={cn('flex cursor-pointer items-center gap-1 p-2 text-xs', isDesktopView ? 'text-black-500' : 'bg-black-200 text-black-800 rounded-lg p-2')}>
                        <MobileIcon/>
                        Mobile
                    </div>
                </div>
                <div className="flex gap-2">
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
                    <PublishButton/>
                </div>
            </nav>
            <Separator/>
            <div className=" mx-10 h-full py-10 pb-24 drop-shadow-xl ">
                {isDesktopView ? (
                    <div className="mx-auto aspect-video !max-h-full !max-w-full">{children}</div>
                ) : (
                    <div
                        className="mx-auto relative aspect-[9/16] h-full rounded-lg drop-shadow-xl"
                    >
                        <iframe
                            onLoad={() => {
                                setIFrameLoaded(true);
                            }}
                            key={key.toString()}
                            className="absolute inset-0 aspect-[9/16] h-full"
                            title="responder-mobile-view"
                            src={mobileViewPreviewUrl}
                        />
                        {!isIframeLoaded &&
                            <Skeleton className="absolute inset-0 pb-10 h-full"/>}

                    </div>
                )}

            </div>
        </div>
    );
};

export default PreviewWrapper;
