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
