/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 14:40
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */

import getConfig from "next/config";

const config = getConfig();

let publicRuntimeConfig: any = {};

if (config && config.publicRuntimeConfig) {
  publicRuntimeConfig = config.publicRuntimeConfig;
}

const IS_IN_PRODUCTION_MODE =
  publicRuntimeConfig.NEXT_PUBLIC_NODE_ENV === "production";

const environments = {
  //build-time configs
  BASE_DEPLOY_PATH: process.env.BASE_DEPLOY_PATH ?? "",
  COMPANY_NAME: process.env.COMPANY_NAME ?? "Better Collected",
  GA_MEASUREMENT_ID: process.env.NEXT_PUBLIC_GA_MEASUREMENT_ID ?? "",
  WAILIST_URL: process.env.NEXT_PUBLIC_WAITLIST_FORM_URL,
  CONTACT_US_URL: process.env.NEXT_PUBLIC_CONTACT_US_URL,
  INDIVIDUAL_PLAN_FORM_URL: process.env.NEXT_PUBLIC_INDIVIDUAL_FORM,
  BUSINESS_PLAN_FORM_URL: process.env.NEXT_PUBLIC_BUSINESS_FORM,
  ENTERPRISE_PLAN_FORM_URL: process.env.NEXT_PUBLIC_ENTERPRISE_FORM,
  //internal configs
  IS_IN_PRODUCTION_MODE,
};

export default environments;
