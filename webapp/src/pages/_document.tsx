import Document, { DocumentContext, DocumentInitialProps, Head, Html, Main, NextScript } from 'next/document';

class MyDocument extends Document {
    static async getInitialProps(ctx: DocumentContext): Promise<DocumentInitialProps> {
        return Document.getInitialProps(ctx);
    }

    render() {
        return (
            <Html lang="en-US" dir="ltr" className="light">
                <Head>
                    {this.props.styles}
                    <script src="https://unpkg.com/@elastic/apm-rum@5.12.0/dist/bundles/elastic-apm-rum.umd.min.js" crossOrigin="true" />
                    <script
                        dangerouslySetInnerHTML={{
                            __html: `
                    elasticApm.init({
                        serviceName: 'FormIntegrator',
                        serverUrl: 'https://apm.sireto.io',
                    })
                    `
                        }}
                    />
                </Head>

                <body>
                    <Main />
                    <NextScript />
                </body>
            </Html>
        );
    }
}

export default MyDocument;
