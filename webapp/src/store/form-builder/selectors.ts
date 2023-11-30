import { RootState } from '@app/store/store';

export const selectBuilderState = (state: RootState) => state.builder.present;

export const selectBuilderPastState = (state: RootState) => state.builder.past[state.builder.past.length - 1];

export const selectBuilderFutureState = (state: RootState) => state.builder.future[0];

export const selectIsFormDirty = (state: RootState) => state.builder.present.isFormDirty;

export const selectFormField = (id: string) => (state: RootState) => state.builder.present.fields[id];

export const selectActiveFieldId = (state: RootState) => state.builder.present.activeFieldId;
export const selectActiveFieldIndex = (state: RootState) => state.builder.present.activeFieldIndex;

export const selectActiveChoiceId = (state: RootState) => state.builder.present.activeChoiceId;
export const selectActiveChoiceIndex = (state: RootState) => state.builder.present.activeChoiceIndex;

export const selectCoverImage = (state: RootState) => state.builder.present.coverImage;
export const selectLogo = (state: RootState) => state.builder.present.logo;

export const selectFields = (state: RootState) => state.builder.present.fields;
export const selectResponseOwnerField = (state: RootState) => state.builder.present.settings?.responseDataOwnerField;

export const selectPreviousField = (id: string) => (state: RootState) => {
    const currentField = state.builder.present.fields[id];
    if (currentField.position == 0) return undefined;
    return Object.values(state.builder.present.fields)[currentField.position - 1];
};

export const selectNextField = (id: string) => (state: RootState) => {
    const currentField = state.builder.present.fields[id];
    const nextPosition = currentField.position + 1;

    // Find the field with the next position
    const nextField = Object.values(state.builder.present.fields).find((field) => field.position === nextPosition);

    return nextField || undefined; // Return the next field or undefined if not found
};

// @ts-ignore
export const selectMenuState = (menu: string) => (state: RootState) => state?.builder?.present?.menus[menu];
