import React, { useState } from 'react';

import CheckBox from '@Components/Common/Input/CheckBox';

type ConsentType = 'info' | 'checkbox';

interface ConsentFieldProps {
    title?: string;
    description?: string;
    type?: ConsentType;
    required?: boolean;
    checked?: boolean;
}
export default function ConsentField({ title = '', description = '', type = 'checkbox', required = false, checked = false }: ConsentFieldProps) {
    const [isChecked, setIsChecked] = useState(checked);

    const handleCheckSelection = (event: any, checked: boolean) => {
        setIsChecked(checked);
    };
    return (
        <div className="space-y-2 p-5 border-b border-new-black-300">
            <div className="flex space-x-2 items-center">
                {type === 'checkbox' && <CheckBox className="!m-0" checked={isChecked} onChange={handleCheckSelection} />}
                <div className="h6-new">
                    {title} {required && <span className="ml-2 text-new-pink">*</span>}
                </div>
            </div>

            {description !== '' && (
                <div className="space-y-2">
                    <p className="p2">{description}</p>
                </div>
            )}
        </div>
    );
}
