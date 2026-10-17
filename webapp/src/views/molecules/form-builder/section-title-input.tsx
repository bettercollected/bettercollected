'use client';

import { useLayoutEffect, useRef } from 'react';

import { cn } from '@app/shadcn/util/lib';
import { SECTION_TITLE_MAX } from '@app/utils/leaflet-sections';

/**
 * The page's section title, edited where respondents see it: on the Leaflet
 * section bar in the builder canvas. Empty, the placeholder shows what the
 * bar falls back to (the page's opening heading, its first question or
 * "Section n"), so it is clear what respondents see when it is left empty.
 *
 * One line of text that wraps like the bar's title: Enter finishes editing
 * instead of adding a line break.
 */
export default function SectionTitleInput({ value, placeholder, onChange, onFocusChange, className }: { value: string; placeholder: string; onChange: (value: string) => void; onFocusChange?: (focused: boolean) => void; className?: string }) {
    const ref = useRef<HTMLTextAreaElement>(null);
    // Grow with the text, so a long title wraps on the bar as it will for respondents.
    useLayoutEffect(() => {
        const element = ref.current;
        if (!element) return;
        element.style.height = 'auto';
        element.style.height = `${element.scrollHeight}px`;
    }, [value, placeholder]);

    return (
        <textarea
            ref={ref}
            rows={1}
            value={value}
            placeholder={placeholder}
            maxLength={SECTION_TITLE_MAX}
            aria-label="Section title"
            data-testid="leaflet-section-title-input"
            spellCheck
            onChange={(event) => onChange(event.target.value.replace(/[\r\n]+/g, ' '))}
            onKeyDown={(event) => {
                if (event.key === 'Enter' || event.key === 'Escape') {
                    event.preventDefault();
                    event.currentTarget.blur();
                }
                // The canvas listens for Escape and Delete; typing here is not a canvas command.
                event.stopPropagation();
            }}
            onClick={(event) => event.stopPropagation()}
            onFocus={() => onFocusChange?.(true)}
            onBlur={() => onFocusChange?.(false)}
            className={cn(
                'block w-full resize-none overflow-hidden rounded-[2px] border-0 bg-transparent p-0 text-balance text-inherit outline-hidden [font:inherit]',
                'placeholder:text-white/75 hover:bg-white/10 focus-visible:bg-white/10 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-white',
                className
            )}
        />
    );
}
