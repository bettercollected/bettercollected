import { DELETION_TABLE_PADDING } from './deletion-request-columns';

// Shared admin-table treatment on the trust ramp: hairline borders, surface header, ink text — the old pure greys
// (#DBDBDB/#2E2E2E) sat outside the blue-biased neutral system every other surface uses.
//
// The edges and the header band read the app theme's roles (`--app-edge`, `--app-edge-strong`, `--app-wash`), with the
// frozen value as the fallback, so a table in a Pigment workspace has warm edges and a warm header band while Daybreak
// (where each role is exactly that value) and any page without a theme scope draw what they always drew. In Daybreak
// `--app-wash` is black-100 (#F5F7FB), `--app-edge` black-300 (#EAECF0) and `--app-edge-strong` black-400 (#D0D5DD): no
// approximation. The neutral text steps stay on the frozen ramp (`--color-black-600/700/900`), as everywhere in the app.
export const TABLE_WASH = 'var(--app-wash, #F5F7FB)';
export const TABLE_EDGE = 'var(--app-edge, #EAECF0)';
export const TABLE_EDGE_STRONG = 'var(--app-edge-strong, #D0D5DD)';
export const TEXT_STRONG = 'var(--color-black-700, #344054)';
export const TEXT_INK = 'var(--color-black-900, #101828)';
const TEXT_MUTED = 'var(--color-black-600, #667085)';

export const dataTableCustomStyles = {
    table: {
        style: {
            // The table sits on the paper-mist page: its outer edges take the
            // strong hairline, inner cell lines stay on white.
            borderTop: `1px solid ${TABLE_EDGE_STRONG}`,
            borderBottom: `1px solid ${TABLE_EDGE_STRONG}`
        }
    },
    headRow: {
        style: {
            border: 'none',
            backgroundColor: TABLE_WASH,
            fontSize: '14px',
            color: `${TEXT_STRONG} !important`,
            height: '50px !important'
        }
    },
    headCells: {
        style: {
            borderRight: `1px solid ${TABLE_EDGE}`,
            color: `${TEXT_STRONG} !important`,
            fontSize: '14px',
            paddingTop: '5px',
            paddingBottom: '5px',
            paddingLeft: '8px',
            paddingRight: '8px'
        }
    },
    cells: {
        style: {
            padding: '0',
            fontSize: '18px',
            color: `${TEXT_INK} !important`,
            borderRight: `1px solid ${TABLE_EDGE}`,
            paddingTop: '8px',
            paddingBottom: '8px'
        }
    },
    rows: {
        style: {
            color: TEXT_MUTED,
            outlineWidth: '0',
            borderRadius: '4px',
            paddingLeft: '0',
            paddingRight: '0',
            height: '48px !important',
            minHeight: '48px',
            backgroundColor: ''
        }
    },
    pagination: {
        style: {
            border: 'none'
        }
    }
};

// The deletion requests table: the same, with the header's left padding the cells' (DELETION_TABLE_PADDING), so a
// column's text starts under its title.
export const deletionRequestTableStyles = {
    ...dataTableCustomStyles,
    headCells: {
        style: {
            ...dataTableCustomStyles.headCells.style,
            paddingLeft: DELETION_TABLE_PADDING,
            paddingRight: '8px'
        }
    }
};

// The table of the custom-domain page keeps its old pure greys (#F6F6F6, #2E2E2E, #4D4D4D, #6E6E6E): none is a role or a ramp
// step, so none is approximated. Only its header band, exactly the wash, follows the theme.
export const simpleDataTableStyles = {
    table: {
        style: {
            borderRadius: '16px !important',
            overflow: 'hidden',
            border: '1px solid #F6F6F6'
        }
    },
    headRow: {
        style: {
            border: 'none',
            backgroundColor: TABLE_WASH,
            fontSize: '12px',
            padding: '0px 24px',
            color: '#2E2E2E !important',
            height: '50px !important'
        }
    },
    headCells: {
        style: {
            color: '#2E2E2E !important',
            fontSize: '14px',
            paddingTop: '5px',
            paddingBottom: '5px',
            paddingLeft: '8px',
            paddingRight: '8px'
        }
    },
    cells: {
        style: {
            padding: '0',
            paddingRight: '8px !important',
            fontSize: '12px',
            color: '#4D4D4D !important',
            paddingTop: '8px',
            paddingBottom: '8px',
            margin: '0px auto'
        }
    },
    rows: {
        style: {
            color: '#6E6E6E',
            outlineWidth: '0',
            padding: '0px 24px',
            border: '1px solid #F6F6F6',
            height: '48px !important',
            minHeight: '48px',
            backgroundColor: ''
        }
    },
    pagination: {
        style: {
            border: 'none'
        }
    }
};
