import React from 'react';

import { useTranslation } from 'next-i18next';

import UserDetails from '@Components/Common/DataDisplay/UserDetails';

import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import FormPageLayout from '@app/components/sidebar/form-page-layout';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormDto } from '@app/models/dtos/form';
import Error from '@app/pages/_error';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { useAppSelector } from '@app/store/hooks';
import { parseDateStrToDate, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';

export default function FormPage(props: any) {
    const { form }: { form: StandardFormDto } = props;
    const { t } = useTranslation();

    const isAdmin = useAppSelector(selectIsAdmin);
    const isProPlan = useAppSelector(selectIsProPlan);

    if (!props && Object.keys(props).length === 0) {
        return <Error />;
    }

    return (
        <FormPageLayout {...props}>
            <div className=" max-w-[700px] container mx-auto px-6 md:px-0">
                {isAdmin && !isProPlan ? (
                    <></>
                ) : (
                    <div className="flex justify-between mb-5">
                        <div>
                            <div className="body6 mb-5 !font-semibold">{t(formConstant.importedBy)}:</div>
                            <UserDetails user={form.importerDetails} />
                        </div>
                        <div>
                            <div className="body6 mb-5 !font-semibold">{t(formConstant.importedOn)}:</div>
                            <div className="body4">{toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(form.createdAt)))}</div>
                        </div>
                    </div>
                )}
                <FormTabContent form={form} />
            </div>
        </FormPageLayout>
    );
}
export { getServerSidePropsForDashboardFormPage as getServerSideProps } from '@app/lib/serverSideProps';
