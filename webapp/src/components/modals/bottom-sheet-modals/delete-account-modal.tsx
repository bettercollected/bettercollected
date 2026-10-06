import { useState } from 'react';

import { useTranslation } from 'react-i18next';
import { useRouter } from 'next/navigation';

import BottomSheetModalWrapper from '@Components/modals/modal-wrapper/bottom-sheet-modal-wrapper';
import { Button } from '@app/shadcn/components/ui/button';
import { Label } from '@app/shadcn/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';

import { toastMessage } from '@app/constants/locales/toast-message';
import { Checkbox } from '@app/shadcn/components/ui/checkbox';
import { AppInput } from '@app/shadcn/components/ui/input';
import { Textarea } from '@app/shadcn/components/ui/textarea';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { useDeleteAccountMutation } from '@app/store/auth/api';

// A workspace the account is the billing owner of that has other owners: the
// backend refuses the deletion (409) until billing moves or they are removed.
interface SharedWorkspace {
    id: string;
    title?: string;
    workspaceName?: string;
    billingOwnerCanChange?: boolean;
}

export function sharedWorkspacesOf(error: any): Array<SharedWorkspace> | null {
    const body = error?.data;
    if (error?.status !== 409 || body?.code !== 'billing_owner_of_shared_workspaces') return null;
    return Array.isArray(body.workspaces) ? body.workspaces : [];
}


export default function DeleteAccountModal() {
    const [deleteAccount] = useDeleteAccountMutation();
    const router = useRouter();
    const { toast } = useToast();

    const { t } = useTranslation();
    const [dropdownValue, setDropdownValue] = useState('');
    const [feedback, setFeedBack] = useState('');
    const [confirm, setConfirm] = useState('');

    const [checked, setChecked] = useState(false);

    const [error, setError] = useState(false);
    const [shared, setShared] = useState<Array<SharedWorkspace> | null>(null);

    const onClickDelete = async () => {
        if (!dropdownValue || !confirm || !checked || confirm.toUpperCase() !== 'CONFIRM' || ((dropdownValue === 'Something else' || dropdownValue === 'I have found a better alternative.') && !feedback)) {
            setError(true);
            return;
        }
        deleteAccount({
            reasonForDeletion: dropdownValue,
            feedback: feedback
        }).then((response) => {
            if ('data' in response) {
                router.push(`/`)
                toast({ description: t(toastMessage.accountDeletion.success).toString() });
            } else if (sharedWorkspacesOf(response.error)) {
                setShared(sharedWorkspacesOf(response.error));
            } else {
                toast({ description: t(toastMessage.accountDeletion.failed).toString(), variant: 'destructive' });
            }
        });
        setError(false);
    };

    const handleCopyPaste = (event: any) => {
        event.preventDefault();
    };

    const Reasons: Array<any> = [
        {
            title: t('DELETE_ACCOUNT.REASONS.4'),
            value: 'I am unhappy with the pricing.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.3'),
            value: 'I miss essential features or integrations that I need.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.1'),
            value: 'I find it challenging to create forms.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.5'),
            value: 'I have found a better alternative.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.6'),
            value: 'The app is slow.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.2'),
            value: 'I am having difficulties in importing the form.'
        },
        {
            title: t('DELETE_ACCOUNT.REASONS.7'),
            value: 'Something else'
        }
    ];

    return (
        <BottomSheetModalWrapper>
            <div>
                <div className="h2-new mb-2">{t('DELETE_ACCOUNT.TITLE')}</div>
                <div className="p2-new text-black-700">{t('DELETE_ACCOUNT.DESCRIPTION')}</div>
            </div>
            <div className="mt-[72px] max-w-[540px]">
                <div className="h4-new text-black-800 mb-2">
                    {t('DELETE_ACCOUNT.WHY_DELETE')}
                    <span className="text-red-500 ml-2">*</span>
                </div>
                <div className="w-full">
                    <Select value={dropdownValue} onValueChange={(val) => setDropdownValue(val)}>
                        <SelectTrigger className="w-full min-w-[167px] !rounded-md !border-gray-600 !mb-0 text-black-900 !bg-white">
                            <SelectValue placeholder="Select a reason" />
                        </SelectTrigger>
                        <SelectContent className="z-[35001]">
                            {Reasons.map((reason: any, index: number) => (
                                <SelectItem key={reason.value} value={reason.value} className="relative">
                                    {reason.title}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>
                <div className="mt-10">
                    <div className="h4-new text-black-800 mb-2">
                        {dropdownValue === 'Something else' || dropdownValue === 'I have found a better alternative.' ? (
                            <>
                                {t('DELETE_ACCOUNT.ANYTHING_ELSE')}
                                <span className="text-red-500 ml-2"> *</span>
                            </>
                        ) : (
                            <>{t('DELETE_ACCOUNT.ANYTHING_ELSE') + '(' + t('DELETE_ACCOUNT.OPTIONAL') + ')'}</>
                        )}
                    </div>
                    <Textarea
                        className="w-full rounded-md border border-black-500 focus:border-[#B8E8FF] focus:shadow-input"
                        value={feedback}
                        onChange={(event) => {
                            setFeedBack(event.target.value);
                        }}
                        required={dropdownValue === 'Something else'}
                        placeholder={t('DELETE_ACCOUNT.WRITE_FEEDBACK')}
                    />
                </div>
                <div className="mt-10">
                    <div className="h4-new text-black-800 mb-2">
                        {t('DELETE_ACCOUNT.TYPE_CONFIRM')}
                        <span className="text-red-500 ml-2">*</span>
                    </div>
                    <AppInput
                        onCut={handleCopyPaste}
                        onPaste={handleCopyPaste}
                        onCopy={handleCopyPaste}
                        value={confirm}
                        onChange={(event) => {
                            setConfirm(event.target.value.toUpperCase());
                        }}
                        placeholder={'CONFIRM'}
                    />
                </div>
                <div className="mt-10 pl-2 flex items-start">
                    <Checkbox
                        checked={checked}
                        onCheckedChange={(checked) => {
                            setChecked(!!checked);
                        }}
                        className="mr-2"
                        id="check"
                    />
                    <Label htmlFor="check" className="cursor-pointer">
                        <div>
                            {t('DELETE_ACCOUNT.I_UNDERSTAND_CONSEQUENCES')}
                            <span className="text-red-500 ml-2">*</span>
                        </div>
                    </Label>
                </div>
                <div className="mt-[72px]">
                    {error && <div className="mb-4 text-sm text-red-500">* Please fill in all required fields or check CONFIRM field.</div>}
                    {shared && (
                        <div className="mb-4 rounded-md border border-red-200 bg-red-50 p-4 text-sm text-black-800" role="alert" data-testid="delete-account-shared-workspaces">
                            <p className="font-medium">{t('DELETE_ACCOUNT.SHARED_WORKSPACES')}</p>
                            <ul className="mt-2 list-disc pl-5">
                                {shared.map((workspace) => (
                                    <li key={workspace.id}>
                                        <span className="font-medium">{workspace.title || workspace.workspaceName}</span>
                                        {': '}
                                        {t(workspace.billingOwnerCanChange ? 'DELETE_ACCOUNT.SHARED_MOVE_OR_REMOVE' : 'DELETE_ACCOUNT.SHARED_REMOVE_OWNERS')}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}
                    <Button variant="danger" size="medium" onClick={onClickDelete}>
                        {t('DELETE_ACCOUNT.DELETE_NOW')}
                    </Button>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
}