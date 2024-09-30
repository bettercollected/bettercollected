// src/models/invitationTypes.ts

export interface InvitationState {
    invitationSent: boolean; // Indicates if the invitation has been sent
    error: string | null; // Stores error message if any
}
