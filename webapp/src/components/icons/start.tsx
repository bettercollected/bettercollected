export function StarIcon(props: React.SVGAttributes<any>) {
    return (
        <svg
            width="44"
            height="43"
            viewBox="0 0 44 43"
            fill={props.fill}
            xmlns="http://www.w3.org/2000/svg"
            {...props}
        >
            <path
                d="M10.3952 40.9123L22 35.0611L33.6048 40.9123C35.1317 41.6821 36.858 40.3049 36.4465 38.6452L33.5977 27.1543L42.4014 17.2902C43.5035 16.0553 42.7142 14.0925 41.0639 13.9645L28.5015 12.99L23.8233 2.61157C23.1153 1.04075 20.8847 1.04075 20.1767 2.61158L15.4985 12.99L2.93612 13.9645C1.28584 14.0925 0.49649 16.0553 1.59865 17.2902L10.4023 27.1543L7.55353 38.6452C7.14205 40.3049 8.86828 41.6821 10.3952 40.9123Z"
                stroke={props.stroke || 'currentColor'}
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
            />
        </svg>
    );
}
