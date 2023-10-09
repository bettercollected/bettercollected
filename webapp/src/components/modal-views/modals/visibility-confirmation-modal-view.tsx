import React from 'react';

import Divider from '@Components/Common/DataDisplay/Divider';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';

interface IVisibilityConfirmationModalViewProps {
    visibilityType: string;
    handleOnConfirm: () => void;
}

const VisibilityConfirmationModalView = ({ visibilityType, handleOnConfirm }: IVisibilityConfirmationModalViewProps) => {
    const { closeModal } = useModal();
    const title: any = {
        Public: ['Are you sure you want to make the form ', 'Public'],
        Private: ['Are you sure you want to make the form ', 'Private'],
        Group: ['No Groups Selected.', '']
    };
    const description: any = {
        Public: 'Anyone with the link of your form page can access and view the form.',
        Private: 'No one will be able to access or view this form.',
        Group: "You haven't selected any groups for your form. In this case, your form will be made public by default."
    };

    const onClickConfirm = () => {
        handleOnConfirm();
        closeModal();
    };

    return (
        <div className={'w-[470px] rounded-xl bg-white'}>
            <div className={'flex justify-between p-4'}>
                <h1 className={'text-sm font-normal text-black-800'}>Confirm Visibility</h1>
                <Close onClick={closeModal} />
            </div>
            <Divider />
            <div className={'pt-6 p-10 flex flex-col gap-3'}>
                <h1 className={'h4-new !text-black-800'}>
                    {title[visibilityType][0]} <span className={'text-pink-500'}>{title[visibilityType][1]} </span> {title[visibilityType][1] ? '?' : '.'}
                </h1>
                <h2 className={'text-sm font-normal mb-3 text-black-700'}>{description[visibilityType]}</h2>
                <div className={'flex flex-row gap-4 w-full'}>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} variant={ButtonVariant.Secondary}>
                        Cancel
                    </ModalButton>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} onClick={onClickConfirm}>
                        Confirm
                    </ModalButton>
                </div>
            </div>
        </div>
    );
};

export default VisibilityConfirmationModalView;
