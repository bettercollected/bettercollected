import { useTranslation } from 'react-i18next';

import Divider from '@Components/common/divider';

import QRGenerator from '@Components/form/qr-generator';
import ModalCloseButton from '@app/components/modal-views/modal-close-button';
import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { useToast } from '@app/shadcn/components/ui/use-toast';
import { selectAuth } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import html2canvas from 'html2canvas';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

interface IGenerateQR {
    form?: StandardFormDto;
}

const GenerateQRModalView = ({ form }: IGenerateQR) => {
    const { toast } = useToast();
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspaceForm = useAppSelector(selectForm);
    const currentForm = form ? form : workspaceForm;
    const auth = useAppSelector(selectAuth);

    const [_, copyToClipboard] = useCopyToClipboard();

    const handleOnCopy = (text: any) => {
        copyToClipboard(text);
        toast({ description: t(toastMessage.copied).toString() });
    };

    const onDownload = async () => {
        try {
            const canvasElement = document.getElementById('form-qr-code');
            const canvas = canvasElement && (await html2canvas(canvasElement));
            const dataUrl = canvas && canvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.href = dataUrl || '';
            link.download = `${currentForm?.title}_QR.png`;
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        } catch (error) {
            toast({ description: t('STAFF.MODALS.QR_DOWNLOAD_FAILED') });
            console.log(error);
        }
    };

    const handleCopyImageToClipboard = async () => {
        try {
            const canvasElement = document.getElementById('form-qr-code');
            const canvas = canvasElement && (await html2canvas(canvasElement));
            canvas &&
                canvas.toBlob((blob) => {
                    if (blob) {
                        const item = new ClipboardItem({ 'image/png': blob });
                        navigator.clipboard.write([item]);
                    }
                }, 'image/png');
            toast({ description: t('STAFF.MODALS.QR_COPIED') });
        } catch (error) {
            toast({ description: t('STAFF.MODALS.QR_FAILED') });
            console.log(error);
        }
    };
    return (
        <div className=" rounded-[8px] bg-white md:w-[466px]">
            <div className={'flex justify-between px-2 py-[18px] md:px-4'}>
                <h1 className={'p2-new'}>{t('STAFF.MODALS.QR_TITLE')}</h1>
                <ModalCloseButton onClick={closeModal} className="absolute right-5 top-3 h-8 w-8" iconClassName="h-6 w-6" />
            </div>
            <Divider />
            <div className={'flex flex-col items-center justify-center gap-4 p-4 pt-6 md:p-10'}>
                <QRGenerator form={currentForm} />
                <span className="p4-new w-[266px] text-center">{t('STAFF.MODALS.QR_INTRO')}</span>
                <div className={'flex gap-2 '}>
                    <Button variant={'v2Button'} onClick={onDownload} data-umami-event="Download QR button">
                        {t('STAFF.MODALS.QR_DOWNLOAD')}
                    </Button>
                    <Button variant={'v2Button'} onClick={handleCopyImageToClipboard} data-umami-event="Copy QR button">
                        {t('STAFF.MODALS.QR_COPY')}
                    </Button>
                </div>
            </div>
        </div>
    );
};
export default GenerateQRModalView;
