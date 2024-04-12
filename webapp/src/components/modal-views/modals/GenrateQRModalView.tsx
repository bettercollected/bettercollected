
import { useTranslation } from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';

import QRGenerator from '@Components/Form/QRGenerator';
import { Close } from '@app/components/icons/close';
import { useModal } from '@app/components/modal-views/context';
import { toastMessage } from '@app/constants/locales/toast-message';
import { StandardFormDto } from '@app/models/dtos/form';
import { Button } from '@app/shadcn/components/ui/button';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import html2canvas from 'html2canvas';
import { toast } from 'react-toastify';
import useCopyToClipboard from 'react-use/lib/useCopyToClipboard';

export interface IGenerateQR {
    form?: StandardFormDto;
}

const GenerateQRModalView = ({ form }: IGenerateQR) => {
    const { closeModal } = useModal();
    const { t } = useTranslation();
    const workspaceForm = useAppSelector(selectForm);
    const currentForm = form ? form : workspaceForm;

    const [_, copyToClipboard] = useCopyToClipboard();

    const handleOnCopy = (text: any) => {
        copyToClipboard(text);
        toast(t(toastMessage.copied).toString(), {
            type: 'info'
        });
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
            toast("Couldn't download because of the error.", {
                type: 'info'
            });
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
                        console.log('canvas : ', item);
                        navigator.clipboard.write([item]);
                    }
                }, 'image/png');
            toast('QR Image Copied.', {
                type: 'info'
            });
        } catch (error) {
            toast('Error Occured', {
                type: 'info'
            });
            console.log(error);
        }
    };
    return (
        <div className=" rounded-[8px] bg-white md:w-[466px]">
            <div className={'flex justify-between px-2 py-[18px] md:px-4'}>
                <h1 className={'p2-new'}>QR Code</h1>
                <div className={'hover:bg-black-200 absolute right-5 top-3 cursor-pointer p-1 hover:rounded-sm'}>
                    <Close
                        onClick={() => {
                            closeModal();
                        }}
                    />
                </div>
            </div>
            <Divider />
            <div className={'flex flex-col items-center justify-center gap-4 p-4 pt-6 md:p-10'}>
                <QRGenerator form={currentForm} />
                <span className="p4-new w-[266px] text-center">
                    Scan this QR code to get access to the form or{' '}
                    <span className="text-brand-500" onClick={onDownload}>
                        Download QR code
                    </span>
                </span>
                <div className={'flex gap-2 '}>
                    <Button variant={'v2Button'} onClick={handleCopyImageToClipboard}>
                        Copy QR
                    </Button>
                </div>
            </div>
        </div>
    );
};
export default GenerateQRModalView;
