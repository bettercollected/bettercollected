import Document, { DocumentContext, DocumentInitialProps, Head, Html, Main, NextScript } from 'next/document';

import environments from '@app/configs/environments';

class MyDocument extends Document {
    static async getInitialProps(ctx: DocumentContext): Promise<DocumentInitialProps> {
        return Document.getInitialProps(ctx);
    }
    render() {
        return (
            <Html lang="en-US" dir="ltr" className="light">
                <Head>
                    {this.props.styles}
                    {embedScript()}
                </Head>

                <body>
                    <Main />
                    <NextScript />
                </body>
            </Html>
        );
    }
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
            <script src="https://unpkg.com/@elastic/apm-rum@5.12.0/dist/bundles/elastic-apm-rum.umd.min.js" crossOrigin="true" />
            <script dangerouslySetInnerHTML={{ __html: htmlStr }} />
        </>
    ) : (
        <></>
    );
}
export default MyDocument;
