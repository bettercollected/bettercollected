/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 16:07
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useState } from 'react';

export default function FormInput(props: any) {
    const { label, placeholder, id, handleChange } = props;

    const [validInputFormat, setValidInputFormat] = useState<any>(undefined);

    const checkValidation = (fieldValue: any) => {
        if (id === 'email') {
            const pattern = /^\w+@[a-zA-Z_]+?\.[a-zA-Z]{2,3}$/;
            if (!!fieldValue.match(pattern)) {
                setValidInputFormat(true);
            } else {
                setValidInputFormat(false);
            }
        }
        handleChange(id, fieldValue);
    };

    const renderValidationMessage = () => (validInputFormat ? <span className={'pl-2.5 text-green-600'}>Valid Input</span> : <span className={'pl-2.5 text-red-600'}>Invalid input</span>);

    return (
        <div className={'flex flex-col mb-4'}>
            <label className={'block text-gray-700 text-sm font-normal mb-2'} htmlFor={id}>
                {id === 'email' && !!label ? `${label}*` : label}
            </label>
            <input className="border text-gray-900 text-sm rounded-lg w-full p-2.5" id={'email'} type="text" placeholder={placeholder} onChange={(e) => checkValidation(e.target.value)} />
            {validInputFormat !== undefined && renderValidationMessage()}
        </div>
    );
}
