import Footer from '@Components/CreateForm/Footer';
import QuestionInput from '@Components/CreateForm/QuestionInput';

import { FormFieldState } from '@app/store/create-form/types';

interface IFormFieldProps {
    field: FormFieldState;
}

export default function FormField({ field }: IFormFieldProps) {
    return (
        <div className=" flex flex-1 flex-col p-5 bg-white rounded">
            <div className="flex-grow ">
                <QuestionInput field={field} />
            </div>
            <div className="flex w-full justify-between"></div>
            <Footer fieldId={field.id} deletable={true} type={field.type} />
        </div>
    );
}
