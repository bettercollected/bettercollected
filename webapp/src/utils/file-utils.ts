import { v4 as uuidv4 } from 'uuid';

import { FileMetadata } from '@app/models/types/file-types';

export const generateFileUrl = (file: File) => {
    const fileUrl = URL.createObjectURL(file);
    return fileUrl;
};

export const generateFileMetaData = (file: File, fileId?: string): FileMetadata => {
    const fileUrl = generateFileUrl(file);
    const fileSizeInMB = parseFloat((file.size / (1024 * 1024)).toFixed(2));
    return { id: fileId ?? uuidv4(), name: file.name, size: fileSizeInMB, type: file.type, url: fileUrl };
};

/**
 * Fetches a file (the server's short-lived signed link) and saves it. Throws
 * when the link answers with an error (an expired link, a refused one), so
 * the caller says so instead of saving the error page as the file.
 */
export async function downloadFile(fileUrl: string, fileName: string) {
    const response = await fetch(fileUrl);
    if (!response.ok) throw new Error(`Download failed (${response.status})`);
    const blob = await response.blob();
    const url = window.URL.createObjectURL(new Blob([blob]));
    try {
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', fileName);
        document.body.appendChild(link);
        link.click();
        link.parentNode?.removeChild(link);
    } finally {
        // the click has started the save; the object URL is not needed after it
        setTimeout(() => window.URL.revokeObjectURL(url), 1000);
    }
    return true;
}

// Sizes are stored in MB with two decimals, so anything under ~5 KB is 0.
export function formatFileSizeMb(sizeMb?: number): string {
    if (sizeMb === undefined || sizeMb === null || Number.isNaN(sizeMb)) return '';
    if (sizeMb < 0.01) return '< 10 KB';
    if (sizeMb < 1) return `${Math.round(sizeMb * 1024)} KB`;
    return `${sizeMb} MB`;
}
