import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import { useTranslation } from 'next-i18next';
import { useState } from 'react';

import { useToast } from '@app/shadcn/components/ui/use-toast';

const AddWorkspaceDomainForm = () => {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();
    const { toast } = useToast();

    const workspace = useAppSelector(selectWorkspace);
    const { openModal } = useFullScreenModal();

    const [warned, setWarned] = useState(false);

    const [domain, setDomain] = useState('');
    const dispatch = useAppDispatch();
    const { t } = useTranslation();

    const [message, setMessage] = useState({
        error: false,
        message: ''
    });

    const addDomain = async () => {
        if (!workspace.isPro) {
            openModal('UPGRADE_TO_PRO');
            return;
        }
        if (domain.match(/^[a-zA-Z0-9-]+\.[a-zA-Z]{2,63}$/) && !warned) {
            setMessage({ error: false, message: 'This looks like a root domain. This might break your existing site. We recommend using subdomain that is not used elsewhere.' });
            setWarned(true);
            return;
        }
        if (!domain.match(/^(?!:\/\/)([a-zA-Z0-9-_]+\.)+[a-zA-Z]{2,63}$/)) {
            setMessage({ error: true, message: "That doesn't look like a domain — try something like forms.yoursite.com." });
        } else {
            const formData = new FormData();
            formData.append('custom_domain', domain);
            const body = {
                workspace_id: workspace.id,
                body: formData
            };
            const response: any = await patchExistingWorkspace(body);
            if (response.data) {
                dispatch(setWorkspace(response.data));
            } else if (response.error) {
                toast({
                    description: response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong),
                    variant: 'destructive'
                });
            }
        }
    };
    return (
        <div className="mt-3 flex flex-col gap-2">
            <span className="p2-new text-black-700">Serve your site from a domain you own — a subdomain like forms.yourdomain.com works best.</span>
            {!workspace.isPro ? (
                // Free plan: the upgrade note IS the whole section. Showing the
                // domain form too was misleading — filling it in only bounced
                // you to the upgrade modal.
                <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-[#FBF3E4] px-3 py-2.5 text-sm text-[#B26B00]">
                    <span>Custom domains are a Pro feature.</span>
                    <button type="button" onClick={() => openModal('UPGRADE_TO_PRO')} className="font-semibold underline underline-offset-2">
                        Upgrade to connect your domain
                    </button>
                </div>
            ) : (
                <>
                    <div className="text-black-800 mt-4 text-sm font-medium">Enter a domain you own</div>
                    <form
                        onSubmit={(event) => {
                            event.preventDefault();
                            addDomain();
                        }}
                        className="flex items-start justify-start gap-4"
                    >
                        <div>
                            <AppInput
                                className={cn('max-w-[600px]', message.message && (message.error ? 'border-[#C43D3D]' : ''))}
                                value={domain}
                                onChange={(event) => {
                                    setDomain(event.target.value);
                                    setWarned(false);
                                    if (message.message) {
                                        setMessage({ error: false, message: '' });
                                    }
                                }}
                                placeholder="eg. forms.yoursite.com"
                            />
                        </div>
                        <Button variant={'v2Button'} type="submit" disabled={warned} isLoading={isLoading}>
                            Add domain
                        </Button>
                    </form>
                    <div className="max-w-[440px]">
                        {message.message && <div className={cn(message.error ? 'text-[#C43D3D]' : 'text-[#B26B00]', 'whitespace-pre-wrap text-wrap text-xs')}>{message.message}</div>}
                        {warned && (
                            <Button variant="ghost" isLoading={isLoading} className="mt-2 cursor-pointer text-xs" onClick={addDomain}>
                                Add anyway
                            </Button>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default AddWorkspaceDomainForm;
