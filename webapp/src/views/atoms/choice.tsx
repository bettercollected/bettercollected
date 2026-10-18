import { CSSProperties, ReactNode, forwardRef } from 'react';

import { Check } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import { FieldChoice } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { themed } from '@app/views/molecules/theme/theme-root';
import { leafletColours, styleTokens } from '@app/views/molecules/theme/theme-shared';

/** A radio (one answer) or a checkbox (several answers). */
export type ChoiceKind = 'radio' | 'checkbox';

/**
 * The control drawn at the start of every option: an empty ring or box at
 * rest, a filled dot or a ticked box when chosen. Selection is visible in the
 * shape itself, not only in colour (WCAG 1.4.1). Its edge wears the theme's
 * tertiary, which every preset keeps at 3:1 or more on its ground.
 */
export function ChoiceIndicator({ kind, selected, theme, inverted = false }: { kind: ChoiceKind; selected?: boolean; theme?: Partial<FormTheme>; inverted?: boolean }) {
    // The chosen control wears the theme's highlight where it sets one
    // (theme-root.ts: an edge colour that reads on the page), else the secondary.
    const onSolid = 'var(--form-highlight-solid-ink, #ffffff)';
    const on = inverted ? onSolid : themed('--form-highlight-edge', theme?.secondary);
    const edge = selected ? on : inverted ? onSolid : theme?.tertiary;
    if (kind === 'checkbox') {
        return (
            <span
                aria-hidden="true"
                data-choice-indicator
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] border-2 border-(--choice-indicator) transition-colors duration-150 group-hover:border-(--choice-indicator-hover)"
                style={{ ['--choice-indicator' as string]: edge, background: selected ? on : '#ffffff' }}
            >
                {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} style={{ color: inverted ? themed('--form-highlight-solid', theme?.secondary) : '#ffffff' }} />}
            </span>
        );
    }
    return (
        <span
            aria-hidden="true"
            data-choice-indicator
            className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-(--choice-indicator) bg-white transition-colors duration-150 group-hover:border-(--choice-indicator-hover)"
            style={{ ['--choice-indicator' as string]: edge }}
        >
            {selected && <span className="h-2.5 w-2.5 rounded-full" style={{ background: on }} />}
        </span>
    );
}

/**
 * How one option row is dressed, shared by every choice control (multiple
 * choice, checkboxes, yes/no, the dropdown list) so they read as one family:
 * a bordered row (tertiary at rest, ink on hover, the action colour when
 * chosen) with a light action tint, or a solid fill with white text in the
 * studio style.
 *
 * 48px tall at least (a comfortable touch target), and the chosen answer is
 * set in semibold on top of the filled control.
 */
export function choiceRowStyle(theme: Partial<FormTheme> | undefined, selected: boolean): { className: string; style: CSSProperties; solid: boolean } {
    const tokens = styleTokens(theme?.style);
    const solid = tokens.solidSelection && selected;
    // The chosen option in the theme's highlight where it sets one
    // (theme-root.ts highlightColours), else the secondary as before.
    const chosenEdge = themed('--form-highlight-edge', theme?.secondary);
    const vars = {
        ['--choice-indicator-hover' as string]: selected ? (solid ? 'var(--form-highlight-solid-ink, #ffffff)' : chosenEdge) : theme?.primary
    };
    if (tokens.ruledChoices) {
        // Leaflet: no box. A 1px rule under each row (a separator in a tint
        // of the border colour; the control itself keeps the full-strength
        // edge) and a faint wash of the action colour on hover.
        return {
            solid: false,
            className: cn('group flex min-h-12 w-full cursor-pointer items-center gap-3 border-b px-1 py-3 text-left text-base leading-snug transition-colors duration-150 hover:bg-(--choice-wash)', selected && 'font-semibold'),
            style: {
                ...vars,
                ['--choice-wash' as string]: theme?.secondary ? theme.secondary + '0D' : 'transparent',
                borderColor: leafletColours(theme).rule,
                color: theme?.primary
            }
        };
    }
    return {
        solid,
        className: cn(
            'form-choice-row group flex min-h-12 w-full cursor-pointer items-center gap-3 border border-(--choice-edge) px-4 py-3 text-left text-base leading-snug transition-colors duration-150 hover:border-(--choice-edge-hover)',
            selected && 'font-semibold'
        ),
        style: {
            ...vars,
            ['--choice-edge-hover' as string]: selected ? chosenEdge : theme?.primary,
            background: solid ? themed('--form-highlight-solid', theme?.secondary) : selected ? themed('--form-highlight-fill', theme?.secondary + '1A') : '',
            ['--choice-edge' as string]: selected ? chosenEdge : theme?.tertiary,
            color: solid ? 'var(--form-highlight-solid-ink, #ffffff)' : selected ? themed('--form-highlight-fill-ink', theme?.primary) : theme?.primary,
            borderRadius: tokens.cardRadius
        }
    };
}

/** The row's content: control, then the label. */
export function ChoiceContent({ kind, selected, theme, solid, lang, children }: { kind: ChoiceKind; selected?: boolean; theme?: Partial<FormTheme>; solid?: boolean; lang?: string; children: ReactNode }) {
    return (
        <>
            <ChoiceIndicator kind={kind} selected={selected} theme={theme} inverted={solid} />
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere]" lang={lang}>
                {children}
            </span>
        </>
    );
}

interface ChoiceProps {
    isSelected?: boolean;
    theme?: FormTheme;
    choice: FieldChoice;
    index: number;
    onClick?: (choiceId: string) => any;
    /** Which control the row draws; also its role (checkbox) when it is one. */
    kind?: ChoiceKind;
    /** The option's language, when it is not the page's (see useFormContentLanguage). */
    lang?: string;
}

/**
 * One option as a button. Checkboxes are announced as checkboxes
 * (role="checkbox" + aria-checked); single-answer lists outside a radio group
 * (the dropdown's options) stay toggle buttons with aria-pressed.
 */
const Choice = forwardRef<HTMLButtonElement, ChoiceProps>(({ isSelected = false, theme, index, choice, onClick, kind = 'radio', lang }, ref) => {
    const row = choiceRowStyle(theme, isSelected);
    const semantics = kind === 'checkbox' ? { role: 'checkbox', 'aria-checked': isSelected } : { 'aria-pressed': isSelected };
    return (
        <button ref={ref} type="button" {...semantics} style={row.style} className={row.className} key={choice.id} onClick={() => onClick && onClick(choice.id || '')}>
            <ChoiceContent kind={kind} selected={isSelected} theme={theme} solid={row.solid} lang={choice.value ? lang : undefined}>
                {choice.value ? choice.value : `Item ${index + 1}`}
            </ChoiceContent>
        </button>
    );
});
Choice.displayName = 'Choice';

export default Choice;
