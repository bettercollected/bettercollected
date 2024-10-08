
import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import { ButtonSize, ButtonVariant } from '@Components/Common/Input/Button/AppButtonProps';
import ModalButton from '@Components/Common/Input/Button/ModalButton';

import { Close } from '@app/Components/icons/close';
import { useModal } from '@app/Components/modal-views/context';
import { useBottomSheetModal } from '@Components/Modals/Contexts/BottomSheetModalContext';

interface IVisibilityConfirmationModalViewProps {
    visibilityType: string;
    handleOnConfirm: () => void;
    isTemplate?: boolean;
}

const VisibilityConfirmationModalView = ({ visibilityType, handleOnConfirm, isTemplate = false }: IVisibilityConfirmationModalViewProps) => {
    const { closeModal } = useModal();
    const { closeBottomSheetModal } = useBottomSheetModal();
    const { t } = useTranslation();
    const title: any = {
        Public: [`${t('VISIBILITY_MODAL.ARE_YOU_SURE')} ${isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.TITLE') : t('VISIBILITY_MODAL.FORM.TITLE')} `, t('PUBLIC')],
        Private: [`${t('VISIBILITY_MODAL.ARE_YOU_SURE')} ${isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.TITLE') : t('VISIBILITY_MODAL.FORM.TITLE')} `, t('HIDDEN')],
        Group: [t('VISIBILITY_MODAL.GROUP.TITLE'), '']
    };
    const description: any = {
        Public: isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.DESCRIPTION_PUBLIC') : t('VISIBILITY_MODAL.FORM.DESCRIPTION_PUBLIC'),
        Private: isTemplate ? t('VISIBILITY_MODAL.TEMPLATE.DESCRIPTION_PRIVATE') : t('VISIBILITY_MODAL.FORM.DESCRIPTION_PRIVATE'),
        Group: t('VISIBILITY_MODAL.GROUP.TITLE')
    };

    const onClickConfirm = () => {
        handleOnConfirm();
        closeModal();
        closeBottomSheetModal();
    };

    return (
        <div className={'rounded-xl bg-white md:w-[466px]'}>
            <div className={'flex justify-between p-4'}>
                <h1 className={'text-black-800 text-sm font-normal'}>{t('VISIBILITY_MODAL.TITLE')}</h1>
                <div className={'hover:bg-black-200 absolute right-5 top-3 cursor-pointer p-1 hover:rounded-sm'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className={'flex flex-col gap-3 p-10 pt-6'}>
                <h1 className={'h4-new !text-black-800'}>
                    {title[visibilityType][0]} <span className={'text-pink-500'}>{title[visibilityType][1]} </span> {title[visibilityType][1] ? '?' : '.'}
                </h1>
                <h2 className={'text-black-700 mb-3 text-sm font-normal'}>{description[visibilityType]}</h2>
                <div className={'flex w-full flex-row gap-4'}>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} variant={ButtonVariant.Secondary} onClick={closeModal}>
                        {t('BUTTON.CANCEL')}
                    </ModalButton>
                    <ModalButton buttonType={'Modal'} size={ButtonSize.Medium} onClick={onClickConfirm}>
                        {t('BUTTON.CONFIRM')}
                    </ModalButton>
                </div>
            </div>
        </div>
    );
};

export default VisibilityConfirmationModalView;
