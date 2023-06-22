import AddFieldGrid from '@Components/CreateForm/AddFieldGrid';
import FormField from '@Components/CreateForm/FormField';
import FormProperty from '@Components/CreateForm/FormProperty';
import { Button } from '@mui/material';

import { useFullScreenModal } from '@app/components/modal-views/full-screen-modal-context';
import { selectCreateForm, setFormDescription, setFormTitle } from '@app/store/create-form/slice';
import { FormFieldState, FormState } from '@app/store/create-form/types';
import { useAppSelector } from '@app/store/hooks';

export default function CreateForm() {
    const createForm: FormState = useAppSelector(selectCreateForm);
    const { openModal } = useFullScreenModal();

    return (
        <div className="lg:max-w-[700px]">
            <FormProperty action={setFormTitle} propertyValue={createForm.title} inputProps={{ placeholder: 'Form Title' }} />
            <FormProperty action={setFormDescription} propertyValue={createForm.description} inputProps={{ placeholder: 'Form Description' }} />
            <div className="flex flex-col gap-3">
                {Object.values(createForm.fields).map((field: FormFieldState) => (
                    <FormField key={field.id} field={field} />
                ))}
            </div>

            {Object.keys(createForm.fields).length === 0 ? (
                <>
                    <div>Start your from with</div>
                    <AddFieldGrid />
                </>
            ) : (
                <div className="w-full flex justify-center mt-10">
                    <Button
                        onClick={() => {
                            openModal('ADD_FIELD');
                        }}
                    >
                        Add field
                    </Button>
                </div>
            )}
        </div>
    );
}
