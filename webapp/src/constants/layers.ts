/**
 * The overlay stacking scale, mirrored by `theme.zIndex` in tailwind.config.ts
 * (`z-modal`, `z-popover`, `z-toast`).
 *
 * Every modal, dialog and sheet uses `z-modal`. Every piece of floating content
 * that is portalled to <body> (select listboxes, popovers, dropdown menus,
 * tooltips) uses `z-popover`, so it always opens in front of the modal it was
 * opened from. Toasts use `z-toast` so feedback is never hidden by a modal.
 */
export const LAYERS = {
    modal: 2500,
    popover: 3000,
    toast: 4000
} as const;

export const LAYER_CLASS_NAMES = ['modal', 'popover', 'toast'] as const;
