import createBreakpoint from 'react-use/lib/factory/createBreakpoint';

const breakPoints = {
    xs: 360,
    '2xs': 480,
    sm: 640,
    md: 768,
    lg: 1024,
    xl: 1280,
    '2xl': 1536
};

export const useBreakpoint = createBreakpoint(breakPoints);
