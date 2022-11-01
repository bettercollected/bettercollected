import * as React from 'react';

import styled from '@emotion/styled';
import MuiAlert, { AlertColor, AlertProps } from '@mui/material/Alert';
import Snackbar from '@mui/material/Snackbar';

interface IMuiSnackbar {
    isOpen: boolean;
    setIsOpen: Function;
    severity: AlertColor;
    message: string;
}

const Alert = React.forwardRef<HTMLDivElement, AlertProps>(function Alert(props, ref) {
    return <MuiAlert elevation={6} ref={ref} variant="filled" {...props} />;
});

const StyledSnackbar = styled.div`
    @media (min-width: 600px) {
        .MuiSnackbar-root {
            bottom: 24px;
            left: 24px;
            right: 24px !important;
        }
    }
`;

export default function MuiSnackbar({ isOpen, setIsOpen, severity, message }: IMuiSnackbar) {
    const handleClose = (event?: React.SyntheticEvent | Event, reason?: string) => {
        if (reason === 'clickaway') {
            return;
        }

        setIsOpen(false);
    };

    return (
        <StyledSnackbar>
            <Snackbar open={isOpen} autoHideDuration={6000} onClose={handleClose}>
                <Alert onClose={handleClose} severity={severity} sx={{ width: '100%' }}>
                    {message}
                </Alert>
            </Snackbar>
        </StyledSnackbar>
    );
}
