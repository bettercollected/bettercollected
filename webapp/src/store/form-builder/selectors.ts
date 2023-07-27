import { RootState } from '@app/store/store';

export const selectBuilderState = (state: RootState) => state.builder;

export const selectIsFormDirty = (state: RootState) => state.builder.isFormDirty;

export const selectFormField = (id: string) => (state: RootState) => state.builder.fields[id];

export const selectResponseOwnerField = (state: RootState) => state.builder.settings?.responseDataOwnerField;
