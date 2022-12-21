import React from 'react';

import Link from 'next/link';

export const FormTabContent = ({ formId }: { formId: string }) => (
    <div className="w-full">
        <div>You can preview the form by clicking the link below.</div>
        <Link href={`/dashboard/forms/preview/${formId}`} target="_blank" referrerPolicy="no-referrer">
            <div className="flex">
                <div className="text-blue-500 hover:underline  cursor-pointer ">Link to preview of form.</div>
                <div className="cursor-pointer">🔗</div>
            </div>
        </Link>
    </div>
);
