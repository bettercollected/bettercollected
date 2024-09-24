import { createSlice, PayloadAction } from '@reduxjs/toolkit';
import { InvitationState } from '@app/models/invitationTypes';

const initialState: InvitationState = {
    invitationSent: false,
    error: null
};

const invitationSlice = createSlice({
    name: 'invitation',
    initialState,
    reducers: {
        resendInvitationSuccess(state) {
            state.invitationSent = true;
            state.error = null;
        },
        resendInvitationFailure(state, action: PayloadAction<string>) {
            state.error = action.payload;
        },
        resetInvitationState(state) {
            state.invitationSent = false;
            state.error = null;
        }
    }
});

export const { useResendInvitationSuccess, useResendInvitationFailure, useResetInvitationState } = invitationSlice.actions;

export default invitationSlice.reducer;
