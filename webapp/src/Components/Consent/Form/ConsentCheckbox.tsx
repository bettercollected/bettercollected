import React from 'react';

import { CheckBox } from '@mui/icons-material';

interface ConsentCheckBoxProps {
    text: string;
    details?: string;
    required?: boolean;
}
export default function ConsentCheckbox({ text, details, required = false }: ConsentCheckBoxProps) {
    return (
        <div className="space-y-2 p-5 border-y border-new-black-300">
            <div className="flex space-x-2">
                <CheckBox sx={{ color: '#0764EB' }} />
                <div className="h6-new">
                    {text} {required && <span className="ml-2 text-new-pink">*</span>}
                </div>
            </div>

            {details && (
                <div className="space-y-2">
                    <p className="p2">{details}</p>
                </div>
            )}
        </div>
    );
}
