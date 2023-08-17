import { RootState } from '@app/store/store';

export const selectBuilderState = (state: RootState) => state.builder.present;

export const selectBuilderPastState = (state: RootState) => state.builder.past[state.builder.past.length - 1];

export const selectBuilderFutureState = (state: RootState) => state.builder.future[0];

export const selectIsFormDirty = (state: RootState) => state.builder.present.isFormDirty;

export const selectFormField = (id: string) => (state: RootState) => state.builder.present.fields[id];

export const selectActiveFieldId = (state: RootState) => state.builder.present.activeFieldId;

export const selectResponseOwnerField = (state: RootState) => state.builder.present.settings?.responseDataOwnerField;
