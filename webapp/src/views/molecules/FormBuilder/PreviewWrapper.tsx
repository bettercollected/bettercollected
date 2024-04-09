import { useState } from 'react';

import environments from '@app/configs/environments';
import { Button } from '@app/shadcn/components/ui/button';
import { Separator } from '@app/shadcn/components/ui/separator';
import { cn } from '@app/shadcn/util/lib';
import { useStandardForm } from '@app/store/jotai/fetchedForm';
import useWorkspace from '@app/store/jotai/workspace';
import { DesktopIcon } from '@app/views/atoms/Icons/DesktopIcon';
import { MobileIcon } from '@app/views/atoms/Icons/MobileIcon';

const PreviewWrapper = ({
    children,
    handleResetResponderState
}: {
    children: React.ReactNode;
    handleResetResponderState: () => void;
}) => {
    const [key, setKey] = useState(1);
    const [isDesktopView, setIsDesktopView] = useState(true);
    const { standardForm } = useStandardForm();
    const { workspace } = useWorkspace();

    const mobileViewPreviewUrl = `${environments.NEXT_PUBLIC_HTTP_SCHEME}://${environments.NEXT_PUBLIC_V2_CLIENT_ENDPOINT_DOMAIN}/${workspace.workspaceName}/forms/${standardForm.formId}?isPreview=true`;
    return (
        <div className=" h-full w-full bg-white">
            <nav className="flex h-14 flex-row justify-between px-4 py-2">
                <div></div>
                <div className="flex items-center gap-4 text-xs font-semibold">
                    <div
                        onClick={() => setIsDesktopView(true)}
                        className={cn(
                            'flex cursor-pointer items-center gap-1 p-2 text-xs',
                            isDesktopView
                                ? 'rounded-lg bg-black-200  text-black-800'
                                : 'text-black-500'
                        )}
                    >
                        <DesktopIcon />
                        Desktop
                    </div>
                    <div
                        onClick={() => setIsDesktopView(false)}
                        className={cn(
                            'flex cursor-pointer items-center gap-1 p-2 text-xs',
                            isDesktopView
                                ? 'text-black-500'
                                : 'rounded-lg bg-black-200 p-2 text-black-800'
                        )}
                    >
                        <MobileIcon />
                        Mobile
                    </div>
                </div>
                <Button
                    variant={'v2Button'}
                    onClick={() => {
                        setKey(key + 1);
                        handleResetResponderState();
                    }}
                >
                    Restart
                </Button>
            </nav>
            <Separator />
            <div className=" mx-10 h-full py-10 pb-24 drop-shadow-xl  ">
                {isDesktopView ? (
                    <div className="mx-auto aspect-video !max-h-full !max-w-full">
                        {children}
                    </div>
                ) : (
                    <iframe
                        key={key.toString()}
                        title="responder-mobile-view"
                        className="mx-auto aspect-[9/20] h-full rounded-lg drop-shadow-xl"
                        src={mobileViewPreviewUrl}
                    />
                )}
            </div>
        </div>
    );
};

export default PreviewWrapper;
