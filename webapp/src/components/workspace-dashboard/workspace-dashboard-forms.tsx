import { PushPin } from '@mui/icons-material';
import { toast } from 'react-toastify';

import { Google } from '@app/components/icons/brands/google';
import { EmptyImportFormIcon } from '@app/components/icons/empty-import-form-icon';
import { ShareIcon } from '@app/components/icons/share-icon';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button/button';
import Image from '@app/components/ui/image';
import ActiveLink from '@app/components/ui/links/active-link';
import environments from '@app/configs/environments';
import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';
import { useCopyToClipboard } from '@app/lib/hooks/use-copy-to-clipboard';
import { StandardFormDto } from '@app/models/dtos/form';
import { WorkspaceDto } from '@app/models/dtos/workspaceDto';
import { toEndDottedStr } from '@app/utils/stringUtils';

interface IWorkspaceDashboardFormsProps {
    workspaceForms: any;
    workspace: WorkspaceDto;
    hasCustomDomain: boolean;
}

export default function WorkspaceDashboardForms({ workspaceForms, workspace, hasCustomDomain }: IWorkspaceDashboardFormsProps) {
    const breakpoint = useBreakpoint();
    const { openModal } = useModal();

    const forms = workspaceForms?.data?.items;

    const [_, copyToClipboard] = useCopyToClipboard();

    return (
        <div className="mb-10">
            {forms?.length === 0 ? (
                <div className="w-full h-full flex flex-col items-center justify-center bg-white rounded-[4px] py-[84px]">
                    <EmptyImportFormIcon className="mb-8" />
                    <p className="sh1 mb-4 !leading-none">Import your first form</p>
                    <p className="body4 mb-8 !leading-none">Import your Google Forms or Typeforms</p>
                    <Button onClick={() => openModal('IMPORT_FORMS')} size="medium">
                        Import Forms
                    </Button>
                </div>
            ) : (
                <div className="grid grid-cols-1 pb-4 md:grid-cols-2 3xl:grid-cols-3 4xl:grid-cols-4 gap-8">
                    {forms?.length !== 0 &&
                        forms?.map((form: StandardFormDto) => {
                            const slug = form.settings?.customUrl;
                            let shareUrl = '';
                            if (window && typeof window !== 'undefined') {
                                const scheme = `${environments.CLIENT_HOST.includes('localhost') ? 'http' : 'https'}://`;
                                shareUrl = scheme + `${hasCustomDomain ? `${workspace.customDomain}/forms/${slug}` : `${environments.CLIENT_HOST}/${workspace.workspaceName}/forms/${slug}`}`;
                            }
                            return (
                                <ActiveLink key={form.formId} href={`/${workspace.workspaceName}/dashboard/forms/${form.formId}`}>
                                    <div className="flex flex-row items-center justify-between h-full gap-8 p-5 border-[1px] border-neutral-300 hover:border-blue-500 drop-shadow-sm hover:drop-shadow-lg transition cursor-pointer bg-white rounded-[20px]">
                                        <div className="flex flex-col w-full justify-between h-full">
                                            <div className="w-full ">
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
                                                    <p className="text-xl text-grey  p-0">{['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form?.title || 'Untitled', 15) : toEndDottedStr(form?.title || 'Untitled', 30)}</p>
                                                </div>
                                                {form?.description && (
                                                    <p className="text-base text-softBlue m-0 p-0 w-full">
                                                        {['xs', 'sm'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 45) : ['md'].indexOf(breakpoint) !== -1 ? toEndDottedStr(form.description, 80) : toEndDottedStr(form.description, 140)}
                                                    </p>
                                                )}
                                                {!form?.description && <p className="text-base text-softBlue m-0 p-0 w-full italic">Form description not available.</p>}
                                            </div>

                                            <div className="flex pt-3 justify-between">
                                                {<div className="rounded space-x-2 text-xs px-2 flex py-1 items-center text-gray-500 bg-gray-100">{form?.settings?.private ? 'Hidden' : 'Public'}</div>}
                                                <div className="flex">
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
                                                    {form?.settings?.pinned && <PushPin className="rotate-45" />}
                                                </div>
                                            </div>
                                        </div>
                                    </div>
                                </ActiveLink>
                            );
                        })}
                </div>
            )}
        </div>
    );
}
