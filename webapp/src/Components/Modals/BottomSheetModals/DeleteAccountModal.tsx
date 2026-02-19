import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/navigation';

import AppTextField from '@Components/Common/Input/AppTextField';
import { Button } from '@app/shadcn/components/ui/button';
import CheckBox from '@Components/Common/Input/CheckBox';
import TextArea from '@Components/Common/Input/TextArea';
import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@app/shadcn/components/ui/select';
import { Label } from '@app/shadcn/components/ui/label';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useDeleteAccountMutation } from '@app/store/auth/api';


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
                    <TextArea
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
                    <AppTextField
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
                    <CheckBox
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
                    <Button variant="danger" size="medium" onClick={onClickDelete}>
                        {t('DELETE_ACCOUNT.DELETE_NOW')}
                    </Button>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
}