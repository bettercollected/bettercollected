import { RootState } from '@app/store/store';

// @ts-ignore
export const selectPatchingTemplate = (state: RootState) => state.mutationStatus.patchTemplate;
