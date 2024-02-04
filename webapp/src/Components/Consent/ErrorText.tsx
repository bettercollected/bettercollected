import React from 'react';

import ErrorIcon from '@mui/icons-material/Error';

interface ErrorTextProps {
    text: string;
}

export default function ErrorText({ text }: ErrorTextProps) {
    return (
        <div className="p2 !text-new-pink items-center !font-normal mb-3">
            <span className="mr-2">
                <ErrorIcon />
            </span>
            {text}
        </div>
    );
}