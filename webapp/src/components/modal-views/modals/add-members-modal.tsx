import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import AppTextField from '@Components/Common/Input/AppTextField';
import AppButton from '@Components/Common/Input/Button/AppButton';
import { ButtonSize } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';
import cn from 'classnames';
import { toast } from 'react-toastify';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { groupConstant } from '@app/constants/locales/group';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ToastId } from '@app/constants/toastId';
import { ResponderGroupDto } from '@app/models/dtos/groups';


interface IAddMemberModalProps {
    handleAddMembers: (members: Array<string>) => void;
    group?: ResponderGroupDto;
}
export default function AddMembersModal({ handleAddMembers, group }: IAddMemberModalProps) {
    const { t } = useTranslation();
    const { closeModal } = useModal();
    const [emails, setEmails] = useState<Array<string>>([]);
    const [email, setEmail] = useState<string>('');
    const handleInput = (event: any) => {
        setEmail(event.target.value);
    };
    const addEmail = (event: any) => {
        event.preventDefault();
        if (emails.includes(email.toLowerCase())) {
            toast(t(toastMessage.emailAlreadyExist).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            return;
        } else if (group && group.emails?.includes(email.toLowerCase())) {
            toast(t(toastMessage.alreadyInGroup).toString(), { toastId: ToastId.ERROR_TOAST, type: 'error' });
            return;
        }
        setEmails([...emails, email.toLowerCase()]);
        setEmail('');
    };
    return (
        <div className=" p-6 relative bg-brand-100 rounded-[8px] ">
            <Close onClick={closeModal} className="absolute top-2 right-2 cursor-pointer p-2 h-8 w-8" />
            <div className="sh1 !leading-none">{t(groupConstant.addMembers.default)}</div>
            <div className="body4 pt-6 !leading-none ">{t(groupConstant.addMembers.description)}</div>
            <form onSubmit={addEmail} className="flex gap-2 mt-4">
                <div className="    ">
                    <AppTextField  value={email} type="email" id="email" placeholder={t(placeHolder.memberEmail)} onChange={handleInput} />
                </div>
                <AppButton size={ButtonSize.Medium} disabled={!email} className={cn('font-semibold !px-6', !email && 'opacity-30')}>
                    {t(buttonConstant.add)}
                </AppButton>
            </form>
            {emails.length !== 0 && (
                <>
                    <p className="mt-2 leading-none mb-4 body5">{t(groupConstant.addedMembers)}</p>
                    <div className="items-center  w-full p-3 bg-white   gap-4 flex flex-wrap ">
                        {emails.map((email) => {
                            return (
                                <div className="p-2 rounded flex items-center gap-2 leading-none bg-brand-200 border border-brand-300 body5 !text-brand-500" key={email}>
                                    <span className="leading-none">{email}</span>
                                    <Close
                                        className="h-3 w-3 cursor-pointer"
                                        onClick={() => {
                                            setEmails(emails.filter((item) => item !== email));
                                        }}
                                    />
                                </div>
                            );
                        })}
                    </div>
                </>
            )}
            <div className="flex w-full mt-8 justify-end">
                <ModalButton buttonType={"Modal"} onClick={() => handleAddMembers(emails)}  size={ButtonSize.Medium} disabled={emails.length === 0} type="submit">
                    {t(buttonConstant.addMembers)}
                </ModalButton>
            </div>
        </div>
    );
}