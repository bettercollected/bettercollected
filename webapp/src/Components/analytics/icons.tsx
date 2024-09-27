import { FaChrome, FaFirefox, FaApple, FaWindows, FaMobileAlt, FaDesktop, FaGlobe, FaLaptop, FaEdge, FaAndroid, FaSafari, FaLinux, FaTablet } from 'react-icons/fa';
import { IconType } from 'react-icons';

export const getBrowserIcon = (browser: string): IconType => {
    switch (browser.toLowerCase()) {
        case 'chrome':
            return FaChrome;
        case 'firefox':
            return FaFirefox;
        case 'edge-chromium':
            return FaEdge;
        case 'safari':
            return FaSafari;
        default:
            return FaGlobe;
    }
};

export const getDeviceIcon = (device: string): IconType => {
    switch (device.toLowerCase()) {
        case 'mobile':
            return FaMobileAlt;
        case 'desktop':
            return FaDesktop;
        case 'laptop':
            return FaLaptop;
        case 'android':
            return FaAndroid;
        case 'tablet':
            return FaTablet;
        default:
            return FaGlobe;
    }
};

export const getOSIcon = (os: string): IconType => {
    switch (os.toLowerCase()) {
        case 'mac os':
            return FaApple;
        case 'android os':
            return FaAndroid;
        case 'windows':
            return FaWindows;
        case 'linux':
            return FaLinux;
        default:
            return FaGlobe;
    }
};
