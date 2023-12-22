import React, { useEffect } from 'react';

import CheckedCircle from '@Components/Common/Icons/Common/CheckedCircle';

import FormSettingsTab from '@app/components/dashboard/form-settings';
import { resetSingleForm } from '@app/store/forms/slice';
import { useAppDispatch } from '@app/store/hooks';

export default function ChangeSlugComponent() {
    const dispatch = useAppDispatch();
    useEffect(() => {
        return () => {
            dispatch(resetSingleForm());
        };
    }, []);

    return (
        <>
            <div className="flex gap-4 mb-[72px]">
                <CheckedCircle />
                <span className="h3-new text-black-900">Form Imported Successfully!</span>
            </div>
            <FormSettingsTab view="LINKS" />
        </>
    );
}
