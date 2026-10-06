import { readFileSync } from 'fs';
import { resolve } from 'path';

import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import { LAYERS } from '@app/constants/layers';
import { cn } from '@app/shadcn/util/lib';

import tailwindConfig from '../../../../tailwind.config';
import { Dialog, DialogContent, DialogDescription } from './dialog';
import { Popover, PopoverContent, PopoverTrigger } from './popover';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './select';

describe('overlay stacking scale', () => {
    it('puts floating content above modals, and toasts above both', () => {
        expect(LAYERS.popover).toBeGreaterThan(LAYERS.modal);
        expect(LAYERS.toast).toBeGreaterThan(LAYERS.popover);
    });

    it('is the scale tailwind generates z-modal / z-popover / z-toast from', () => {
        const zIndex = (tailwindConfig.theme as any).zIndex;
        expect(zIndex.modal).toBe(String(LAYERS.modal));
        expect(zIndex.popover).toBe(String(LAYERS.popover));
        expect(zIndex.toast).toBe(String(LAYERS.toast));
    });

    it('lets a call site override a layer instead of emitting both classes', () => {
        expect(cn('z-popover bg-white', 'z-[10]')).toBe('bg-white z-[10]');
        expect(cn('z-modal', 'z-popover')).toBe('z-popover');
    });
});

describe('select inside a modal', () => {
    it('renders its listbox on the popover layer, above the modal layer', () => {
        render(
            <Dialog open>
                <DialogContent title="Invite">
                    <Select open value="editor">
                        <SelectTrigger aria-label="Role">
                            <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                            <SelectItem value="editor">Editor</SelectItem>
                        </SelectContent>
                    </Select>
                </DialogContent>
            </Dialog>
        );
        // An open select hides everything else from assistive tech, the dialog included.
        const dialog = screen.getByRole('dialog', { hidden: true });
        const listbox = screen.getByRole('listbox');
        expect(dialog.className).toContain('z-modal');
        expect(listbox.className).toContain('z-popover');
        // Portalled out of the dialog, so no ancestor of the dialog clips it.
        expect(dialog.contains(listbox)).toBe(false);
    });
});

describe('overlay surfaces', () => {
    it('gives dialogs, popovers and select menus an opaque white surface', () => {
        render(
            <Dialog open>
                <DialogContent title="Before you publish">
                    <DialogDescription>Recommended</DialogDescription>
                    <Popover open>
                        <PopoverTrigger>Open</PopoverTrigger>
                        <PopoverContent data-testid="popover">Popover</PopoverContent>
                    </Popover>
                </DialogContent>
            </Dialog>
        );
        expect(screen.getByRole('dialog', { name: 'Before you publish' }).className).toContain('bg-white');
        expect(screen.getByText('Recommended').className).toContain('text-black-600');
        expect(screen.getByTestId('popover').className).toContain('bg-white');
        expect(screen.getByTestId('popover').className).toContain('z-popover');
    });

    // The tailwind config uses `presets: []` and defines no shadcn colour
    // tokens, so classes like `bg-background` silently generate nothing and
    // leave an overlay transparent over its dark backdrop.
    it.each(['dialog', 'alert-dialog', 'sheet', 'popover', 'select', 'dropdown-menu', 'command'])('%s uses no undefined colour tokens', (name) => {
        const source = readFileSync(resolve(__dirname, `${name}.tsx`), 'utf8');
        expect(source).not.toMatch(/\b(?:bg|text|border|ring|ring-offset)-(?:background|foreground|popover|popover-foreground|muted|muted-foreground|accent|accent-foreground|input|ring)\b/);
    });
});
