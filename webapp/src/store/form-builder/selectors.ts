import { RootState } from '@app/store/store';

export const selectBuilderState = (state: RootState) => state.builder;

export const selectIsFormDirty = (state: RootState) => state.builder.isFormDirty;
