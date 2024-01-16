import React, { useState } from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import CheckBox from '@Components/Common/Input/CheckBox';
import TextArea from '@Components/Common/Input/TextArea';
import BottomSheetModalWrapper from '@Components/Modals/ModalWrappers/BottomSheetModalWrapper';
import { FormControlLabel, FormGroup, Select } from '@mui/material';
import MenuItem from '@mui/material/MenuItem';
import { toast } from 'react-toastify';

import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { useDeleteAccountMutation } from '@app/store/auth/api';

export default function DeleteAccountModal() {
    const [deleteAccount] = useDeleteAccountMutation();
    const router = useRouter();

    const { t } = useTranslation();
    const [dropdownValue, setDropdownValue] = useState('');
    const [feedback, setFeedBack] = useState('');
    const [confirm, setConfirm] = useState('');

    const [checked, setChecked] = useState(false);

    const [error, setError] = useState(false);
    const onDropdownChange = (event: any) => {
        setDropdownValue(event.target.value);
    };

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
                router.push(`/`).then(() => {
                    toast(t(toastMessage.accountDeletion.success).toString(), {
                        toastId: ToastId.SUCCESS_TOAST,
                        type: 'success'
                    });
                });
            } else {
                toast(t(toastMessage.accountDeletion.failed).toString(), {
                    toastId: ToastId.ERROR_TOAST,
                    type: 'error'
                });
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
                    <Select
                        size="small"
                        MenuProps={{
                            style: { zIndex: 35001 }
                        }}
                        sx={{
                            '.MuiSelect-select.Mui-disabled': {
                                WebkitTextFillColor: '#1D1D1D'
                            }
                        }}
                        style={{
                            paddingTop: '3.5px',
                            paddingBottom: '3.5px',
                            paddingLeft: '2px',
                            fontSize: '14px'
                        }}
                        value={dropdownValue}
                        onChange={onDropdownChange}
                        className="w-full min-w-[167px] !rounded-md !border-gray-600 !mb-0 text-black-900 !bg-white"
                    >
                        {Reasons.map((reason: any, index: number) => (
                            <MenuItem key={reason.value} value={reason.value} className="relative">
                                {reason.title}
                            </MenuItem>
                        ))}
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
                <FormGroup className="mt-10 pl-2">
                    <FormControlLabel
                        checked={checked}
                        onChange={(event, checked) => {
                            setChecked(checked);
                        }}
                        className="flex items-start"
                        control={<CheckBox className="mr-2" />}
                        label={
                            <div>
                                {t('DELETE_ACCOUNT.I_UNDERSTAND_CONSEQUENCES')}
                                <span className="text-red-500 ml-2">*</span>
                            </div>
                        }
                    />
                </FormGroup>
                <div className="mt-[72px]">
                    {error && <div className="mb-4 text-sm text-red-500">* Please fill in all required fields or check CONFIRM field.</div>}
                    <AppButton variant={ButtonVariant.Danger} size={ButtonSize.Medium} onClick={onClickDelete}>
                        {t('DELETE_ACCOUNT.DELETE_NOW')}
                    </AppButton>
                </div>
            </div>
        </BottomSheetModalWrapper>
    );
}
