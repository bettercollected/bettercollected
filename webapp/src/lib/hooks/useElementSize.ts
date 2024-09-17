import { useCallback, useEffect, useState } from 'react';

interface ElementSize {
    width: number;
    height: number;
    marginTop: number;
    marginRight: number;
    marginBottom: number;
    marginLeft: number;
}

const useElementSize = (selector: string): ElementSize => {
    const [elementSize, setElementSize] = useState<ElementSize>({
        width: 0,
        height: 0,
        marginTop: 0,
        marginRight: 0,
        marginBottom: 0,
        marginLeft: 0
    });

    const updateSize = useCallback(() => {
        const elements = document.querySelectorAll(selector);
        let totalWidth = 0;
        let totalHeight = 0;

        let marginTop = 0;
        let marginRight = 0;
        let marginBottom = 0;
        let marginLeft = 0;

        elements.forEach((element: Element) => {
            const computedStyle = window.getComputedStyle(element as HTMLElement);
            const width =
                (element as HTMLElement).offsetWidth +
                parseFloat(computedStyle.marginLeft) +
                parseFloat(computedStyle.marginRight) +
                parseFloat(computedStyle.paddingLeft) +
                parseFloat(computedStyle.paddingRight);
            const height =
                (element as HTMLElement).offsetHeight +
                parseFloat(computedStyle.marginTop) +
                parseFloat(computedStyle.marginBottom) +
                parseFloat(computedStyle.paddingTop) +
                parseFloat(computedStyle.paddingBottom);

            totalWidth += width;
            totalHeight += height;

            marginTop += parseFloat(computedStyle.marginTop);
            marginRight += parseFloat(computedStyle.marginRight);
            marginBottom += parseFloat(computedStyle.marginBottom);
            marginLeft += parseFloat(computedStyle.marginLeft);
        });

        setElementSize({
            width: totalWidth,
            height: totalHeight,
            marginTop: marginTop,
            marginRight: marginRight,
            marginBottom: marginBottom,
            marginLeft: marginLeft
        });
    }, [selector]);

    useEffect(() => {
        updateSize();

        window.addEventListener('resize', updateSize);

        return () => {
            window.removeEventListener('resize', updateSize);
        };
    }, [updateSize]);

    return elementSize;
};

export default useElementSize;
