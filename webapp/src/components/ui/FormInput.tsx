/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-17
 * Time: 16:07
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useEffect, useState } from 'react';

export default function FormInput(props: any) {
    const { value, placeholder, onChange, handleValidation, inputFieldType } = props;

    const [validInputFormat, setValidInputFormat] = useState<any>(false);

    useEffect(() => {
        handleValidation(validInputFormat);
    }, [validInputFormat]);

    const checkValidation = (e: any) => {
        const fieldValue = e.target.value.toLowerCase();

        const pattern = /^\w+([\.-]?\w+)*@\w+([\.-]?\w+)*(\.\w{2,3})+$/;
        if (!!fieldValue.match(pattern)) {
            setValidInputFormat(true);
        } else {
            setValidInputFormat(false);
        }
        onChange(e);
    };

    return (
        <div className={'flex items-center mb-4 w-60 mx-auto !rounded-[1px] !h-[50px]'}>
            <input
                data-testid="form-input"
                className={`border-solid ${value?.length !== 0 ? (validInputFormat ? '!border-green-500' : '!border-red-500') : ''} w-60 mx-auto !rounded-[1px] !h-[50px] text-gray-900 p-2.5 text-sm`}
                value={value}
                type="text"
                placeholder={placeholder}
                onChange={(e) => checkValidation(e)}
            />
        </div>
    );
}
