import { type ClassValue, clsx } from 'clsx';

import { extendTailwindMerge } from 'tailwind-merge';

import { LAYER_CLASS_NAMES } from '@app/constants/layers';

// Teach tailwind-merge the named z-index layers, so a call site's `z-[…]`
// replaces a primitive's `z-popover` instead of both classes being emitted.
const twMerge = extendTailwindMerge({
    extend: {
        classGroups: {
            z: [{ z: [...LAYER_CLASS_NAMES] }]
        }
    }
});

export function cn(...inputs: ClassValue[]) {
    return twMerge(clsx(inputs));
}
