import { atom, useAtom } from 'jotai';

interface FileAtom {
    fieldId: string;
    fileId: string;
    fileName: string;
    file: File;
}

const filesAtom = atom<FileAtom[]>([]);

export default function useFormAtom() {
    const [files, setFiles] = useAtom(filesAtom);

    const addFile = (fieldId: string, fileId: string, fileName: string, file: File) => {
        // remove existing file
        const updatedFiles = files.filter((item) => item.fieldId !== fieldId);
        // add new file
        updatedFiles.push({ fieldId, fileId, fileName, file });

        setFiles(updatedFiles);
    };

    // The file of one question only (a drawn signature that was cleared or typed over).
    const removeFile = (fieldId: string) => {
        setFiles(files.filter((item) => item.fieldId !== fieldId));
    };

    const resetFormFiles = () => {
        setFiles([]);
    };

    return { files, addFile, removeFile, resetFormFiles };
}
