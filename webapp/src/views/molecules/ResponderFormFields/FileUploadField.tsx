import { useEffect, useRef, useState } from 'react';

import { toast } from 'react-toastify';
import styled from 'styled-components';
import { v4 } from 'uuid';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FileMetadata } from '@app/models/types/fieldTypes';
import { useFormState } from '@app/store/jotai/form';
import useFormAtom from '@app/store/jotai/formFile';
import { useFormResponse } from '@app/store/jotai/responderFormResponse';
import { useResponderState } from '@app/store/jotai/responderFormState';
import { downloadFile, generateFileMetaData } from '@app/utils/fileUtils';
import DeleteIcon from '@app/views/atoms/Icons/Delete';
import { FolderUploadIcon } from '@app/views/atoms/Icons/FolderUploadIcon';

import QuestionWrapper from './QuestionQwrapper';

const StyledLabel = styled.label<{ $theme: any }>(({ $theme }) => {
    const secondaryColor = $theme?.secondary;
    return {
        '&:hover': {
            borderColor: secondaryColor + '!important'
        }
    };
});

export default function FileUpload({ field }: { field: StandardFormFieldDto }) {
    const { formResponse, addFieldFileAnswer } = useFormResponse();
    const { theme } = useFormState();
    const { nextField } = useResponderState();

    const [isDragging, setIsDragging] = useState(false);
    const inputFileRef = useRef<HTMLInputElement | null>(null);
    const { addFile } = useFormAtom();
    const ans = formResponse.answers && formResponse.answers[field.id];
    const [fileMetaData, setFileMetadata] = useState<FileMetadata>(ans?.file_metadata ?? { id: v4() });
    useEffect(() => {
        formResponse.answers && setFileMetadata(formResponse.answers[field.id]?.file_metadata ?? { id: v4() });
    }, [formResponse.answers]);

    const handleDragEnter = (event: any) => {
        // event.preventDefault();
        setIsDragging(true);
    };

    const handleDragLeave = () => {
        setIsDragging(false);
    };

    const handleDragOver = (event: any) => {
        // event.preventDefault();
        setIsDragging(true);
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
        setTimeout(() => {
            nextField();
        }, 200);
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
            ans?.file_metadata?.url && downloadFile(ans?.file_metadata?.url, fileMetaData.name ?? fileMetaData.id);
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
                <div style={{ backgroundColor: theme?.tertiary }} className="p1 flex w-full cursor-pointer items-center justify-between rounded px-3 py-2" onClick={downloadFormFile}>
                    <p className="mr-5 flex-1 truncate">{fileMetaData?.name}</p>
                    <p className="text-sm">{fileMetaData?.size} MB</p>
                </div>

                <div
                    style={{
                        backgroundColor: theme?.tertiary,
                        color: theme?.primary
                    }}
                    className="items-center justify-center rounded p-2"
                    onClick={handleDeleteFile}
                >
                    <DeleteIcon />
                </div>
            </div>
        );
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-3 md:max-w-[800px]">
                {
                    <StyledLabel
                        tabIndex={0}
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        $theme={theme}
                        style={{
                            borderColor: isDragging ? theme?.secondary : theme?.tertiary
                        }}
                        htmlFor={`${fileMetaData.id}-file-input`}
                        className="flex cursor-pointer items-center justify-center space-x-2  rounded-2xl border border-dashed px-3  py-2 "
                    >
                        <div className={`flex w-full flex-col items-center justify-center space-y-3  py-10 `}>
                            <FolderUploadIcon
                                style={{
                                    color: theme?.secondary
                                }}
                            />
                            <input ref={inputFileRef} type="file" id={`${fileMetaData.id}-file-input`} className="hidden" onChange={handleFileInputChange} />
                            <div style={{ color: theme?.secondary }} className="flex w-full flex-col items-center space-y-2 text-sm ">
                                <span className="font-semibold leading-4">{isDragging ? 'Release to drop' : 'Choose your file or drag file'}</span>
                                <span className="text-center text-xs leading-5">
                                    <span className="block">Max size limit: 25 MB</span>
                                </span>
                            </div>
                        </div>
                    </StyledLabel>
                }
                {fileMetaData.name && getFilePreview()}
            </div>
        </QuestionWrapper>
    );
}
