/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 14:40
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import getConfig from 'next/config';

const config = getConfig();
let publicRuntimeConfig: any = {};
if (config && config.publicRuntimeConfig) {
    publicRuntimeConfig = config.publicRuntimeConfig;
}

const IS_IN_PRODUCTION_MODE = publicRuntimeConfig.NEXT_PUBLIC_NODE_ENV === 'production';
const BASE_DEPLOY_PATH = process.env.BASE_DEPLOY_PATH ?? '';

console.log('environments: ', publicRuntimeConfig.API_ENDPOINT_HOST);

const environments = {
    // build-time configs
    BASE_DEPLOY_PATH,

    // api host configs
    API_ENDPOINT_HOST: publicRuntimeConfig.API_ENDPOINT_HOST,

    // run-time configs
    CONTACT_US_URL: publicRuntimeConfig.CONTACT_US_URL,
    GA_MEASUREMENT_ID: publicRuntimeConfig.GA_MEASUREMENT_ID,
    WAITLIST_FORM_URL: publicRuntimeConfig.WAITLIST_FORM_URL,
    INDIVIDUAL_FORM_URL: publicRuntimeConfig.INDIVIDUAL_FORM_URL,
    BUSINESS_FORM_URL: publicRuntimeConfig.BUSINESS_FORM_URL,
    ENTERPRISE_FORM_URL: publicRuntimeConfig.ENTERPRISE_FORM_URL,

    // Custom Domain Variables (run-time configs)
    IS_CUSTOM_DOMAIN: (publicRuntimeConfig.IS_CUSTOM_DOMAIN && (publicRuntimeConfig.IS_CUSTOM_DOMAIN === 'true' || publicRuntimeConfig.IS_CUSTOM_DOMAIN === true)) ?? false,
    CUSTOM_DOMAIN: publicRuntimeConfig.CUSTOM_DOMAIN,
    CUSTOM_DOMAIN_JSON: publicRuntimeConfig.CUSTOM_DOMAIN_JSON,
    ENABLE_CHECK_MY_DATA: (publicRuntimeConfig.ENABLE_CHECK_MY_DATA && (publicRuntimeConfig.ENABLE_CHECK_MY_DATA === 'true' || publicRuntimeConfig.ENABLE_CHECK_MY_DATA === true)) ?? false,

    // internal configs
    IS_IN_PRODUCTION_MODE,
    TERMS_AND_CONDITIONS: `${BASE_DEPLOY_PATH}/legal/terms-and-conditions-2022.pdf`,
    PRIVACY_POLICY: `${BASE_DEPLOY_PATH}/legal/privacy-policy-2022.pdf`
};

export default environments;
