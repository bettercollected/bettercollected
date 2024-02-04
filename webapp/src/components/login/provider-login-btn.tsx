import React, {PureComponent} from 'react';

import {GoogleIcon} from '@Components/Common/Icons/Google/google';

import {ProviderIcon} from '@app/components/icons/brands/provider';
import {
    darkStyle,
    disabledStyle,
    hoverStyle,
    lightStyle,
    typeformDarkStyle
} from '@app/components/icons/brands/styles/google';

interface IPropTypes {
    label: string;
    icon: any;
    disabled?: boolean;
    tabIndex?: number;
    onClick: Function;
    className?: string;
    type: 'light' | 'dark' | 'typeform';
    style?: any;
}

interface IState {
    hovered: boolean;
}

export default class ProviderLoginButton extends PureComponent<IPropTypes, IState> {
    static defaultProps = {
        icon: ProviderIcon,
        label: 'Sign in with Google',
        disabled: false,
        type: 'light',
        tabIndex: 0,
        className: '',
        onClick: () => {
        }
    };

    state = {
        hovered: false
    };

    getStyle = (propStyles: any) => {
        const baseStyle = this.props.type === 'dark' ? darkStyle : this.props.type === 'light' ? lightStyle : typeformDarkStyle;
        if (this.props.type === 'typeform') hoverStyle.boxShadow = '0 0 3px 3px rgba(0,0,0,.3)';
        else hoverStyle.boxShadow = '0 0 3px 3px rgba(66,133,244,.3)';
        if (this.state.hovered) {
            return {...baseStyle, ...hoverStyle, ...propStyles};
        }
        if (this.props.disabled) {
            return {...baseStyle, ...disabledStyle, ...propStyles};
        }
        return {...baseStyle, ...propStyles};
    };

    mouseOver = () => {
        if (!this.props.disabled) {
            this.setState({hovered: true});
        }
    };

    mouseOut = () => {
        if (!this.props.disabled) {
            this.setState({hovered: false});
        }
    };

    click = (e: any) => {
        if (!this.props.disabled) {
            this.props.onClick(e);
        }
    };

    render() {
        const {label, icon, style, className, ...otherProps} = this.props;

        const Icon = icon;

        return (
            <div {...otherProps} role="button" onClick={this.click} onMouseOver={this.mouseOver}
                 onMouseOut={this.mouseOut}
                 className={`flex justify-center items-center bg-black-800 text-white ${className} ${this.props.disabled ? 'cursor-not-allowed opacity-70' : ''}`}>
                {/*<Icon {...this.props} />*/}
                <GoogleIcon/>
                <span className="mx-1">{label}</span>
            </div>
        );
    }
}
