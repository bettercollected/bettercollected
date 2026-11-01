import useRespondentLanguage from '@app/lib/hooks/use-respondent-language';
import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { FolderUploadIcon } from '@Components/icons/folder-upload-icon';

const FileUpload = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { theme } = useFormState();
    // what respondents see, in their language (as the rest of this preview)
    const { t: tr } = useRespondentLanguage();

    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert(tr('FILE.TOO_LARGE', { size: 25 }));
    };
    return (
        <>
            <label
                htmlFor="form-builder-file-upload"
                style={{
                    borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                }}
                className={'flex h-[200px] w-full max-w-[800px] cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dotted'}
            >
                <FolderUploadIcon
                    style={{
                        color: slide.properties?.theme?.secondary || theme?.secondary
                    }}
                />
                <div style={{ color: theme?.secondary }} className={'flex flex-col items-center gap-1'}>
                    <span className={'text-base font-semibold'}>{tr('FILE.CHOOSE')}</span>
                    <span className={'text-[12px]'}>{tr('FILE.MAX_SIZE', { size: 25 })}</span>
                </div>
            </label>
            <input type="file" id="form-builder-file-upload" className={'hidden'} onChange={handleFileInputChange} />
        </>
    );
};

export default FileUpload;
