import React from 'react';

import { useTranslation } from 'next-i18next';
import { useRouter } from 'next/router';

import UserDetails from '@Components/Common/DataDisplay/UserDetails';
import EditIcon from '@Components/Common/Icons/Edit';
import ShareIcon from '@Components/Common/Icons/ShareIcon';
import Button from '@Components/Common/Input/Button';

import { FormTabContent } from '@app/components/dashboard/form-tab-content';
import { formConstant } from '@app/constants/locales/form';
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
    const router = useRouter();
    return (
        <div className="flex lg:flex-row flex-col-reverse gap-10  w-full   ">
            <FormTabContent form={form} />
            {/* <div className="flex gap-4">
                    {form?.settings?.provider === 'self' && (
                        <Button
                            variant="contained"
                            className="w-fit bg-brand-500 px-8 gap-2 py-3 "
                            onClick={() => {
                                router.push(`/${workspace.workspaceName}/dashboard/forms/${form.formId}/edit`);
                            }}
                        >
                            <span>
                                <EditIcon />
                            </span>
                            Edit
                        </Button>
                    )}
                    <Button
                        variant="outlined"
                        className="w-fit text-brand-500 px-8 gap-2 py-3 "
                        onClick={() =>
                            openModal('SHARE_VIEW', {
                                url: getFormUrl(form, workspace),
                                title: t(formConstant.shareThisForm)
                            })
                        }
                    >
                        <span>
                            <ShareIcon />
                        </span>
                        Share
                    </Button>
                </div> */}
            {/* {isAdmin && isProPlan && (
                <div className="flex flex-col lg:basis-1/4 gap-6 w-full">
                    <div className="flex gap-4 items-center">
                        <div className="body4 text-black-700 ">{t(formConstant.importedBy)}:</div>
                        <UserDetails user={form.importerDetails} />
                    </div>
                    <div className="flex gap-4 items-center">
                        <div className="body4 text-black-700">{t(formConstant.importedOn)}:</div>
                        <div className="body4">{toMonthDateYearStr(parseDateStrToDate(utcToLocalDate(form.createdAt)))}</div>
                    </div>
                </div>
            )} */}
        </div>
    );
}
