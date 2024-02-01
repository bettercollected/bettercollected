import React from 'react';

export function JoyrideStepTitle({ text }: { text: string }) {
    return <span className="sh3">{text}</span>;
}

export function JoyrideStepContent({
    children
}: {
    children: React.ReactNode | React.ReactNode[] | string;
}) {
    return <p className="body4">{children}</p>;
}
