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

    // Both update from the files as they are when the update runs, not as this
    // render saw them: a drawing committed after an await must not bring back
    // or drop another question's file.
    const addFile = (fieldId: string, fileId: string, fileName: string, file: File) => {
        // the question's earlier file is replaced
        setFiles((current) => [...current.filter((item) => item.fieldId !== fieldId), { fieldId, fileId, fileName, file }]);
    };

    // The file of one question only (a drawn signature that was cleared or typed over).
    const removeFile = (fieldId: string) => {
        setFiles((current) => current.filter((item) => item.fieldId !== fieldId));
    };

    const resetFormFiles = () => {
        setFiles([]);
    };

    return { files, addFile, removeFile, resetFormFiles };
}
