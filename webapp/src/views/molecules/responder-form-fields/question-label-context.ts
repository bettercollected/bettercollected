import { ReactNode, createContext, useContext } from 'react';

/**
 * How a question's controls are named and described for assistive tech,
 * set by QuestionWrapper for the field inside it.
 *
 * Every control is named by the question's title (the rendered plain text,
 * so rich text and piped answers read as they show), never by its
 * placeholder. Inside a repeating-group item the item's heading ("Child 2")
 * is part of the name, so the same question in two items is told apart.
 * The description, "Why we ask this" and, while it shows, the error message
 * describe the control.
 */
export interface QuestionLabel {
    /** Space-separated ids naming the control: the title, then the item heading. Undefined for an untitled question. */
    labelledBy?: string;
    /** Space-separated ids describing the control: description, "why we ask", error. */
    describedBy?: string;
    /** The visually hidden "required" note, for controls that cannot carry aria-required. */
    requiredId?: string;
    required: boolean;
    invalid: boolean;
}

export const QuestionLabelContext = createContext<QuestionLabel | null>(null);

/** Space-separated ids for aria-labelledby / aria-describedby; undefined when there are none. */
export const joinIds = (...ids: Array<string | undefined | null | false>) => ids.filter(Boolean).join(' ') || undefined;

export interface GroupLabelProps {
    'aria-labelledby'?: string;
    'aria-describedby'?: string;
}

export interface ControlLabelProps extends GroupLabelProps {
    'aria-required'?: boolean;
    'aria-invalid'?: boolean;
}

/**
 * Props for the control(s) of the question being rendered: `control` for an
 * element that takes aria-required (a text box, a radio group, a file
 * input), `group` for one that does not (a button, a group of checkboxes or
 * buttons), which then hears "required" through its description. Outside a
 * QuestionWrapper (the builder canvas) both are empty.
 */
export function useQuestionLabel(): { label: QuestionLabel | null; control: ControlLabelProps; group: GroupLabelProps } {
    const label = useContext(QuestionLabelContext);
    if (!label) return { label: null, control: {}, group: {} };
    return {
        label,
        control: {
            'aria-labelledby': label.labelledBy,
            'aria-describedby': label.describedBy,
            'aria-required': label.required || undefined,
            'aria-invalid': label.invalid || undefined
        },
        group: {
            'aria-labelledby': label.labelledBy,
            'aria-describedby': joinIds(label.required && label.requiredId, label.describedBy)
        }
    };
}

/** useQuestionLabel as a render prop, for a field whose control sits inside the QuestionWrapper it renders. */
export function WithQuestionLabel({ children }: { children: (label: ReturnType<typeof useQuestionLabel>) => ReactNode }) {
    return children(useQuestionLabel());
}
