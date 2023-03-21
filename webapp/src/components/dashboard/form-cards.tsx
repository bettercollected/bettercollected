import React from 'react';

import { toast } from 'react-toastify';

import FormsCard from '@app/components/cards/form-card';
import FormsContainer from '@app/components/cards/form-container';
import { Google } from '@app/components/icons/brands/google';
import { ShareIcon } from '@app/components/icons/share-icon';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface FormCardsProps {
    title: string;
    formsArray: Array<StandardFormDto>;
    workspace: WorkspaceDto;
}

const FormCards = ({ title, formsArray, workspace }: FormCardsProps) => {
    const isCustomDomain = window?.location.host !== environments.CLIENT_HOST;

    const breakpoint = useBreakpoint();

    const [_, copyToClipboard] = useCopyToClipboard();

    if (formsArray.length === 0) return <></>;
    return (
        <div data-testid="form-cards-container" className="mb-6">
            {!!title && <h1 className=" text-gray-700 font-semibold text-md md:text-lg mb-4">{title}</h1>}
            <FormsContainer>
                {formsArray.map((form: StandardFormDto) => {
                    const slug = form.settings?.customUrl;
                    let shareUrl = '';
                    if (window && typeof window !== 'undefined') {
                        shareUrl = isCustomDomain ? `${window.location.origin}/forms/${slug}` : `${window.location.origin}/${workspace.workspaceName}/forms/${slug}`;
                    }
                    return (
                        <ActiveLink
                            key={form.formId}
                            href={{
                                pathname: isCustomDomain ? `/forms/${slug}` : `${workspace.workspaceName}/forms/${slug}`,
                                query: { back: true }
                            }}
                        >
                            <FormsCard>
                                <div className="flex flex-col justify-start h-full">
                                    <div className="flex mb-4 w-full items-center space-x-4">
                                        <div>
                                            {form?.settings?.provider === 'typeform' ? (
                                                <div className="rounded-full border h-[24px] w-[28px] border-white relative">
                                                    <Image src="/tf.png" className="rounded-full" layout="fill" alt={'T'} />
                                                </div>
                                            ) : (
                                                <div className="rounded-full bg-white p-1">
                                                    <Google />
                                                </div>
                                            )}
                                        </div>
                                        <p className="text-xl text-grey  p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title, 15) : toEndDottedStr(form?.title || 'Untitled', 30)}</p>
                                    </div>
                                    {form?.description && (
                                        <p className="text-base text-softBlue m-0 p-0 w-full">
                                            {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                        </p>
                                    )}

                                    {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
                                </div>

                                <div
                                    aria-hidden
                                    onClick={(event) => {
                                        event.preventDefault();
                                        event.stopPropagation();
                                        copyToClipboard(shareUrl);
                                        toast('Copied URL', { type: 'info' });
                                    }}
                                    className="p-2 border-[1px] border-white hover:border-neutral-100 hover:shadow rounded-md"
                                >
                                    <ShareIcon width={19} height={19} />
                                </div>
                            </FormsCard>
                        </ActiveLink>
                    );
                })}
            </FormsContainer>
        </div>
    );
};
export default FormCards;
