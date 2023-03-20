import { useEffect, useState } from 'react';

import { useBreakpoint } from '@app/lib/hooks/use-breakpoint';

export default function DynamicContainer({ children }: any) {
    const breakpoint = useBreakpoint();

    const [maxWidth, setMaxWidth] = useState('max-w-screen');

    useEffect(() => {
        switch (breakpoint) {
            case 'xl':
                setMaxWidth('max-w-[1080px]');
                break;
            case '2xl':
                setMaxWidth('max-w-[1240px]');
                break;
            case '3xl':
                setMaxWidth('max-w-[1580px]');
                break;
            case '4xl':
                setMaxWidth('max-w-[1960px]');
                break;

            case 'xs':
            case 'sm':
            case 'md':
            case 'lg':
            default:
                setMaxWidth('max-w-screen');
        }
    }, [breakpoint]);

    return <div className={`${maxWidth} w-full`}>{children}</div>;
}
