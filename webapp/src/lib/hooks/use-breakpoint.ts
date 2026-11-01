import createBreakpoint from 'react-use/lib/factory/createBreakpoint';

const breakPoints = {
    xs: 480,
    '2xs': 360,
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    '2xl': 1536
};

export const useBreakpoint = createBreakpoint(breakPoints);

export function useIsMobile() {
    const breakpoint = useBreakpoint();

    return ['xs', '2xs', 'sm', 'md'].indexOf(breakpoint) !== -1;
}

/**
 * A phone: narrower than the `sm` breakpoint (640px). The responses list is
 * drawn as cards there instead of a table. Not the same as useIsMobile, which
 * also counts tablets.
 */
export function useIsPhone() {
    const breakpoint = useBreakpoint();

    return ['sm', 'md', 'lg', 'xl', '2xl'].indexOf(breakpoint) === -1;
}
