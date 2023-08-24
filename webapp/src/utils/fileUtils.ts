import { uuidv4 } from '@mswjs/interceptors/lib/utils/uuid';
import { parseNumber } from 'libphonenumber-js';

import { FileMetaData } from '@app/models/types/fileTypes';

export const generateFileUrl = (file: File) => {
    const fileUrl = URL.createObjectURL(file);
    return fileUrl;
};

export const generateFileMetaData = (file: File, fileId?: string): FileMetaData => {
    const fileUrl = generateFileUrl(file);
    const fileSizeInMB = parseFloat((file.size / (1024 * 1024)).toFixed(2));
    return { id: fileId ?? uuidv4(), name: file.name, size: fileSizeInMB, type: file.type, url: fileUrl };
};
