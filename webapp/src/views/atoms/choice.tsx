import { CSSProperties, KeyboardEvent, ReactNode, forwardRef } from 'react';

import { Check } from 'lucide-react';

import { FormTheme, THEME_RADII } from '@app/constants/theme';
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
                {selected && <Check className="form-choice-pop h-3.5 w-3.5" strokeWidth={3} style={{ color: inverted ? themed('--form-highlight-solid', theme?.secondary) : '#ffffff' }} />}
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
            {selected && <span className="form-choice-pop h-2.5 w-2.5 rounded-full" style={{ background: on }} />}
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

/**
 * Whether a theme draws its answer options as lettered cards: a key letter
 * (A, B, C…) at the start of each option, which the respondent can press to
 * choose it, and a check mark at the end of a chosen one. Themes that set
 * their own corners (`radius`, the shape of fields, option cards and
 * buttons) do, the complete looks among them; a theme without one keeps the
 * ring and box it always had, so stored forms don't change.
 */
export function showsOptionKeys(theme?: Partial<FormTheme> | null): boolean {
    return !!theme?.radius && (THEME_RADII as readonly string[]).includes(theme.radius);
}

/** The key letters of `count` options: A to Z, none past the 26th. */
export function optionKeys(count: number): Array<string | undefined> {
    return Array.from({ length: count }, (_, index) => (index < 26 ? String.fromCharCode(65 + index) : undefined));
}

/**
 * Key letters for a short list of labels (Yes and No): their own first
 * letters (Y and N, J and N in Dutch) when those are distinct letters, else
 * A, B, C.
 */
export function initialKeys(labels: string[]): Array<string | undefined> {
    const initials = labels.map((label) => label.trim().charAt(0).toUpperCase());
    const usable = initials.every((initial) => /^[A-Z]$/.test(initial)) && new Set(initials).size === initials.length;
    return usable ? initials : optionKeys(labels.length);
}

/**
 * The option a key press names: the index of its letter among `keys`, or -1.
 * Only a plain letter counts (no Ctrl, Alt or Meta, so browser and screen
 * reader shortcuts pass through), and only while focus is on an option
 * itself, never in a text field: the letters are shortcuts of the focused
 * group alone (WCAG 2.1.4).
 */
export function optionIndexForKey(event: KeyboardEvent<HTMLElement>, keys: Array<string | undefined>): number {
    if (event.ctrlKey || event.altKey || event.metaKey || event.key.length !== 1) return -1;
    const target = event.target as HTMLElement;
    if (target.closest('input, textarea, select, [contenteditable="true"]')) return -1;
    return keys.indexOf(event.key.toUpperCase());
}

const KEY_CORNER: Record<string, string> = { sharp: '0px', soft: '4px', round: '9999px' };

/**
 * The key letter at the start of a lettered option card (showsOptionKeys):
 * an outlined square in the theme's corners at rest (the tertiary edge, the
 * letter in ink), filled in the chosen colour with its own ink once chosen.
 * On a solid chosen row (studio) it is drawn in the row's ink instead.
 * Decorative for assistive tech: the option carries `aria-keyshortcuts`.
 */
export function OptionKeyHint({ letter, selected, theme, inverted = false }: { letter: string; selected?: boolean; theme?: Partial<FormTheme>; inverted?: boolean }) {
    const solidInk = 'var(--form-highlight-solid-ink, #ffffff)';
    const colours: CSSProperties = inverted
        ? { borderColor: solidInk, color: solidInk }
        : selected
          ? { borderColor: themed('--form-highlight-edge', theme?.secondary), background: themed('--form-highlight-solid', theme?.secondary), color: solidInk }
          : { borderColor: theme?.tertiary, color: theme?.primary };
    return (
        <span
            aria-hidden="true"
            data-option-key-hint
            className="flex h-7 w-7 shrink-0 items-center justify-center border font-mono text-[13px] font-semibold leading-none transition-colors duration-150"
            style={{ ...colours, borderRadius: KEY_CORNER[theme?.radius ?? 'soft'] ?? '4px' }}
        >
            {letter}
        </span>
    );
}

/**
 * The row's content: control, then the label. With a key letter (a theme
 * that shows option keys) the letter stands where the control was, and a
 * chosen row ends in a check mark, so the choice reads in a shape as well as
 * in colour and weight; the mark pops in gently unless reduced motion is
 * asked for (`form-choice-pop`, tailwind.css).
 */
export function ChoiceContent({ kind, selected, theme, solid, lang, keyHint, children }: { kind: ChoiceKind; selected?: boolean; theme?: Partial<FormTheme>; solid?: boolean; lang?: string; keyHint?: string; children: ReactNode }) {
    return (
        <>
            {keyHint ? <OptionKeyHint letter={keyHint} selected={selected} theme={theme} inverted={solid} /> : <ChoiceIndicator kind={kind} selected={selected} theme={theme} inverted={solid} />}
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere]" lang={lang}>
                {children}
            </span>
            {keyHint && selected && (
                <Check
                    aria-hidden="true"
                    data-choice-check
                    className="form-choice-pop h-5 w-5 shrink-0"
                    strokeWidth={2.5}
                    style={{ color: solid ? 'var(--form-highlight-solid-ink, #ffffff)' : themed('--form-highlight-edge', theme?.secondary) }}
                />
            )}
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
    /** Its key letter, on a theme that shows option keys (showsOptionKeys). */
    keyHint?: string;
    onKeyDown?: (event: KeyboardEvent<HTMLButtonElement>) => void;
}

/**
 * One option as a button. Checkboxes are announced as checkboxes
 * (role="checkbox" + aria-checked); single-answer lists outside a radio group
 * (the dropdown's options) stay toggle buttons with aria-pressed.
 */
const Choice = forwardRef<HTMLButtonElement, ChoiceProps>(({ isSelected = false, theme, index, choice, onClick, kind = 'radio', lang, keyHint, onKeyDown }, ref) => {
    const row = choiceRowStyle(theme, isSelected);
    const semantics = kind === 'checkbox' ? { role: 'checkbox', 'aria-checked': isSelected } : { 'aria-pressed': isSelected };
    return (
        <button ref={ref} type="button" {...semantics} aria-keyshortcuts={keyHint} data-option-key={keyHint} style={row.style} className={row.className} key={choice.id} onClick={() => onClick && onClick(choice.id || '')} onKeyDown={onKeyDown}>
            <ChoiceContent kind={kind} selected={isSelected} theme={theme} solid={row.solid} lang={choice.value ? lang : undefined} keyHint={keyHint}>
                {choice.value ? choice.value : `Item ${index + 1}`}
            </ChoiceContent>
        </button>
    );
});
Choice.displayName = 'Choice';

export default Choice;
