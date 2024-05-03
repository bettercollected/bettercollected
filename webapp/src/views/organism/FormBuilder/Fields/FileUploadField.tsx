import { StandardFormFieldDto } from '@app/models/dtos/form';
import { useFormState } from '@app/store/jotai/form';
import { FolderUploadIcon } from '@app/views/atoms/Icons/FolderUploadIcon';

const FileUpload = ({ field, slide, disabled }: { field: StandardFormFieldDto; slide: StandardFormFieldDto; disabled: boolean }) => {
    const { theme } = useFormState();

    const handleFileInputChange = (event: any) => {
        const file = event.target.files[0];
        if (file.size > 26214400) alert('Size greater than 25MB.');
    };
    return (
        <>
            <label
                htmlFor="form-builder-file-upload"
                style={{
                    borderColor: slide.properties?.theme?.tertiary || theme?.tertiary
                }}
                className={'flex h-[200px] w-full max-w-[800px] cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dotted'}
            >
                <FolderUploadIcon
                    style={{
                        color: slide.properties?.theme?.secondary || theme?.secondary
                    }}
                />
                <div style={{ color: theme?.secondary }} className={'flex flex-col items-center gap-1'}>
                    <span className={'text-base font-semibold'}>Choose your file or drag file</span>
                    <span className={'text-[12px]'}>Max size limit: 25 MB</span>
                </div>
            </label>
            <input type="file" id="form-builder-file-upload" className={'hidden'} onChange={handleFileInputChange} />
        </>
    );
};

export default FileUpload;
