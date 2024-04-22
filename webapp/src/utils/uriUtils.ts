/**
 * Utility class for working with URIs
 *
 * @author Bibishan Pandey
 * @email bibishan@sireto.io
 */
export default class UriUtils {
    /**
     * Extracts hostname from a URL using the regex
     * @param url Full URL to extract hostname from (e.g. https://www.google.com/search?q=hello)
     * @returns string of hostname (e.g. www.google.com)
     *
     * @example
     * const url = 'https://www.google.com/search?q=hello';
     * const hostname = UriUtils.getHostnameFromRegex(url);
     *
     * @author Bibishan Pandey
     * @email bibishan@sireto.io
     */
    static getHostnameFromRegex(url: string): string {
        // run against regex
        const matches = url.match(/^https?:\/\/([^/?#]+)(?:[/?#]|$)/i);
        // extract hostname (will be empty string if no match is found)
        return matches ? matches[1] : '';
    }
}
