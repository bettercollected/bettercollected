import { useEffect, useState } from 'react';

export function useScaling() {
    const [scale, setScale] = useState<number>(1);

    useEffect(() => {
        const updateScale = () => {
            const screenWidth = window.innerWidth;
            let referenceWidth: number;

            if (screenWidth < 1920) {
                referenceWidth = 1024;
            } else {
                referenceWidth = 1920;
            }

            const newScale = screenWidth / referenceWidth;

            setScale(newScale);
        };

        window.addEventListener('resize', updateScale);
        updateScale();

        return () => window.removeEventListener('resize', updateScale);
    }, []);

    return scale;
}
