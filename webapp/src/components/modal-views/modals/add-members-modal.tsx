import { useState } from 'react';

import { useTranslation } from 'next-i18next';

import { Close } from '@app/Components/icons/close';
import { useModal } from '@app/Components/modal-views/context';
import { buttonConstant } from '@app/constants/locales/button';
import { placeHolder } from '@app/constants/locales/placeholder';
import { toastMessage } from '@app/constants/locales/toast-message';
import { ResponderGroupDto } from '@app/models/dtos/groups';
import { Button } from '@app/shadcn/components/ui/button';
import { AppInput } from '@app/shadcn/components/ui/input';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import PlusIcon from '@Components/Common/Icons/Common/Plus';
import HeaderModalWrapper from '@Components/Modals/ModalWrappers/HeaderModalWrapper';
import cn from 'classnames';


interface IAddMemberModalProps {
    handleAddMembers: (members: Array<string>) => void;
    group?: ResponderGroupDto;
}

export default function AddMembersModal({ handleAddMembers, group }: IAddMemberModalProps) {
    const { toast } = useToast();
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
            toast({ description: t(toastMessage.emailAlreadyExist).toString(), variant: 'destructive' });
            return;
        } else if (group && group.emails?.includes(email.toLowerCase())) {
            toast({ description: t(toastMessage.alreadyInGroup).toString(), variant: 'destructive' });
            return;
        }
        setEmails([...emails, email.toLowerCase()]);
        setEmail('');
    };
    return (
        <HeaderModalWrapper headerTitle={t('GROUP.ADD_MEMBERS.DEFAULT')}>
            <div className=" ">
                <div className="h4-new">{t('EMAIL_ADDRESS')}</div>
                <form onSubmit={addEmail} className="flex gap-2 mt-2">
                    <div className="    ">
                        <AppInput className="w-full" value={email} type="email" id="email" placeholder={t(placeHolder.memberEmail)} onChange={handleInput} />
                    </div>
                    <Button size="sm" variant="ghost" disabled={!email} className={cn('font-semibold', !email && 'opacity-30')}>
                        <PlusIcon width={16} height={16} />
                    </Button>
                </form>
                {emails.length !== 0 && (
                    <>
                        <div className="items-center  w-full mt-6 flex md:max-w-[660px] max-w-full flex-wrap gap-4 ">
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
                    <Button className="w-full" onClick={() => handleAddMembers(emails)} size="medium" disabled={emails.length === 0} type="submit">
                        {t(buttonConstant.addMembers)}
                    </Button>
                </div>
            </div>
        </HeaderModalWrapper>
    );
}