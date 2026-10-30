// Inspired by react-hot-toast library
import * as React from 'react';

import type { ToastActionElement, ToastProps } from '@app/shadcn/components/ui/toast';

const TOAST_LIMIT = 1;
const TOAST_REMOVE_DELAY = 3000;

type ToasterToast = ToastProps & {
    id: string;
    title?: React.ReactNode;
    description?: React.ReactNode;
    action?: ToastActionElement;
};

const actionTypes = {
    ADD_TOAST: 'ADD_TOAST',
    UPDATE_TOAST: 'UPDATE_TOAST',
    DISMISS_TOAST: 'DISMISS_TOAST',
    REMOVE_TOAST: 'REMOVE_TOAST'
} as const;

let count = 0;

function genId() {
    count = (count + 1) % Number.MAX_SAFE_INTEGER;
    return count.toString();
}

type ActionType = typeof actionTypes;

type Action =
    | {
          type: ActionType['ADD_TOAST'];
          toast: ToasterToast;
      }
    | {
          type: ActionType['UPDATE_TOAST'];
          toast: Partial<ToasterToast>;
      }
    | {
          type: ActionType['DISMISS_TOAST'];
          toastId?: ToasterToast['id'];
      }
    | {
          type: ActionType['REMOVE_TOAST'];
          toastId?: ToasterToast['id'];
      };

interface State {
    toasts: ToasterToast[];
}

const toastTimeouts = new Map<string, ReturnType<typeof setTimeout>>();

const addToRemoveQueue = (toastId: string) => {
    if (toastTimeouts.has(toastId)) {
        return;
    }

    const timeout = setTimeout(() => {
        toastTimeouts.delete(toastId);
        dispatch({
            type: 'REMOVE_TOAST',
            toastId: toastId
        });
    }, TOAST_REMOVE_DELAY);

    toastTimeouts.set(toastId, timeout);
};

export const reducer = (state: State, action: Action): State => {
    switch (action.type) {
        case 'ADD_TOAST':
            return {
                ...state,
                toasts: [action.toast, ...state.toasts].slice(0, TOAST_LIMIT)
            };

        case 'UPDATE_TOAST':
            return {
                ...state,
                toasts: state.toasts.map((t) =>
                    t.id === action.toast.id ? { ...t, ...action.toast } : t
                )
            };

        case 'DISMISS_TOAST': {
            const { toastId } = action;

            // ! Side effects ! - This could be extracted into a dismissToast() action,
            // but I'll keep it here for simplicity
            if (toastId) {
                addToRemoveQueue(toastId);
            } else {
                state.toasts.forEach((toast) => {
                    addToRemoveQueue(toast.id);
                });
            }

            return {
                ...state,
                toasts: state.toasts.map((t) =>
                    t.id === toastId || toastId === undefined
                        ? {
                              ...t,
                              open: false
                          }
                        : t
                )
            };
        }
        case 'REMOVE_TOAST':
            if (action.toastId === undefined) {
                return {
                    ...state,
                    toasts: []
                };
            }
            return {
                ...state,
                toasts: state.toasts.filter((t) => t.id !== action.toastId)
            };
    }
};

const listeners: Array<(state: State) => void> = [];

let memoryState: State = { toasts: [] };

function dispatch(action: Action) {
    memoryState = reducer(memoryState, action);
    // a copy: a listener may unsubscribe while this runs
    [...listeners].forEach((listener) => {
        listener(memoryState);
    });
}

type Toast = Omit<ToasterToast, 'id'>;

function toast({ ...props }: Toast) {
    const id = genId();

    const update = (props: ToasterToast) =>
        dispatch({
            type: 'UPDATE_TOAST',
            toast: { ...props, id }
        });
    const dismiss = () => dispatch({ type: 'DISMISS_TOAST', toastId: id });

    dispatch({
        type: 'ADD_TOAST',
        toast: {
            ...props,
            id,
            open: true,
            onOpenChange: (open) => {
                if (!open) dismiss();
            }
        }
    });

    return {
        id: id,
        dismiss,
        update
    };
}

/** How notices waiting for the same thing merge: their counts add up. */
export interface ToastMerge {
    key: string;
    count: number;
    describe: (count: number) => React.ReactNode;
}

interface WaitingNotice {
    props: Toast;
    merge?: ToastMerge;
}

// Notices waiting for an action toast (an Undo) to close.
let waitingNotices: WaitingNotice[] = [];
const offersAction = (state: State) => state.toasts.some((item) => item.open && !!item.action);
const describe = ({ props, merge }: WaitingNotice): Toast => (merge ? { ...props, description: merge.describe(merge.count) } : props);

function showWaiting() {
    // checked again: another action toast may have opened meanwhile
    if (offersAction(memoryState) || !waitingNotices.length) return;
    const due = waitingNotices;
    waitingNotices = [];
    stopWatching();
    due.forEach((notice) => toast(describe(notice)));
}

const watchToasts = (state: State) => {
    if (!offersAction(state)) setTimeout(showWaiting, 0);
};

function stopWatching() {
    const index = listeners.indexOf(watchToasts);
    if (index > -1) listeners.splice(index, 1);
}

/**
 * A plain notice that never replaces a toast offering an action (an Undo,
 * say; only one toast shows at a time): shown now, or once no open toast
 * has an action. Waiting notices with the same `merge.key` become one, their
 * counts added up. Returns a cancel for a notice still waiting (call it when
 * the page that asked goes away).
 */
function toastWhenFree(props: Toast, merge?: ToastMerge): () => void {
    if (!offersAction(memoryState) && !waitingNotices.length) {
        toast(describe({ props, merge }));
        return () => undefined;
    }
    const same = merge ? waitingNotices.find((notice) => notice.merge?.key === merge.key) : undefined;
    let entry: WaitingNotice;
    if (same?.merge && merge) {
        same.merge = { ...same.merge, count: same.merge.count + merge.count };
        entry = same;
    } else {
        entry = { props, merge: merge ? { ...merge } : undefined };
        waitingNotices.push(entry);
    }
    if (!listeners.includes(watchToasts)) listeners.push(watchToasts);
    if (!offersAction(memoryState)) setTimeout(showWaiting, 0);
    return () => {
        waitingNotices = waitingNotices.filter((notice) => notice !== entry);
        if (!waitingNotices.length) stopWatching();
    };
}

function useToast() {
    const [state, setState] = React.useState<State>(memoryState);

    React.useEffect(() => {
        listeners.push(setState);
        return () => {
            const index = listeners.indexOf(setState);
            if (index > -1) {
                listeners.splice(index, 1);
            }
        };
    }, [state]);

    return {
        ...state,
        toast,
        dismiss: (toastId?: string) => dispatch({ type: 'DISMISS_TOAST', toastId })
    };
}

export { useToast, toast, toastWhenFree };
