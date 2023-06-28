import FormBuilderInput from '@Components/FormBuilder/InputComponents/FormBuilderInput';
import { Notes } from '@mui/icons-material';

export default function LongText() {
    return (
        <FormBuilderInput
            multiline
            minRows={3}
            maxRows={5}
            InputProps={{
                endAdornment: <Notes />,
                sx: {
                    '& .css-3fezr7-MuiInputBase-root-MuiOutlinedInput-root': {
                        padding: '4px 8px 4px 8px'
                    },
                    fontSize: '.875rem;',
                    alignItems: 'flex-start'
                }
            }}
        />
    );
}
