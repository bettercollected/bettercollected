/**
 * The layout of the deletion requests table's columns (the workspace's Deletion requests page and a form's).
 *
 * react-data-table's `.rdt_table` has `min-width: fit-content`, so a table whose columns are not told how to share
 * the width takes the width of its widest text (every cell nowrap): wider than its card, with the columns sharing it
 * equally, so the email, the form name and the date were cut with room to spare and the last column ran off the edge.
 * Each column therefore says what it needs (`minWidth`) and who gets the rest (`grow`); a date or a long address
 * wraps where it must instead of being cut (`wrap`: a nowrap cell would count its whole text into the table's
 * fit-content width again), and the smallest the table gets (about 1055 px; the rest goes to the address and the form name, which then fit on one line) fits the card at 1440.
 *
 * One left padding for the header and the cells (`DELETION_TABLE_PADDING`), so a column's text starts under its title.
 */
export const DELETION_TABLE_PADDING = '16px';

export interface ColumnLayout {
    minWidth: string;
    grow: number;
    wrap?: boolean;
}

/** In column order: requested by, [form], requested on, status, deleted on, actions. */
export function deletionRequestColumnLayout(withFormColumn: boolean): ColumnLayout[] {
    const requestedBy: ColumnLayout = { minWidth: '225px', grow: 2, wrap: true };
    const form: ColumnLayout = { minWidth: '215px', grow: 2, wrap: true };
    const requestedOn: ColumnLayout = { minWidth: '200px', grow: 1, wrap: true };
    // room for a declined request's reason under the chip
    const status: ColumnLayout = { minWidth: '105px', grow: 1 };
    const deletedOn: ColumnLayout = { minWidth: '105px', grow: 1, wrap: true };
    // View and Delete response side by side
    const actions: ColumnLayout = { minWidth: '205px', grow: 0 };
    return withFormColumn ? [requestedBy, form, requestedOn, status, deletedOn, actions] : [requestedBy, requestedOn, status, deletedOn, actions];
}

/** The columns with the layout applied and the same left padding in every cell. */
export function withDeletionRequestLayout<T extends { style?: Record<string, unknown> }>(columns: T[], withFormColumn: boolean): T[] {
    const layout = deletionRequestColumnLayout(withFormColumn);
    return columns.map((column, index) => ({ ...column, ...layout[index], style: { ...column.style, paddingLeft: DELETION_TABLE_PADDING } }));
}
