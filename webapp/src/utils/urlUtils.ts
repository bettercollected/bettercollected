export function isValidRelativeURL(url: string): boolean {
    // Define a regular expression to match valid relative URLs
    const relativeURLPattern = /^\/|^(?!(?:[a-zA-Z]+:|\/\/))[\w\d\-._~:/?#\[\]@!$&'()*+,;=]+$/;

    // Check if the URL matches the pattern
    return relativeURLPattern.test(url) && !url.includes('//');
}
