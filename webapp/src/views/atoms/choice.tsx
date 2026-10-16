import { CSSProperties, ReactNode, forwardRef } from 'react';

import { Check } from 'lucide-react';

import { FormTheme } from '@app/constants/theme';
import { FieldChoice } from '@app/models/dtos/form';
import { cn } from '@app/shadcn/util/lib';
import { styleTokens } from '@app/views/molecules/theme/theme-shared';

/** A radio (one answer) or a checkbox (several answers). */
export type ChoiceKind = 'radio' | 'checkbox';

/**
 * The control drawn at the start of every option: an empty ring or box at
 * rest, a filled dot or a ticked box when chosen. Selection is visible in the
 * shape itself, not only in colour (WCAG 1.4.1). Its edge wears the theme's
 * tertiary, which every preset keeps at 3:1 or more on its ground.
 */
export function ChoiceIndicator({ kind, selected, theme, inverted = false }: { kind: ChoiceKind; selected?: boolean; theme?: Partial<FormTheme>; inverted?: boolean }) {
    const on = inverted ? '#ffffff' : theme?.secondary;
    const edge = selected ? on : inverted ? '#ffffff' : theme?.tertiary;
    if (kind === 'checkbox') {
        return (
            <span
                aria-hidden="true"
                data-choice-indicator
                className="flex h-5 w-5 shrink-0 items-center justify-center rounded-[4px] border-2 border-(--choice-indicator) transition-colors duration-150 group-hover:border-(--choice-indicator-hover)"
                style={{ ['--choice-indicator' as string]: edge, background: selected ? on : '#ffffff' }}
            >
                {selected && <Check className="h-3.5 w-3.5" strokeWidth={3} style={{ color: inverted ? theme?.secondary : '#ffffff' }} />}
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
    const vars = {
        ['--choice-indicator-hover' as string]: selected ? (solid ? '#ffffff' : theme?.secondary) : theme?.primary
    };
    return {
        solid,
        className: cn('group flex min-h-12 w-full cursor-pointer items-center gap-3 border border-(--choice-edge) px-4 py-3 text-left text-base leading-snug transition-colors duration-150 hover:border-(--choice-edge-hover)', selected && 'font-semibold'),
        style: {
            ...vars,
            ['--choice-edge-hover' as string]: selected ? theme?.secondary : theme?.primary,
            background: solid ? theme?.secondary : selected ? theme?.secondary + '1A' : '',
            ['--choice-edge' as string]: selected ? theme?.secondary : theme?.tertiary,
            color: solid ? '#ffffff' : theme?.primary,
            borderRadius: tokens.inputRadius
        }
    };
}

/** The row's content: control, then the label. */
export function ChoiceContent({ kind, selected, theme, solid, children }: { kind: ChoiceKind; selected?: boolean; theme?: Partial<FormTheme>; solid?: boolean; children: ReactNode }) {
    return (
        <>
            <ChoiceIndicator kind={kind} selected={selected} theme={theme} inverted={solid} />
            <span className="min-w-0 flex-1 [overflow-wrap:anywhere]">{children}</span>
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
}

/**
 * One option as a button. Checkboxes are announced as checkboxes
 * (role="checkbox" + aria-checked); single-answer lists outside a radio group
 * (the dropdown's options) stay toggle buttons with aria-pressed.
 */
const Choice = forwardRef<HTMLButtonElement, ChoiceProps>(({ isSelected = false, theme, index, choice, onClick, kind = 'radio' }, ref) => {
    const row = choiceRowStyle(theme, isSelected);
    const semantics = kind === 'checkbox' ? { role: 'checkbox', 'aria-checked': isSelected } : { 'aria-pressed': isSelected };
    return (
        <button ref={ref} type="button" {...semantics} style={row.style} className={row.className} key={choice.id} onClick={() => onClick && onClick(choice.id || '')}>
            <ChoiceContent kind={kind} selected={isSelected} theme={theme} solid={row.solid}>
                {choice.value ? choice.value : `Item ${index + 1}`}
            </ChoiceContent>
        </button>
    );
});
Choice.displayName = 'Choice';

export default Choice;
