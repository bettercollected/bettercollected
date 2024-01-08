import React from 'react';

import Image from 'next/image';

import { CircularProgress } from '@mui/material';

import GoogleFolder from '@app/assets/images/google_folder.png';

interface ImportFormLoadingProps {
    loadingText: string;
    formTitle: string;
}

export default function ImportFormLoading({ loadingText, formTitle }: ImportFormLoadingProps) {
    return (
        <div className="flex flex-col h-full justify-center items-center">
            <Image className={'pb-1'} src={GoogleFolder} alt={'GoogleFolder'} />
            <div className=" h3-new mt-4">{loadingText}</div>
            <div className=" mt-2">{formTitle}</div>
            <CircularProgress size={48} className="mt-12" />
        </div>
    );
}
