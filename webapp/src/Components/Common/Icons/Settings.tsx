import React from 'react';

export default function SettingsIcon(props: React.SVGAttributes<{}>) {
    return (
        <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg" {...props}>
            <path
                d="M9 1H11C11.5523 1 12 1.44772 12 2V2.56879C12 2.99659 12.2871 3.36825 12.6822 3.53228C13.0775 3.69638 13.5377 3.63384 13.8403 3.33123L14.2426 2.92891C14.6331 2.53838 15.2663 2.53838 15.6568 2.92891L17.071 4.34312C17.4616 4.73365 17.4615 5.36681 17.071 5.75734L16.6688 6.1596C16.3661 6.46223 16.3036 6.92247 16.4677 7.31774C16.6317 7.71287 17.0034 8 17.4313 8L18 8C18.5523 8 19 8.44771 19 9V11C19 11.5523 18.5523 12 18 12H17.4312C17.0034 12 16.6318 12.2871 16.4677 12.6822C16.3036 13.0775 16.3661 13.5377 16.6688 13.8403L17.071 14.2426C17.4616 14.6331 17.4616 15.2663 17.071 15.6568L15.6568 17.071C15.2663 17.4616 14.6331 17.4616 14.2426 17.071L13.8403 16.6688C13.5377 16.3661 13.0775 16.3036 12.6822 16.4677C12.2871 16.6318 12 17.0034 12 17.4312V18C12 18.5523 11.5523 19 11 19H9C8.44772 19 8 18.5523 8 18V17.4313C8 17.0034 7.71287 16.6317 7.31774 16.4677C6.92247 16.3036 6.46223 16.3661 6.1596 16.6688L5.75732 17.071C5.36679 17.4616 4.73363 17.4616 4.34311 17.071L2.92889 15.6568C2.53837 15.2663 2.53837 14.6331 2.92889 14.2426L3.33123 13.8403C3.63384 13.5377 3.69638 13.0775 3.53228 12.6822C3.36825 12.2871 2.99659 12 2.56879 12H2C1.44772 12 1 11.5523 1 11V9C1 8.44772 1.44772 8 2 8L2.56877 8C2.99658 8 3.36825 7.71288 3.53229 7.31776C3.6964 6.9225 3.63386 6.46229 3.33123 6.15966L2.92891 5.75734C2.53838 5.36681 2.53838 4.73365 2.92891 4.34313L4.34312 2.92891C4.73365 2.53839 5.36681 2.53839 5.75734 2.92891L6.15966 3.33123C6.46228 3.63386 6.9225 3.6964 7.31776 3.53229C7.71288 3.36825 8 2.99658 8 2.56876V2C8 1.44772 8.44772 1 9 1Z"
                stroke="currentColor"
                strokeWidth={props.strokeWidth || 2}
            />
            <path d="M12 10C12 11.1046 11.1046 12 10 12C8.89543 12 8 11.1046 8 10C8 8.89543 8.89543 8 10 8C11.1046 8 12 8.89543 12 10Z" stroke="currentColor" strokeWidth={props.strokeWidth || 2} />
        </svg>
    );
}
