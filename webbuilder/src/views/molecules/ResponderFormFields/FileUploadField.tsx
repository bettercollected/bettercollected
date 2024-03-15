import { useRef, useState } from 'react';

import Image from 'next/image';

import { toast } from 'react-toastify';
import { v4 } from 'uuid';

import { FormField } from '@app/models/dtos/form';
import { FileMetadata } from '@app/models/types/fieldTypes';
import { useFormState } from '@app/store/jotai/form';
import useFormAtom from '@app/store/jotai/formFile';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { downloadFile, generateFileMetaData } from '@app/utils/fileUtils';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import { FolderUploadIcon } from '@app/views/atoms/Icons/FolderUploadIcon';

export default function FileUpload({ field }: { field: FormField }) {
    const { formResponse, addFieldFileAnswer } = useFormResponse();
    const { theme } = useFormState();

    const [isDragging, setIsDragging] = useState(false);
    const inputFileRef = useRef<HTMLInputElement | null>(null);
    const { addFile } = useFormAtom();
    const ans = formResponse.answers && formResponse.answers[field.id];
    const [fileMetaData, setFileMetadata] = useState<FileMetadata>(
        ans?.file_metadata ?? { id: v4() }
    );

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
        addFieldFileAnswer(field.id, { ...fMetaData });
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
        try {
            ans?.file_metadata?.url &&
                downloadFile(
                    ans?.file_metadata?.url,
                    fileMetaData.name ?? fileMetaData.id
                );
        } catch (err) {
            toast('Error downloading file', { type: 'error' });
        }
    };
    const handleDeleteFile = () => {
        if (inputFileRef.current) {
            inputFileRef.current.value = '';
        }
        setFileMetadata({
            ...fileMetaData,
            name: undefined,
            size: undefined,
            type: undefined,
            url: undefined
        });
    };
    const getFilePreview = () => {
        return (
            <div className="flex w-full space-x-2">
                <div
                    className="p1 flex w-full cursor-pointer items-center justify-between rounded bg-blue-200 px-3 py-2"
                    onClick={downloadFormFile}
                >
                    <p className="mr-5 flex-1 truncate">{fileMetaData?.name}</p>
                    <p className="text-sm">{fileMetaData?.size} MB</p>
                </div>

                <div
                    className="items-center justify-center rounded bg-blue-200 p-2"
                    onClick={handleDeleteFile}
                >
                    <DeleteIcon />
                </div>
            </div>
        );
    };

    return (
        <div className="w-full space-y-3 md:w-[541px]">
            {!ans?.file_metadata && (
                <div
                    tabIndex={0}
                    className={`flex flex-col  items-center justify-center space-y-3 rounded border border-dashed border-black-600 bg-black-200 py-10 focus-visible:!outline-none ${isDragging ? 'border-blue-500' : ''}`}
                    onDragEnter={handleDragEnter}
                    onDragLeave={handleDragLeave}
                    onDragOver={handleDragOver}
                    onDrop={handleDrop}
                >
                    <label
                        htmlFor={`${fileMetaData.id}-file-input`}
                        className="flex cursor-pointer items-center space-x-2 rounded border bg-white px-3 py-2 hover:bg-gray-50"
                    >
                        <FolderUploadIcon
                            style={{
                                color: theme?.secondary
                            }}
                        />
                        <span className="text-sm font-semibold leading-5 text-black-900">
                            Upload File
                        </span>
                    </label>
                    <input
                        ref={inputFileRef}
                        type="file"
                        id={`${fileMetaData.id}-file-input`}
                        className="hidden"
                        onChange={handleFileInputChange}
                    />
                    <div className="flex w-full flex-col items-center space-y-2 text-xs text-black-800">
                        <span className="font-semibold leading-4">
                            {isDragging ? 'Release to drop' : 'Or drag here'}
                        </span>
                        <span className="text-center leading-5">
                            Media supported: Images, PDF, Videos, Audios, File{' '}
                            <span className="block">Max size limit: 25 MB</span>
                        </span>
                    </div>
                </div>
            )}
            {fileMetaData.name && getFilePreview()}
        </div>
    );
}
