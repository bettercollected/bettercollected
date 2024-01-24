import React from 'react';

import { serverSideTranslations } from 'next-i18next/serverSideTranslations';

import BetterCollectedForm from '@Components/Form/BetterCollectedForm';

import { useGetTemplateByIdQuery } from '@app/store/template/api';
import { convertFormTemplateToStandardForm } from '@app/utils/convertDataType';
import { checkHasAdminDomain, getRequestHost } from '@app/utils/serverSidePropsUtils';


export default function TemplatePreview(props: any) {
    const { templateId } = props;
    const { data } = useGetTemplateByIdQuery({
        template_id: templateId
    });
    return <div className="overflow-hidden h-[100vh] max-h-[100v] bg-white">{data && <BetterCollectedForm isDisabled form={convertFormTemplateToStandardForm(data)} />}</div>;
}

export async function getServerSideProps(_context: any) {
    const hasAdminDomain = checkHasAdminDomain(getRequestHost(_context));

    if (!hasAdminDomain) {
        return {
            redirect: {
                path: '/',
                permanent: false
            }
        };
    }
    const { id } = _context.params;
    return {
        props: {
            ...(await serverSideTranslations(_context.locale, ['common', 'builder'], null, ['en', 'nl'])),
            templateId: id
        }
    };
}