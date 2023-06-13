import React from 'react';

import { useTranslation } from 'next-i18next';

import UserDetails from '@Components/Common/DataDisplay/UserDetails';
import Share from '@Components/Common/Icons/Share';

import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import { formConstant } from '@app/constants/locales/form';
import { StandardFormDto } from '@app/models/dtos/form';
import { selectIsAdmin, selectIsProPlan } from '@app/store/auth/slice';
import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import { selectWorkspace } from '@app/store/workspaces/slice';
import { parseDateStrToDate, toMonthDateYearStr, utcToLocalDate } from '@app/utils/dateUtils';
import { getFormUrl } from '@app/utils/urlUtils';

import { useModal } from '../modal-views/context';

export default function FormPreview() {
    const isAdmin = useAppSelector(selectIsAdmin);
    const isProPlan = useAppSelector(selectIsProPlan);
    const workspace = useAppSelector(selectWorkspace);
    const form = useAppSelector(selectForm);
    const { t } = useTranslation();
    const { openModal } = useModal();
    return (
        <div className="flex md:flex-row flex-col-reverse gap-10  w-full   ">
            <FormTabContent form={form} />
            {isAdmin && !isProPlan ? (
                <></>
            ) : (
                <div className="flex flex-col gap-6 w-full">
                    <div
                        onClick={() =>
                            openModal('SHARE_VIEW', {
                                url: getFormUrl(form, workspace),
                                title: t(formConstant.shareThisForm)
                            })
                        }
                        className=" cursor-pointer items-center  flex gap-[10px]"
                    >
                        <Share className="h-4 w-4  !text-brand-500" />
                        <span className="body6 !text-brand-500">Share Form</span>
                    </div>
                    <div className="flex gap-4 items-center">
                        <div className="body4 text-black-700 ">{t(formConstant.importedBy)}:</div>
                        <UserDetails user={form.importerDetails} />
                    </div>
                    <div className="flex gap-4 items-center">
                        <div className="body4 text-black-700">{t(formConstant.importedOn)}:</div>
                        <div className="body4">{toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(form.createdAt)))}</div>
                    </div>
                </div>
            )}
        </div>
    );
}
