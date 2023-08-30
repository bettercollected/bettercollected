import * as React from 'react';

import { Switch, SwitchProps } from '@mui/material';
import { styled } from '@mui/material/styles';
import PropTypes from 'prop-types';

// Define prop types for customization
interface CustomSwitchProps extends SwitchProps {
    thumbColorChecked?: string;
    thumbColorUnchecked?: string;
    trackColorChecked?: string;
    trackColorUnchecked?: string;
    thumbSize?: number;
    trackBorderRadius?: number;
}

const MuiSwitch = styled((props: CustomSwitchProps) => <Switch focusVisibleClassName=".Mui-focusVisible" disableRipple {...props} />)(
    ({ theme, thumbColorChecked, thumbColorUnchecked, trackColorChecked, trackColorUnchecked, thumbSize, trackBorderRadius }) => ({
        width: thumbSize ? thumbSize * 2 + 2 : 42,
        height: thumbSize ? thumbSize + 4 : 26,
        padding: 0,

        '& .MuiSwitch-switchBase': {
            padding: 0,
            margin: 2,
            transitionDuration: '300ms',
            '&.Mui-checked': {
                transform: `translateX(${thumbSize || 16}px)`,
                color: '#fff',
                '& + .MuiSwitch-track': {
                    backgroundColor: trackColorChecked || (theme.palette.mode === 'dark' ? '#2ECA45' : '#65C466'),
                    opacity: 1,
                    border: 0
                },
                '&.Mui-disabled + .MuiSwitch-track': {
                    opacity: 0.5
                }
            },
            '&.Mui-focusVisible .MuiSwitch-thumb': {
                color: '#33cf4d',
                border: '6px solid #fff'
            },
            '&.Mui-disabled .MuiSwitch-thumb': {
                color: theme.palette.mode === 'light' ? theme.palette.grey[100] : theme.palette.grey[600]
            },
            '&.Mui-disabled + .MuiSwitch-track': {
                opacity: theme.palette.mode === 'light' ? 0.7 : 0.3
            }
        },
        '& .MuiSwitch-thumb': {
            boxSizing: 'border-box',
            width: thumbSize || 22,
            height: thumbSize || 22
        },
        '& .MuiSwitch-track': {
            borderRadius: trackBorderRadius || (thumbSize ? thumbSize + 4 : 26) / 2,
            backgroundColor: trackColorUnchecked || (theme.palette.mode === 'light' ? '#E9E9EA' : '#39393D'),
            opacity: 1,
            transition: theme.transitions.create(['background-color'], {
                duration: 500
            })
        }
    })
);

MuiSwitch.propTypes = {
    thumbColorChecked: PropTypes.string,
    thumbColorUnchecked: PropTypes.string,
    trackColorChecked: PropTypes.string,
    trackColorUnchecked: PropTypes.string,
    thumbSize: PropTypes.number,
    trackBorderRadius: PropTypes.number
};

export default MuiSwitch;
