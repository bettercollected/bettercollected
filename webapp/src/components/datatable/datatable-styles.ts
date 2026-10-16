// Shared admin-table treatment on the trust ramp: hairline borders (#EAECF0),
// surface header (#F5F7FB), ink text — the old pure greys (#DBDBDB/#2E2E2E)
// sat outside the blue-biased neutral system every other surface uses.
export const dataTableCustomStyles = {
    table: {
        style: {
            // The table sits on the paper-mist page: its outer edges take the
            // strong hairline, inner cell lines stay on white.
            borderTop: '1px solid #D0D5DD',
            borderBottom: '1px solid #D0D5DD'
        }
    },
    headRow: {
        style: {
            border: 'none',
            backgroundColor: '#F5F7FB',
            fontSize: '14px',
            color: '#344054 !important',
            height: '50px !important'
        }
    },
    headCells: {
        style: {
            borderRight: '1px solid #EAECF0',
            color: '#344054 !important',
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
            color: '#101828 !important',
            borderRight: '1px solid #EAECF0',
            paddingTop: '8px',
            paddingBottom: '8px'
        }
    },
    rows: {
        style: {
            color: '#667085',
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
            backgroundColor: '#F5F7FB',
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
