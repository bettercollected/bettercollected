import React from 'react';

import { Archive } from 'lucide-react';

interface IEmptyFormsViewProps {
    description?: string;
    className?: string;
}

export default function EmptyFormsView({ description = '0 Forms', className = '' }: IEmptyFormsViewProps) {
    return (
        <div data-testid="empty-forms-view-image" className={`w-full min-h-[30vh] flex flex-col items-center justify-center text-darkGrey ${className}`}>
            <Archive size={40} />
            <p className="mt-4 p-0">{description}</p>
        </div>
    );
}