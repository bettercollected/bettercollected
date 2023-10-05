import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { accountDeletion } from '@app/constants/locales/account-deletion';
import { buttonConstant } from '@app/constants/locales/button';
import { localesCommon } from '@app/constants/locales/common';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useDeleteAccountMutation } from '@app/store/auth/api';

export default function UserDeletionModal() {
    const { closeModal } = useModal();
    const [confirm, setConfirm] = useState('');
    const { t } = useTranslation();
    const [deleteAccount, { isLoading, isSuccess }] = useDeleteAccountMutation();
    const router = useRouter();
    const locale = router?.locale === 'en' ? '' : `${router.locale}/`;

    const handleDeleteAccount = async (event: any) => {
        event.preventDefault();
        try {
            if (confirm.toUpperCase() === 'CONFIRM') {
                await deleteAccount().then((response) => {
                    if ('data' in response) {
                        router.push(`/`);
                        toast(t(toastMessage.accountDeletion.success).toString(), {
                            toastId: ToastId.SUCCESS_TOAST,
                            type: 'success'
                        });
                    } else {
                        toast(t(toastMessage.accountDeletion.failed).toString(), {
                            toastId: ToastId.ERROR_TOAST,
                            type: 'error'
                        });
                    }
                });
            }
        } catch (e) {
            toast(t(toastMessage.accountDeletion.failed).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const handleCopyPaste = (event: any) => {
        event.preventDefault();
    };

    return (
        <form onSubmit={handleDeleteAccount} className="p-10 rounded relative w-full bg-white md:w-[682px]">
            <Close
                className="absolute cursor-pointer text-black-600 top-5 right-5"
                height={16}
                width={16}
                onClick={() => {
                    closeModal();
                }}
            />
            <p className="sh3">{t(accountDeletion.title)}</p>
            <ul className="list-disc  body4 ml-5 mt-4 !text-black-700 !mb-6">
                <li>{t(accountDeletion.point1)}</li>
                <li className="my-3">{t(accountDeletion.point2)}</li>
                <li>{t(accountDeletion.point3)}</li>
                <li className="mt-3">{t(accountDeletion.point4)}</li>
            </ul>
            <p dangerouslySetInnerHTML={{ __html: t(accountDeletion.inputTextLabel) }} className="body6 !font-normal"></p>
            <div className="flex gap-4 mt-2 ">
                <AppTextField
                    inputProps={{
                        style: {
                            textTransform: 'uppercase',
                            paddingTop: 0,
                            paddingBottom: 0,
                            height: 48,
                            fontSize: 16,
                            color: 'black',
                            fontWeight: 400,
                            content: 'none',
                            letterSpacing: 0
                        }
                    }}
                    placeholder={t(localesCommon.confirm)}
                    onChange={(e) => {
                        setConfirm(e.target.value);
                    }}
                    onCut={handleCopyPaste}
                    onPaste={handleCopyPaste}
                    onCopy={handleCopyPaste}
                />
                <AppButton variant={ButtonVariant.Danger} disabled={confirm.toUpperCase() !== 'CONFIRM'} isLoading={isLoading || isSuccess} className={cn(confirm.toUpperCase() !== 'CONFIRM' ? 'cursor-not-allowed' : '')} size={ButtonSize.Medium}>
                    {t(buttonConstant.deleteNow)}
                </AppButton>
            </div>
        </form>
    );
}
