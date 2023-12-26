import Document, {DocumentContext, DocumentInitialProps, Head, Html, Main, NextScript} from 'next/document';

import environments from '@app/configs/environments';

class MyDocument extends Document {
    static async getInitialProps(ctx: DocumentContext): Promise<DocumentInitialProps> {
        return Document.getInitialProps(ctx);
    }

    render() {
        return (
            <Html lang="en-US" dir="ltr" className="light">
                <meta name="viewport"
                      content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=0"/>
                <Head>
                    {this.props.styles}
                    {embedScript()}
                    {embedMicrosoftClarityScript()}
                    {
                        environments.NEXT_PUBLIC_NODE_ENV === "production" && environments.UMAMI_WEBSITE_ID && environments.UMAMI_SCRIPT_URL &&
                        <script async src={environments.UMAMI_SCRIPT_URL}
                                data-website-id={environments.UMAMI_WEBSITE_ID}/>
                    }
                </Head>
                <body>
                <Main/>
                <NextScript/>
                </body>
            </Html>
        );
    }
}

function embedMicrosoftClarityScript() {
    if (environments.MICROSOFT_CLARITY_TRACKING_CODE)
        return (
            <script
                type="text/javascript"
                dangerouslySetInnerHTML={{
                    __html: `
                (function(c,l,a,r,i,t,y){
                    c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
                    t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
                    y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
                })(window, document, "clarity", "script", "${environments.MICROSOFT_CLARITY_TRACKING_CODE}");
            `
                }}
            />
        );
    return <></>;
}

function embedScript() {
    const config = {
        serviceName: environments.ELASTIC_APM_SERVICE_NAME + '-browser',
        serverUrl: environments.ELASTIC_APM_SERVER_URL,
        environment: environments.ELASTIC_APM_ENVIRONMENT || undefined
    };
    const htmlStr = 'elasticApm.init(' + JSON.stringify(config) + ')';
    return environments.APM_ENABLED ? (
        <>
            <script src="https://unpkg.com/@elastic/apm-rum@5.12.0/dist/bundles/elastic-apm-rum.umd.min.js"
                    crossOrigin="true"/>
            <script dangerouslySetInnerHTML={{__html: htmlStr}}/>
        </>
    ) : (
        <></>
    );
}

export default MyDocument;
