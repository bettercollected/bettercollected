import React from 'react';

import {useTranslation} from 'next-i18next';

import Divider from '@Components/Common/DataDisplay/Divider';
import AppButton from '@Components/Common/Input/Button/AppButton';

import {Close} from '@app/components/icons/close';
import {useModal} from '@app/components/modal-views/context';
import {useAppSelector} from '@app/store/hooks';
import QRGenerator from "@Components/Form/QRGenerator";
import useCopyToClipboard from "react-use/lib/useCopyToClipboard";
import {toast} from "react-toastify";
import {toastMessage} from "@app/constants/locales/toast-message";
import html2canvas from "html2canvas";
import {selectForm} from "@app/store/forms/slice";
import {StandardFormDto} from "@app/models/dtos/form";

export interface IGenerateQR {
    form?: StandardFormDto;
}

const GenerateQRModalView = ({form}: IGenerateQR) => {
        const {closeModal} = useModal();
        const {t} = useTranslation();
        const workspaceForm = useAppSelector(selectForm)
        const currentForm = form ? form : workspaceForm

        const [_, copyToClipboard] = useCopyToClipboard();

        const handleOnCopy = (text: any) => {
            copyToClipboard(text);
            toast(t(toastMessage.copied).toString(), {
                type: 'info'
            });
        };

        const onDownload = async () => {
            try {
                const canvasElement = document.getElementById("form-qr-code");
                const canvas = canvasElement && await html2canvas(canvasElement);
                const dataUrl = canvas && canvas.toDataURL('image/png');
                const link = document.createElement('a');
                link.href = dataUrl || '';
                link.download = 'QR.png';
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            } catch (error) {
                toast('Couldn\'t download because of the error.', {
                    type: 'info'
                });
                console.log(error)
            }
        };

        const handleCopyImageToClipboard = async () => {
                try {
                    const canvasElement = document.getElementById("form-qr-code");
                    const canvas = canvasElement && await html2canvas(canvasElement);
                    canvas && canvas.toBlob((blob) => {
                        if (blob) {
                            const item = new ClipboardItem({'image/png': blob});
                            navigator.clipboard.write([item])
                        }
                    }, 'image/png');
                    toast('QR Image Copied.', {
                        type: 'info'
                    });
                } catch (error) {
                    toast('Error Occured', {
                        type: 'info'
                    });
                    console.log(error)
                }
            }
        ;

        return (
            <div className=" bg-white md:w-[466px] rounded-[8px]">
                <div className={'flex justify-between px-2 md:px-4 py-[18px]'}>
                    <h1 className={'text-sm font-normal text-black-800'}>Generated QR</h1>
                    <div className={'absolute top-3 right-5 cursor-pointer hover:bg-black-200 hover:rounded-sm p-1'}>
                        <Close
                            onClick={() => {
                                closeModal();
                            }}
                        />
                    </div>
                </div>
                <Divider/>
                <div className={'p-4 md:p-10 pt-6 items-center flex flex-col justify-center gap-4'}>
                    <QRGenerator form={currentForm}/>
                    <div className={'flex gap-2 '}>
                        <AppButton onClick={handleCopyImageToClipboard}>
                            Copy QR
                        </AppButton>
                        <AppButton onClick={onDownload}>
                            Download QR
                        </AppButton>
                    </div>
                </div>
            </div>
        );
    }
;

export default GenerateQRModalView;
