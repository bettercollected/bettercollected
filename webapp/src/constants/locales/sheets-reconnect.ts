// A Google Sheets action whose grant predates the `drive.file` flow: it must be reconnected before it runs again.
export const sheetsReconnect = {
    badge: 'SHEETS_RECONNECT.BADGE',
    title: 'SHEETS_RECONNECT.TITLE',
    description: 'SHEETS_RECONNECT.DESCRIPTION',
    newSheet: 'SHEETS_RECONNECT.NEW_SHEET',
    button: 'SHEETS_RECONNECT.BUTTON'
};
