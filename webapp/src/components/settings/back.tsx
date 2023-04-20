import React from 'react';

import { useRouter } from 'next/router';

import { ChevronLeft } from '@mui/icons-material';

export default function BackButton() {
    const router = useRouter();

    const handleBackClick = async () => {
        await router.back();
    };
    return (
        <div className="paragraph text-black-900 cursor-pointer" onClick={handleBackClick}>
            <ChevronLeft />
            <span className="ml-2">Back</span>
        </div>
    );
}
