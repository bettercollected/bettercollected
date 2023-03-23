import React, { PureComponent } from 'react';

import { ProviderIcon } from '@app/components/icons/brands/provider';
import { darkStyle, disabledStyle, hoverStyle, lightStyle, typeformDarkStyle } from '@app/components/icons/brands/styles/google';

interface IPropTypes {
    label: string;
    icon: any;
    isGoogle: boolean;
    disabled?: boolean;
    tabIndex?: number;
    onClick: Function;
    type: 'light' | 'dark' | 'typeform';
    style?: any;
}

interface IState {
    hovered: boolean;
}

export default class ProviderLoginButton extends PureComponent<IPropTypes, IState> {
    static defaultProps = {
        icon: ProviderIcon,
        isGoogle: true,
        label: 'Sign in with Google',
        disabled: false,
        type: 'light',
        tabIndex: 0,
        onClick: () => {}
    };

    state = {
        hovered: false
    };

    getStyle = (propStyles: any) => {
        const baseStyle = this.props.type === 'dark' ? darkStyle : this.props.type === 'light' ? lightStyle : typeformDarkStyle;
        if (this.state.hovered) {
            return { ...baseStyle, ...hoverStyle, ...propStyles };
        }
        if (this.props.disabled) {
            return { ...baseStyle, ...disabledStyle, ...propStyles };
        }
        return { ...baseStyle, ...propStyles };
    };

    mouseOver = () => {
        if (!this.props.disabled) {
            this.setState({ hovered: true });
        }
    };

    mouseOut = () => {
        if (!this.props.disabled) {
            this.setState({ hovered: false });
        }
    };

    click = (e: any) => {
        if (!this.props.disabled) {
            this.props.onClick(e);
        }
    };

    render() {
        const { label, icon, style, ...otherProps } = this.props;

        const Icon = icon;

        return (
            <div {...otherProps} role="button" onClick={this.click} style={this.getStyle(style)} onMouseOver={this.mouseOver} onMouseOut={this.mouseOut}>
                <Icon {...this.props} />
                <span>{label}</span>
            </div>
        );
    }
}
