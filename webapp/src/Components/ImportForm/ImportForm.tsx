import React from "react";
import GoogleFolder from "@app/assets/images/google_folder.png";
import Image from 'next/image';
import AppTextField from "@Components/Common/Input/AppTextField";
import {LinkIcon} from "@app/components/icons/link-icon";
import GoogleForm from "@app/assets/images/google_form.png";

const ImportForm = () => {
    return <div className={'flex flex-col items-center gap-4 md:w-[500px]'}>
        <Image className={'pb-1'} src={GoogleFolder} alt={'GoogleFolder'}/>
        <h1 className={'h3-new !text-black-800'}>Import Google Form <span className={'!text-pink-500'}> From URL</span></h1>
        <h4 className={'body4 !text-black-700  text-center pb-6'}>Use the editing URL directly from the top of the Google browser bar, not the shared form link.</h4>
        <AppTextField placeholder={'Paste URL'} className={'w-full pb-14'} icon={<LinkIcon/>}/>
        <Image  src={GoogleForm} alt={'GoogleForm'}/>
    </div>
}

export default ImportForm