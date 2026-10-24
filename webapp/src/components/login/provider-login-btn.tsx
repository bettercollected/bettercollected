import { PureComponent } from 'react';

import { GoogleIcon } from '@Components/icons/google';

import { ProviderIcon } from '@app/components/icons/brands/provider';
import { darkStyle, disabledStyle, hoverStyle, lightStyle } from '@app/components/icons/brands/styles/google';

interface IPropTypes {
    label: string;
    icon: any;
    disabled?: boolean;
    tabIndex?: number;
    onClick: Function;
    className?: string;
    type: 'light' | 'dark';
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
        onClick: () => { }
    };

    state = {
        hovered: false
    };

    getStyle = (propStyles: any) => {
        const baseStyle = this.props.type === 'dark' ? darkStyle : lightStyle;
        hoverStyle.boxShadow = '0 0 3px 3px rgba(66,133,244,.3)';
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
        const { label, icon, style, className, ...otherProps } = this.props;

        const Icon = icon;

        return (
            <div {...otherProps} role="button" onClick={this.click} onMouseOver={this.mouseOver} onMouseOut={this.mouseOut} className={`bg-black-800 hover:bg-black-900 key-edge [--key-edge:#05080F] flex items-center justify-center text-white transition-colors ${className}`}>
                {/*<Icon {...this.props} />*/}
                <GoogleIcon />
                <span className="mx-1">{label}</span>
            </div>
        );
    }
}
