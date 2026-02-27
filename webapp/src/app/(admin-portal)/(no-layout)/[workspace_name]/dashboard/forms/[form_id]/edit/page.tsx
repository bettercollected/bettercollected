'use client';

import { selectForm } from '@app/store/forms/slice';
import { useAppSelector } from '@app/store/hooks';
import FullScreenLoader from '@Components/ui/fullscreen-loader';
import FormEditPage from './_components/form-edit-page';

export default function FormPage(props: { params: Promise<{ form_id: string }> }) {

    const standardForm: any = useAppSelector(selectForm);

    if (!standardForm.formId) {
        return <FullScreenLoader />
    }

    return (
        <FormEditPage params={props.params} />
    );
}
