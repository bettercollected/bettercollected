import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';

import { FileMetadata } from '@app/models/types/fileTypes';

export const generateFileUrl = (file: File) => {
    const fileUrl = URL.createObjectURL(file);
    return fileUrl;
};

export const generateFileMetaData = (file: File, fileId?: string): FileMetadata => {
    const fileUrl = generateFileUrl(file);
    const fileSizeInMB = parseFloat((file.size / (1024 * 1024)).toFixed(2));
    return { id: fileId ?? uuidv4(), name: file.name, size: fileSizeInMB, type: file.type, url: fileUrl };
};

export async function downloadFile(fileUrl: string, fileName: string) {
    const response = await fetch(fileUrl);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(new Blob([blob]));
    const link = document.createElement('a');
    link.href = url;
    link.setAttribute('download', fileName);
    document.body.appendChild(link);
    link.click();
    link.parentNode!.removeChild(link);
    return true;
}
