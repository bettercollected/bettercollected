/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-20
 * Time: 20:07
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import { useEffect, useState } from 'react';

export default function useDimension() {
    const [windowSize, setWindowSize] = useState<any>({
        width: undefined,
        height: undefined
    });

    function handleResize() {
        setWindowSize({
            width: window.innerWidth,
            height: window.innerHeight
        });
    }

    useEffect(() => {
        if (typeof window !== 'undefined') {
            window.addEventListener('resize', handleResize);
            return () => window.removeEventListener('resize', handleResize);
        }
    }, []);

    return windowSize;
}
