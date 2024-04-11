import { BorderLeft, BorderRight } from '@mui/icons-material';

export const dataTableCustomStyles = {
    table: {
        style: {
            border: 'none',
            background: 'transparent'
        }
    },
    headRow: {
        style: {
            border: 'none',
            backgroundColor: '#EEEEEE',
            fontSize: '14px',
            color: '#2E2E2E !important',
            height: '50px !important'
        }
    },
    headCells: {
        style: {
            borderRight: '1px solid #DBDBDB',
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
            fontSize: '18px',
            color: '#2E2E2E !important',
            borderRight: '1px solid #DBDBDB'
            // paddingLeft: '6px',
            // paddingRight: '6px'
        }
    },
    rows: {
        style: {
            color: '#6E6E6E',
            outlineWidth: '0',
            borderRadius: '4px',
            paddingLeft: '0',
            paddingRight: '0',
            height: '40px !important',
            minHeight: '40px'
        }
    },
    pagination: {
        style: {
            border: 'none'
        }
    }
};
