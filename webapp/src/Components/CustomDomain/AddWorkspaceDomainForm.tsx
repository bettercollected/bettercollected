import { ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { cn } from '@app/shadcn/util/lib';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { usePatchExistingWorkspaceMutation } from '@app/store/workspaces/api';
import { selectWorkspace, setWorkspace } from '@app/store/workspaces/slice';
import { useTranslation } from 'next-i18next';
import { useState } from 'react';
import { toast } from 'react-toastify';

const AddWorkspaceDomainForm = () => {
    const [patchExistingWorkspace, { isLoading }] = usePatchExistingWorkspaceMutation();

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
            setMessage({ error: true, message: 'Invalid Domain' });
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
                toast.error(response.error.data?.message || response.error.data || t(toastMessage.somethingWentWrong), { toastId: ToastId.ERROR_TOAST });
            }
        }
    };
    return (
        <div className="mt-4 flex flex-col  gap-2">
            <span className="text-black-700 text-xs">You can use your own domain name to have a custom URL for your published forms. Consider using a subdomain, such as : forms.yourdomain.com</span>
            <div className="text-black-800 mt-4 text-xs font-medium">Enter a domain you own</div>
            <form
                onSubmit={(event) => {
                    event.preventDefault();
                    addDomain();
                }}
                className="flex items-center gap-4"
            >
                <AppInput
                    className={cn('max-w-[400px]', message.message && (message.error ? 'border-red-500' : ''))}
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
                <Button variant={'v2Button'} type="submit" disabled={warned} isLoading={isLoading}>
                    {' '}
                    Add Domain
                </Button>
            </form>
            <div className="max-w-[400px]">
                {message.message && <div className={cn(message.error ? 'text-red-500' : 'text-[#FFA716]', 'whitespace-pre-wrap text-wrap text-xs	')}>{message.message}</div>}
                {warned && (
                    <Button variant={ButtonVariant.Ghost} isLoading={isLoading} className="mt-2 cursor-pointer text-xs text-blue-500" onClick={addDomain}>
                        Add Anyway
                    </Button>
                )}
            </div>
        </div>
    );
};

export default AddWorkspaceDomainForm;
