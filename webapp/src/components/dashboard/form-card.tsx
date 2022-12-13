import React, { useState } from 'react';

import EmptyTray from '@app/assets/svgs/empty-tray.svg';
import { ShareIcon } from '@app/components/icons/share-icon';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import Loader from '@app/components/ui/loader';
import MuiSnackbar from '@app/components/ui/mui-snackbar';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { useGetWorkspaceFormsQuery } from '@app/store/workspaces/api';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IFormCard {
    workspaceId: string;
}

export default function FormCard({ workspaceId }: IFormCard) {
    const [isOpen, setIsOpen] = useState(false);
    const [_, copyToClipboard] = useCopyToClipboard();
    const { isLoading, data, isError } = useGetWorkspaceFormsQuery(workspaceId, { pollingInterval: 30000, refetchOnReconnect: true, refetchOnFocus: true, refetchOnMountOrArgChange: true });

    if (isLoading)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Loader />
            </div>
        );

    if ((data?.payload?.content && Array.isArray(data?.payload?.content) && data?.payload?.content?.length === 0) || isError)
        return (
            <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                <p className="mt-4 p-0">0 forms</p>
            </div>
        );

    const forms: Array<StandardFormDto> = data?.payload?.content ?? [];

    return (
        <div className="pt-3 md:pt-7">
            {forms.length === 0 && (
                <div className="w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey">
                    <Image src={EmptyTray} width={40} height={40} alt="Empty Tray" />
                    <p className="mt-4 p-0">0 forms</p>
                </div>
            )}
            <div className="grid grid-cols-1 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                {forms.length !== 0 &&
                    forms.map((form: StandardFormDto) => {
                        const slug = form.settings.customUrl;
                        let shareUrl = '';
                        if (window && typeof window !== 'undefined') {
                            shareUrl = `${window.location.origin}/forms/${slug}`;
                        }
                        return (
                            <ActiveLink
                                key={form.formId}
                                href={{
                                    pathname: `/forms/[slug]`,
                                    query: { slug }
                                }}
                            >
                                <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                                    <div className="flex flex-col justify-start h-full">
                                        <p className="text-xl text-grey mb-4 p-0">{form.title}</p>
                                        {form?.description && <p className="text-base text-softBlue m-0 p-0 w-full">{toEndDottedStr(form.description, 180)}</p>}
                                    </div>
                                    <div
                                        aria-hidden
                                        onClick={(event) => {
                                            event.preventDefault();
                                            event.stopPropagation();
                                            copyToClipboard(shareUrl);
                                            setIsOpen(true);
                                        }}
                                        className="p-2 border-[1px] border-white hover:border-neutral-100 hover:shadow rounded-md"
                                    >
                                        <ShareIcon width={19} height={19} />
                                    </div>
                                </div>
                            </ActiveLink>
                        );
                    })}
            </div>
            <MuiSnackbar isOpen={isOpen} setIsOpen={setIsOpen} message="Copied URL" severity="info" />
        </div>
    );
}
