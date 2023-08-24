import { atom, useAtom } from 'jotai';

interface FileAtom {
    fileId: string;
    fieldId: string;
    fileName: string;
    file: File;
}
const filesAtom = atom<FileAtom[]>([]);

export default function useFormAtom() {
    const [files, setFiles] = useAtom(filesAtom);

    const addFile = (fieldId: string, fileId: string, fileName: string, file: File) => {
        setFiles([...files, { fieldId, fileId, fileName, file }]);
    };
    const resetFormFiles = () => {
        setFiles([]);
    };
    return { files, addFile, resetFormFiles };
}
