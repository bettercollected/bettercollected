import React, { useState } from 'react';

import Image from 'next/image';

import deleteImg from '@app/assets/images/delete.png';
import fileUploadImg from '@app/assets/images/file-upload.png';

interface FileUploadProps {
    id?: string;
    disableUpload?: boolean;
}
export default function FileUpload({ id, disableUpload = false }: FileUploadProps) {
    const [isDragging, setIsDragging] = useState(false);
    const [file, setFile] = useState<File | null>(null);

    const handleDragEnter = (event: any) => {
        event.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDragOver = (event: any) => {
        event.preventDefault();
    };

    const handleDrop = (event: any) => {
        event.preventDefault();
        setIsDragging(false);

        const files: FileList = event.dataTransfer.files;
        setFile(Object.values(files)[0]);
    };

    const handleFileInputChange = (event: any) => {
        const files: File[] = event.target.files;
        setFile(Object.values(files)[0]);
    };

    const getFilePreview = (file: File) => {
        return (
            <div className="flex w-full space-x-2">
                <div className="p1 flex w-full justify-between rounded bg-blue-200 py-2 px-3">{file.name}</div>
                <div className="items-center justify-center rounded bg-blue-200 p-2" onClick={() => setFile(null)}>
                    <Image src={deleteImg} alt="delete-icon" width={24} height={24} />
                </div>
            </div>
        );
    };

    return (
        <div className="w-[541px] space-y-3">
            <div
                tabIndex={0}
                id={id}
                className={`flex flex-col items-center justify-center space-y-3 rounded border border-dashed border-black-600 bg-black-200 py-10 focus-visible:!outline-none ${isDragging && !disableUpload ? 'border-blue-500' : ''}`}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDragOver={handleDragOver}
                onDrop={handleDrop}
            >
                <label htmlFor={`${id}-file-input`} className="flex cursor-pointer items-center space-x-2 rounded border bg-white py-2 px-3 hover:bg-gray-50">
                    <Image alt="file-upload-img" src={fileUploadImg} width={24} height={24} />
                    <span className="text-sm font-semibold leading-5 text-black-900">Upload File</span>
                </label>
                {!disableUpload && <input type="file" id={`${id}-file-input`} className="hidden" onChange={handleFileInputChange} />}
                <div className="flex w-full flex-col items-center space-y-2 text-xs text-black-800">
                    <span className="font-semibold leading-4">{isDragging ? 'Release to drop' : 'Or drag here'}</span>
                    <span className="text-center leading-5">
                        Media supported: Images, PDF, Videos, Audios, File <span className="block">Max size limit: 25 MB</span>
                    </span>
                </div>
            </div>
            {file && getFilePreview(file)}
        </div>
    );
}
