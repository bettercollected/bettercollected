import { RootState } from '../store';

export const selectConsentAnswers = (state: RootState) => state.fillForm.consentAnswers;