import React, { useRef, useState } from 'react';

import Image from 'next/image';

import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { toast } from 'react-toastify';

import deleteImg from '@app/assets/images/delete.png';
import fileUploadImg from '@app/assets/images/file-upload.png';
import AnchorLink from '@app/components/ui/links/anchor-link';
import { FileMetadata } from '@app/models/types/fileTypes';
import { addAnswer, selectAnswer } from '@app/store/fill-form/slice';
import { useAppDispatch, useAppSelector } from '@app/store/hooks';
import { useLazyGetFormFileDownloadableLinkQuery } from '@app/store/workspaces/api';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { downloadFile, generateFileMetaData } from '@app/utils/fileUtils';

import { FormFieldProps } from './BetterCollectedForm';
import useFormAtom from './atom';

export default function FileUpload({ field, ans, enabled }: FormFieldProps) {
    const [isDragging, setIsDragging] = useState(false);
    const inputFileRef = useRef<HTMLInputElement | null>(null);
    const { addFile } = useFormAtom();
    const workspace = useAppSelector(selectWorkspace);
    const [getFileDownloadableLink, result] = useLazyGetFormFileDownloadableLinkQuery();
    const [fileMetaData, setFileMetadata] = useState<FileMetadata>(ans?.file_metadata ?? { id: uuidv4() });
    const dispatch = useAppDispatch();

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

    const updateAndDispatchFile = (file: File) => {
        const fMetaData = generateFileMetaData(file, fileMetaData.id);
        if (fMetaData.size! > 25.0) {
            toast('File must be less than 25 MB', { type: 'error' });
            return;
        }
        setFileMetadata({ ...fMetaData });
        addFile(field.id, fMetaData.id, fMetaData.name!, file);
        dispatch(addAnswer({ field: { id: field.id }, file_metadata: { ...fMetaData } }));
    };

    const handleDrop = (event: any) => {
        event.preventDefault();
        setIsDragging(false);

        const files: FileList = event.dataTransfer.files;
        const file = Object.values(files)[0];
        updateAndDispatchFile(file);
    };

    const handleFileInputChange = (event: any) => {
        const files: File[] = event.target.files;
        const file = Object.values(files)[0];
        updateAndDispatchFile(file);
    };

    const downloadFormFile = async () => {
        if (!enabled) return;

        const payload = await getFileDownloadableLink({ workspace_id: workspace.id, file_id: fileMetaData.id });
        if (payload.data) {
            downloadFile(payload.data, fileMetaData.name ?? fileMetaData.id);
        } else {
            toast('Error downloading file', { type: 'error' });
        }
    };
    const handleDeleteFile = () => {
        if (inputFileRef.current) {
            inputFileRef.current.value = '';
        }
        setFileMetadata({ ...fileMetaData, name: undefined, size: undefined, type: undefined, url: undefined });
    };
    const getFilePreview = () => {
        return (
            <div className="flex w-full space-x-2">
                <div className="p1 flex w-full justify-between items-center rounded bg-blue-200 py-2 px-3 cursor-pointer" onClick={downloadFormFile}>
                    <p>{fileMetaData?.name}</p>
                    <p className="text-sm">{fileMetaData?.size} MB</p>
                </div>

                {enabled && (
                    <div className="items-center justify-center rounded bg-blue-200 p-2" onClick={handleDeleteFile}>
                        <Image src={deleteImg} alt="delete-icon" />
                    </div>
                )}
            </div>
        );
    };

    return (
        <div className="space-y-3 w-[541px]">
            {(!ans?.file_metadata || enabled) && (
                <div
                    tabIndex={0}
                    className={`flex flex-col  items-center justify-center space-y-3 rounded border border-dashed border-black-600 bg-black-200 py-10 focus-visible:!outline-none ${isDragging && enabled ? 'border-blue-500' : ''}`}
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                >
                    <label htmlFor={`${fileMetaData.id}-file-input`} className="flex cursor-pointer items-center space-x-2 rounded border bg-white py-2 px-3 hover:bg-gray-50">
                        <Image alt="file-upload-img" src={fileUploadImg} width={24} height={24} />
                        <span className="text-sm font-semibold leading-5 text-black-900">Upload File</span>
                    </label>
                    {enabled && <input ref={inputFileRef} type="file" id={`${fileMetaData.id}-file-input`} className="hidden" onChange={handleFileInputChange} />}
                    <div className="flex w-full flex-col items-center space-y-2 text-xs text-black-800">
                        <span className="font-semibold leading-4">{isDragging ? 'Release to drop' : 'Or drag here'}</span>
                        <span className="text-center leading-5">
                            Media supported: Images, PDF, Videos, Audios, File <span className="block">Max size limit: 25 MB</span>
                        </span>
                    </div>
                </div>
            )}
            {fileMetaData.name && getFilePreview()}
        </div>
    );
}
