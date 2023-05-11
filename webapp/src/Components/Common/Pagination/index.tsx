import { Pagination } from '@mui/material';
import { styled } from '@mui/material/styles';

const StyledPagination = styled(Pagination)({
    '& .MuiPagination-ul li:last-child': {
        marginLeft: '16px'
    },
    '& .MuiPagination-ul li:last-child button::before': {
        content: "'Next'",
        marginRight: '8px'
    },
    '& .MuiPagination-ul li:first-child': {
        marginRight: '16px'
    },
    '& .MuiPagination-ul li:first-child button::after': {
        content: "'Previous'",
        marginLeft: '8px'
    }
});
export default StyledPagination;
