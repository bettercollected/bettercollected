import React from 'react';

import Image from "next/legacy/image";

import { Loader2 } from 'lucide-react';

import GoogleFolder from '@app/assets/images/google_folder.png';


interface ImportFormLoadingProps {
    loadingText: string;
    formTitle: string;
}

export default function ImportFormLoading({ loadingText, formTitle }: ImportFormLoadingProps) {
    return (
        <div className="flex flex-col h-full min-h-[480px] md:min-h-[480px] md:w-[777px] lg:w-[1052px] lg:h-[650px] justify-center items-center">
            <Image className={'pb-1'} src={GoogleFolder} alt={'GoogleFolder'} />
            <div className=" h3-new mt-4">{loadingText}</div>
            <div className=" mt-2">{formTitle}</div>
            <Loader2 className="mt-12 h-12 w-12 animate-spin text-primary" />
        </div>
    );
}