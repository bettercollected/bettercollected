import React, {useState} from 'react';

import {useTranslation} from 'next-i18next';
import {useRouter} from 'next/router';

import Divider from '@Components/Common/DataDisplay/Divider';
import AppButton from '@Components/Common/Input/Button/AppButton';

import {Close} from '@app/components/icons/close';
import {useModal} from '@app/components/modal-views/context';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {useAppSelector} from '@app/store/hooks';
import QRGenerator from "@Components/Form/QRGenerator";
import useCopyToClipboard from "react-use/lib/useCopyToClipboard";
import {toast} from "react-toastify";
import {toastMessage} from "@app/constants/locales/toast-message";
import html2canvas from "html2canvas";

const GenerateQRModalView = () => {
    const {closeModal} = useModal();
    const {t} = useTranslation();
    const router = useRouter();
    const workspace: WorkspaceDto = useAppSelector((state) => state.workspace);

    const [_, copyToClipboard] = useCopyToClipboard();

    // const canvasElement = document.getElementsByTagName("canvas")[0];
    const canvasElement = document.getElementById("form-qr-code");

    const handleOnCopy = (text: any) => {
        copyToClipboard(text);
        toast(t(toastMessage.copied).toString(), {
            type: 'info'
        });
    };

    const onDownload = async () => {
        if (canvasElement) {
            const canvas = await html2canvas(canvasElement);
            const dataUrl = canvas.toDataURL('image/png');
            const link = document.createElement('a');
            link.href = dataUrl;
            link.download = 'QR.png';
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        }
    };

    // const onShare = () => {
    //     const dataUrl = canvasElement.toDataURL('image/png');
    //     handleOnCopy(dataUrl)
    // }

    const handleCopyImageToClipboard = async () => {
            try {
                if (canvasElement) {
                    const canvas = await html2canvas(canvasElement);
                    canvas.toBlob((blob) => {
                        if (blob) {
                            const item = new ClipboardItem({'image/png': blob});
                            navigator.clipboard.write([item])
                        }
                    }, 'image/png');
                    toast('QR Image Copied.', {
                        type: 'info'
                    });
                }
            } catch (error) {
                toast('Error Occured', {
                    type: 'info'
                });
                console.log(error)
            }
        }
    ;

    return (
        <div className=" bg-white w-[466px] rounded-[8px]">
            <div className={'flex justify-between px-4 py-[18px]'}>
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
            <div className={'p-10 pt-6 items-center flex flex-col justify-center gap-4'}>
                <QRGenerator/>
                <div className={'flex gap-2 '}>
                    <AppButton onClick={handleCopyImageToClipboard}>
                        Copy QR
                    </AppButton>
                    <AppButton onClick={onDownload}>
                        Download QR
                    </AppButton>
                    {/*<AppButton onClick={onShare}>*/}
                    {/*    Share QR*/}
                    {/*</AppButton>*/}
                </div>
            </div>
        </div>
    );
};

export default GenerateQRModalView;
