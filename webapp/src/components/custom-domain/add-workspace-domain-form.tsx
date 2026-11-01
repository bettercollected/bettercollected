import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import { useTranslation } from 'react-i18next';
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
            setMessage({ error: false, message: t('STAFF.WORKSPACE.ROOT_DOMAIN_WARNING') });
            setWarned(true);
            return;
        }
        if (!domain.match(/^(?!:\/\/)([a-zA-Z0-9-_]+\.)+[a-zA-Z]{2,63}$/)) {
            setMessage({ error: true, message: t('STAFF.WORKSPACE.NOT_A_DOMAIN') });
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
            <span className="p2-new text-black-700">{t('STAFF.WORKSPACE.DOMAIN_INTRO')}</span>
            {!workspace.isPro ? (
                // Free plan: the upgrade note IS the whole section. Showing the
                // domain form too was misleading — filling it in only bounced
                // you to the upgrade modal.
                <div className="mt-2 flex flex-wrap items-center gap-2 rounded-lg bg-brand-accent-100 px-3 py-2.5 text-sm text-brand-olive">
                    <span>{t('STAFF.WORKSPACE.DOMAIN_PRO')}</span>
                    <button type="button" onClick={() => openModal('UPGRADE_TO_PRO')} className="font-semibold underline underline-offset-2">
                        {t('STAFF.WORKSPACE.DOMAIN_UPGRADE')}
                    </button>
                </div>
            ) : (
                <>
                    <div className="text-black-800 mt-4 text-sm font-medium">{t('STAFF.WORKSPACE.DOMAIN_ENTER')}</div>
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
                                placeholder={t('STAFF.WORKSPACE.DOMAIN_PLACEHOLDER')}
                            />
                        </div>
                        <Button variant={'v2Button'} type="submit" disabled={warned} isLoading={isLoading}>
                            {t('STAFF.WORKSPACE.DOMAIN_ADD')}
                        </Button>
                    </form>
                    <div className="max-w-[440px]">
                        {message.message && <div className={cn(message.error ? 'text-[#C43D3D]' : 'text-brand-olive', 'whitespace-pre-wrap text-wrap text-xs')}>{message.message}</div>}
                        {warned && (
                            <Button variant="ghost" isLoading={isLoading} className="mt-2 cursor-pointer text-xs" onClick={addDomain}>
                                {t('STAFF.WORKSPACE.DOMAIN_ADD_ANYWAY')}
                            </Button>
                        )}
                    </div>
                </>
            )}
        </div>
    );
};

export default AddWorkspaceDomainForm;
