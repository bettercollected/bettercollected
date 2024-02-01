import React from 'react';

import { disabledIconStyle, iconStyle, svgStyle } from './styles/google';

const darkSvg = (
    <svg
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"
        width="46px"
        height="46px"
        viewBox="0 0 46 46"
        style={svgStyle}
    >
        <defs>
            <filter
                x="-50%"
                y="-50%"
                width="200%"
                height="200%"
                filterUnits="objectBoundingBox"
                id="filter-1"
            >
                <feOffset dx="0" dy="1" in="SourceAlpha" result="shadowOffsetOuter1" />
                <feGaussianBlur
                    stdDeviation="0.5"
                    in="shadowOffsetOuter1"
                    result="shadowBlurOuter1"
                />
                <feColorMatrix
                    values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.168 0"
                    in="shadowBlurOuter1"
                    type="matrix"
                    result="shadowMatrixOuter1"
                />
                <feOffset dx="0" dy="0" in="SourceAlpha" result="shadowOffsetOuter2" />
                <feGaussianBlur
                    stdDeviation="0.5"
                    in="shadowOffsetOuter2"
                    result="shadowBlurOuter2"
                />
                <feColorMatrix
                    values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.084 0"
                    in="shadowBlurOuter2"
                    type="matrix"
                    result="shadowMatrixOuter2"
                />
                <feMerge>
                    <feMergeNode in="shadowMatrixOuter1" />
                    <feMergeNode in="shadowMatrixOuter2" />
                    <feMergeNode in="SourceGraphic" />
                </feMerge>
            </filter>
            <rect id="path-2" x="0" y="0" width="40" height="40" rx="2" />
            <rect id="path-3" x="5" y="5" width="38" height="38" rx="1" />
        </defs>
        <g
            id="Google-Button"
            stroke="none"
            strokeWidth="1"
            fill="none"
            fillRule="evenodd"
        >
            <g id="9-PATCH" transform="translate(-608.000000, -219.000000)" />
            <g id="btn_google_dark_normal" transform="translate(-1.000000, -1.000000)">
                <g
                    id="button"
                    transform="translate(4.000000, 4.000000)"
                    filter="url(#filter-1)"
                >
                    <g id="button-bg">
                        <use fill="#4285F4" fillRule="evenodd" />
                        <use fill="none" />
                        <use fill="none" />
                        <use fill="none" />
                    </g>
                </g>
                <g id="button-bg-copy">
                    <use fill="#FFFFFF" fillRule="evenodd" />
                    <use fill="none" />
                    <use fill="none" />
                    <use fill="none" />
                </g>
                <g id="logo_googleg_48dp" transform="translate(15.000000, 15.000000)">
                    <path
                        d="M17.64,9.20454545 C17.64,8.56636364 17.5827273,7.95272727 17.4763636,7.36363636 L9,7.36363636 L9,10.845 L13.8436364,10.845 C13.635,11.97 13.0009091,12.9231818 12.0477273,13.5613636 L12.0477273,15.8195455 L14.9563636,15.8195455 C16.6581818,14.2527273 17.64,11.9454545 17.64,9.20454545 L17.64,9.20454545 Z"
                        id="Shape"
                        fill="#4285F4"
                    />
                    <path
                        d="M9,18 C11.43,18 13.4672727,17.1940909 14.9563636,15.8195455 L12.0477273,13.5613636 C11.2418182,14.1013636 10.2109091,14.4204545 9,14.4204545 C6.65590909,14.4204545 4.67181818,12.8372727 3.96409091,10.71 L0.957272727,10.71 L0.957272727,13.0418182 C2.43818182,15.9831818 5.48181818,18 9,18 L9,18 Z"
                        id="Shape"
                        fill="#34A853"
                    />
                    <path
                        d="M3.96409091,10.71 C3.78409091,10.17 3.68181818,9.59318182 3.68181818,9 C3.68181818,8.40681818 3.78409091,7.83 3.96409091,7.29 L3.96409091,4.95818182 L0.957272727,4.95818182 C0.347727273,6.17318182 0,7.54772727 0,9 C0,10.4522727 0.347727273,11.8268182 0.957272727,13.0418182 L3.96409091,10.71 L3.96409091,10.71 Z"
                        id="Shape"
                        fill="#FBBC05"
                    />
                    <path
                        d="M9,3.57954545 C10.3213636,3.57954545 11.5077273,4.03363636 12.4404545,4.92545455 L15.0218182,2.34409091 C13.4631818,0.891818182 11.4259091,0 9,0 C5.48181818,0 2.43818182,2.01681818 0.957272727,4.95818182 L3.96409091,7.29 C4.67181818,5.16272727 6.65590909,3.57954545 9,3.57954545 L9,3.57954545 Z"
                        id="Shape"
                        fill="#EA4335"
                    />
                    <path d="M0,0 L18,0 L18,18 L0,18 L0,0 Z" id="Shape" />
                </g>
                <g id="handles_square" />
            </g>
        </g>
    </svg>
);

const lightSvg = (
    <svg
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"
        width="46px"
        height="46px"
        viewBox="0 0 46 46"
        style={svgStyle}
    >
        <defs>
            <filter
                x="-50%"
                y="-50%"
                width="200%"
                height="200%"
                filterUnits="objectBoundingBox"
                id="filter-1"
            >
                <feOffset dx="0" dy="1" in="SourceAlpha" result="shadowOffsetOuter1" />
                <feGaussianBlur
                    stdDeviation="0.5"
                    in="shadowOffsetOuter1"
                    result="shadowBlurOuter1"
                />
                <feColorMatrix
                    values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.168 0"
                    in="shadowBlurOuter1"
                    type="matrix"
                    result="shadowMatrixOuter1"
                />
                <feOffset dx="0" dy="0" in="SourceAlpha" result="shadowOffsetOuter2" />
                <feGaussianBlur
                    stdDeviation="0.5"
                    in="shadowOffsetOuter2"
                    result="shadowBlurOuter2"
                />
                <feColorMatrix
                    values="0 0 0 0 0   0 0 0 0 0   0 0 0 0 0  0 0 0 0.084 0"
                    in="shadowBlurOuter2"
                    type="matrix"
                    result="shadowMatrixOuter2"
                />
                <feMerge>
                    <feMergeNode in="shadowMatrixOuter1" />
                    <feMergeNode in="shadowMatrixOuter2" />
                    <feMergeNode in="SourceGraphic" />
                </feMerge>
            </filter>
            <rect id="path-2" x="0" y="0" width="40" height="40" rx="2" />
        </defs>
        <g
            id="Google-Button"
            stroke="none"
            strokeWidth="1"
            fill="none"
            fillRule="evenodd"
        >
            <g id="9-PATCH" transform="translate(-608.000000, -160.000000)" />
            <g id="btn_google_light_normal" transform="translate(-1.000000, -1.000000)">
                <g
                    id="button"
                    transform="translate(4.000000, 4.000000)"
                    filter="url(#filter-1)"
                >
                    <g id="button-bg">
                        <use fill="#FFFFFF" fillRule="evenodd" />
                        <use fill="none" />
                        <use fill="none" />
                        <use fill="none" />
                    </g>
                </g>
                <g id="logo_googleg_48dp" transform="translate(15.000000, 15.000000)">
                    <path
                        d="M17.64,9.20454545 C17.64,8.56636364 17.5827273,7.95272727 17.4763636,7.36363636 L9,7.36363636 L9,10.845 L13.8436364,10.845 C13.635,11.97 13.0009091,12.9231818 12.0477273,13.5613636 L12.0477273,15.8195455 L14.9563636,15.8195455 C16.6581818,14.2527273 17.64,11.9454545 17.64,9.20454545 L17.64,9.20454545 Z"
                        id="Shape"
                        fill="#4285F4"
                    />
                    <path
                        d="M9,18 C11.43,18 13.4672727,17.1940909 14.9563636,15.8195455 L12.0477273,13.5613636 C11.2418182,14.1013636 10.2109091,14.4204545 9,14.4204545 C6.65590909,14.4204545 4.67181818,12.8372727 3.96409091,10.71 L0.957272727,10.71 L0.957272727,13.0418182 C2.43818182,15.9831818 5.48181818,18 9,18 L9,18 Z"
                        id="Shape"
                        fill="#34A853"
                    />
                    <path
                        d="M3.96409091,10.71 C3.78409091,10.17 3.68181818,9.59318182 3.68181818,9 C3.68181818,8.40681818 3.78409091,7.83 3.96409091,7.29 L3.96409091,4.95818182 L0.957272727,4.95818182 C0.347727273,6.17318182 0,7.54772727 0,9 C0,10.4522727 0.347727273,11.8268182 0.957272727,13.0418182 L3.96409091,10.71 L3.96409091,10.71 Z"
                        id="Shape"
                        fill="#FBBC05"
                    />
                    <path
                        d="M9,3.57954545 C10.3213636,3.57954545 11.5077273,4.03363636 12.4404545,4.92545455 L15.0218182,2.34409091 C13.4631818,0.891818182 11.4259091,0 9,0 C5.48181818,0 2.43818182,2.01681818 0.957272727,4.95818182 L3.96409091,7.29 C4.67181818,5.16272727 6.65590909,3.57954545 9,3.57954545 L9,3.57954545 Z"
                        id="Shape"
                        fill="#EA4335"
                    />
                    <path d="M0,0 L18,0 L18,18 L0,18 L0,0 Z" id="Shape" />
                </g>
                <g id="handles_square" />
            </g>
        </g>
    </svg>
);

const disabledSvg = (
    <svg
        width="46px"
        height="46px"
        viewBox="0 0 46 46"
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"
        style={svgStyle}
    >
        <defs>
            <rect id="path-1" x="0" y="0" width="40" height="40" rx="2" />
        </defs>
        <g
            id="Google-Button"
            stroke="none"
            strokeWidth="1"
            fill="none"
            fillRule="evenodd"
        >
            <g id="9-PATCH" transform="translate(-788.000000, -219.000000)" />
            <g
                id="btn_google_dark_disabled"
                transform="translate(-1.000000, -1.000000)"
            >
                <g id="button" transform="translate(4.000000, 4.000000)">
                    <g id="button-bg">
                        <use fillOpacity="0.08" fill="#000000" fillRule="evenodd" />
                        <use fill="none" />
                        <use fill="none" />
                        <use fill="none" />
                    </g>
                </g>
                <path
                    d="M24.001,25.71 L24.001,22.362 L32.425,22.362 C32.551,22.929 32.65,23.46 32.65,24.207 C32.65,29.346 29.203,33 24.01,33 C19.042,33 15.01,28.968 15.01,24 C15.01,19.032 19.042,15 24.01,15 C26.44,15 28.474,15.891 30.031,17.349 L27.475,19.833 C26.827,19.221 25.693,18.501 24.01,18.501 C21.031,18.501 18.601,20.976 18.601,24.009 C18.601,27.042 21.031,29.517 24.01,29.517 C27.457,29.517 28.726,27.132 28.96,25.719 L24.001,25.719 L24.001,25.71 Z"
                    id="Shape-Copy"
                    fillOpacity="0.4"
                    fill="#000000"
                />
                <g id="handles_square" />
            </g>
        </g>
    </svg>
);

const typeformSvg = (
    <svg
        width="44px"
        height="44px"
        viewBox="-0.5 0 257 257"
        version="1.1"
        xmlns="http://www.w3.org/2000/svg"
        preserveAspectRatio="xMidYMid"
    >
        <g>
            <path
                d="M121.239531,0.47435412 C154.258847,-2.24419986 177.973534,6.51949224 203.490026,32.0209539 C231.03887,59.5533708 249.354214,95.2328648 254.290235,133.239251 C259.781839,175.505244 252.228399,207.045826 228.963591,230.137302 C206.717472,252.217693 174.224091,259.500956 130.817584,255.872056 L130.817584,255.872056 L129.020628,255.714401 C92.0580678,252.31591 65.9142731,240.197353 40.5830264,214.542641 C13.525519,187.139558 -0.732370213,156.026391 0.0289819699,123.37039 C0.401368488,107.383336 4.93009017,93.7578927 13.6639513,80.3889177 C19.3897229,71.6244438 25.2046788,64.7874057 37.3681164,52.2487147 L37.3681164,52.2487147 L41.4275324,48.0907013 L45.9022443,43.5551431 C74.7290193,14.5793771 93.7072016,2.74118195 121.239531,0.47435412 Z M201.527922,33.9842216 C176.58625,9.05724142 153.671595,0.589198793 121.467288,3.24065127 C94.3271196,5.47519117 75.6884654,17.3319772 46.5188613,46.8760997 L46.5188613,46.8760997 L44.4086816,49.0171264 C30.1966379,63.4648858 23.5365117,70.8518409 17.66965,79.3947543 L17.66965,79.3947543 L16.8159631,80.6541424 L15.9876804,81.9069942 C7.52700788,94.8577977 3.16375473,107.9854 2.80388584,123.435056 C2.06141566,155.281167 15.9979199,185.693018 42.5581255,212.592447 C67.82505,238.182016 93.7827344,249.991613 131.048788,253.106044 L131.048788,253.106044 L132.897415,253.254431 C174.642425,256.464747 205.76515,249.252143 227.008257,228.167291 C249.578581,205.765126 256.927442,175.078792 251.537704,133.596809 C246.682834,96.2152658 228.654224,61.0943485 201.527922,33.9842216 Z M166.984321,93.3903087 L166.984321,106.949394 L138.186877,106.949394 L138.186877,184.662246 L123.842281,184.662246 L123.842281,106.949394 L95.044837,106.949394 L95.044837,93.3903087 L166.984321,93.3903087 Z"
                fill="#262627"
                fillRule="nonzero"
            ></path>
        </g>
    </svg>
);

interface IProviderIconProps {
    disabled: boolean;
    type: 'light' | 'dark' | 'typeform';
}

export const ProviderIcon = ({ disabled, type }: IProviderIconProps) => {
    const getEnabledIcon =
        type === 'dark' ? darkSvg : type === 'light' ? lightSvg : typeformSvg;
    const getDisabledIcon = type === 'typeform' ? typeformSvg : disabledSvg;

    return (
        <div
            className="flex items-center justify-center"
            // @ts-ignore
            style={!disabled ? iconStyle : { ...iconStyle, ...disabledIconStyle }}
        >
            {!disabled ? getEnabledIcon : getDisabledIcon}
        </div>
    );
};

ProviderIcon.defaultProps = {
    type: 'light'
};
