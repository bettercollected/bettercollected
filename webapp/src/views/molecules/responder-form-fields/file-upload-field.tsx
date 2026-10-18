import { useEffect, useRef, useState } from 'react';

import { useToast } from '@app/shadcn/components/ui/use-toast';
import styled from 'styled-components';
import { v4 } from 'uuid';

import { StandardFormFieldDto } from '@app/models/dtos/form';
import { FileMetadata } from '@app/models/types/field-types';
import { useFormState } from '@app/store/jotai/form';
import useFormAtom from '@app/store/jotai/form-file';
import { useFormResponse } from '@app/store/jotai/responder-form-response';
import { useResponderState } from '@app/store/jotai/responder-form-state';
import { downloadFile, formatFileSizeMb, generateFileMetaData } from '@app/utils/file-utils';
import DeleteIcon from '@Components/icons/delete';
import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';

/** Largest file a respondent can upload, in MB. */
const MAX_FILE_MB = 25;
import { FolderUploadIcon } from '@Components/icons/folder-upload-icon';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { scrollToDivById } from '@app/utils/scroll-utils';
import { WithQuestionLabel } from './question-label-context';
import QuestionWrapper from './question-wrapper';

const StyledLabel = styled.label<{ $theme: any }>(({ $theme }) => {
    const secondaryColor = $theme?.secondary;
    return {
        '&:hover': {
            borderColor: secondaryColor + '!important'
        }
    };
});

export default function FileUpload({ field }: { field: StandardFormFieldDto }) {
    const { toast } = useToast();
    const { t } = useRespondentLanguage();
    const { formResponse, addFieldFileAnswer, removeAnswer } = useFormResponse();
    const { theme } = useFormState();

    const form = useAppSelector(selectForm);
    const { currentSlide } = useResponderState();

    const [isDragging, setIsDragging] = useState(false);
    const hintId = `file-hint-${field.id}`;
    const inputFileRef = useRef<HTMLInputElement | null>(null);
    const { addFile, resetFormFiles } = useFormAtom();
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
        if (fMetaData.size! > MAX_FILE_MB) {
            toast({ description: t('FILE.TOO_LARGE', { size: MAX_FILE_MB }), variant: 'destructive' });
            return;
        }
        setFileMetadata({ ...fMetaData });
        addFile(field.id, fMetaData.id, fMetaData.name!, file);
        addFieldFileAnswer(field.id, { ...fMetaData });
        setTimeout(() => {
            if (form?.fields?.[currentSlide]?.properties?.fields?.length !== field.index + 1) scrollToDivById(form?.fields?.[currentSlide]?.properties?.fields?.[field.index + 1]?.id);
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
            toast({ description: t('FILE.DOWNLOAD_ERROR'), variant: 'destructive' });
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
        resetFormFiles();
        removeAnswer(field.id);
    };
    const getFilePreview = () => {
        return (
            <div className="flex w-full space-x-2">
                {/* Tinted fill + ink text — a solid tertiary block under ink text is
                    the same legibility defect the yes/no chips had. */}
                <div style={{ backgroundColor: theme?.tertiary + '55', color: theme?.primary }} className="p1 flex w-full cursor-pointer items-center justify-between rounded-[4px] px-3 py-2" onClick={downloadFormFile}>
                    <p className="mr-5 flex-1 truncate">{fileMetaData?.name}</p>
                    <p className="text-sm">{formatFileSizeMb(fileMetaData?.size)}</p>
                </div>

                <button
                    type="button"
                    aria-label={t('FILE.REMOVE')}
                    style={{
                        backgroundColor: theme?.tertiary + '55',
                        color: theme?.primary
                    }}
                    className="items-center justify-center rounded-[4px] p-2"
                    onClick={handleDeleteFile}
                >
                    <DeleteIcon />
                </button>
            </div>
        );
    };

    return (
        <QuestionWrapper field={field}>
            <div className="w-full space-y-3 md:max-w-[800px]">
                {
                    <StyledLabel
                        onDragEnter={handleDragEnter}
                        onDragLeave={handleDragLeave}
                        onDragOver={handleDragOver}
                        onDrop={handleDrop}
                        $theme={theme}
                        style={{
                            borderColor: isDragging ? theme?.secondary : theme?.tertiary,
                            ['--file-focus' as string]: theme?.secondary ?? '#1649E2'
                        }}
                        htmlFor={`${fileMetaData.id}-file-input`}
                        // The file input inside is the control (focusable, named by the
                        // question); the drop zone shows its focus.
                        className="flex cursor-pointer items-center justify-center space-x-2 relative rounded-md border border-dashed px-3 py-2 focus-within:ring-2 focus-within:ring-(--file-focus) focus-within:ring-offset-2"
                    >
                        <div className={`flex w-full flex-col items-center justify-center space-y-3  py-10 `}>
                            <FolderUploadIcon
                                style={{
                                    color: theme?.secondary
                                }}
                            />
                            <WithQuestionLabel hints={[hintId]}>
                                {({ control }) => (
                                    <input
                                        ref={inputFileRef}
                                        type="file"
                                        id={`${fileMetaData.id}-file-input`}
                                        className="sr-only"
                                        onChange={handleFileInputChange}
                                        {...control}
                                    />
                                )}
                            </WithQuestionLabel>
                            <div id={hintId} style={{ color: theme?.secondary }} className="flex w-full flex-col items-center space-y-2 text-sm ">
                                <span className="font-semibold leading-4">{isDragging ? t('FILE.RELEASE') : t('FILE.CHOOSE')}</span>
                                <span className="text-center text-xs leading-5">
                                    <span className="block">{t('FILE.MAX_SIZE', { size: MAX_FILE_MB })}</span>
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
