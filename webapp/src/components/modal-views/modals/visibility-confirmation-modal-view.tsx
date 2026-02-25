
import { useTranslation } from 'next-i18next';

import { Button } from '@app/shadcn/components/ui/button';
import Divider from '@Components/Common/divider';

import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { useBottomSheetModal } from '@app/components/Modals/Contexts/BottomSheetModalContext';

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
                    <Button size="medium" variant="secondary" onClick={closeModal}>
                        {t('BUTTON.CANCEL')}
                    </Button>
                    <Button size="medium" onClick={onClickConfirm}>
                        {t('BUTTON.CONFIRM')}
                    </Button>
                </div>
            </div>
        </div>
    );
};

export default VisibilityConfirmationModalView;
