import React from 'react';

import {useTranslation} from 'next-i18next';
import {NextSeo} from 'next-seo';
import {WorkspaceDto} from '@app/models/dtos/workspaceDto';
import {useAppSelector} from '@app/store/hooks';
import {selectWorkspace} from '@app/store/workspaces/slice';
import Layout from "@app/layouts/_layout";
import {ChevronForward} from "@app/components/icons/chevron-forward";
import {useRouter} from "next/router";
import ImportForm from '@Components/ImportForm/ImportForm';

export default function ImportFormPage({workspace, hasCustomDomain}: {
    workspace: WorkspaceDto;
    hasCustomDomain: boolean
}) {
    const {t} = useTranslation();
    const {title} = useAppSelector(selectWorkspace);
    const [mobileOpen, setMobileOpen] = React.useState(false);
    const router = useRouter();
    const handleDrawerToggle = () => {
        setMobileOpen(!mobileOpen);
    };

    const handleClickBack = () => {
        router.back();
    }

    return (
        <Layout showNavbar={true} className="!p-0 bg-white flex flex-col min-h-screen">
            <NextSeo title={'Import-form | ' + title} noindex={true} nofollow={true}/>
            <div className={'flex flex-col gap-11'}>
                <div className="flex w-fit items-center gap-1 px-2 md:px-5 pt-2 cursor-pointer"
                     onClick={handleClickBack}>
                    <ChevronForward className=" rotate-180 h-6 w-6 p-[2px] "/>
                    <p className={'text-sm text-black-700 font-normal'}>{t('BUTTON.BACK')}</p>
                </div>
                <div className={'flex flex-col items-center'}>
                    <ImportForm/>
                </div>
            </div>
        </Layout>
    );
}

export {getAuthUserPropsWithWorkspace as getServerSideProps} from '@app/lib/serverSideProps';

