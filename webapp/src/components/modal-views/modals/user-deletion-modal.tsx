import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import cn from 'classnames';
import { toast } from 'react-toastify';

import BetterInput from '@app/components/Common/input';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import Button from '@app/components/ui/button';
import FullScreenLoader from '@app/components/ui/fullscreen-loader';
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

    const handleDeleteAccount = async () => {
        try {
            if (confirm === 'CONFIRM') {
                await deleteAccount();
                router.push(`/${locale}login`);
                toast(t(toastMessage.accountDeletion.success).toString(), { toastId: ToastId.SUCCESS_TOAST, type: 'success' });
            }
        } catch (e) {
            toast(t(toastMessage.accountDeletion.failed).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
        }
    };
    const handleCopyPaste = (event: any) => {
        event.preventDefault();
    };

    return (
        <form onSubmit={handleDeleteAccount} className="p-6 pb-3 rounded relative w-full bg-white md:w-[682px]">
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
            <div className="flex gap-[26px] mt-2">
                <BetterInput
                    InputProps={{
                        sx: {
                            height: '42px',
                            borderColor: '#0764EB !important'
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
                <Button
                    disabled={confirm !== 'CONFIRM'}
                    isLoading={isLoading || isSuccess}
                    className={cn('body4 !text-brand-100 py-4 px-6 !leading-none !h-[42px] bg-red-500 ', confirm !== 'CONFIRM' ? 'opacity-30 cursor-not-allowed' : 'hover:!bg-red-600')}
                >
                    {t(buttonConstant.deleteNow)}
                </Button>
            </div>
        </form>
    );
}
