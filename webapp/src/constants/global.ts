/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 14:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import environments from '@app/configs/environments';

const globalConstants = {
    appName: 'Better Collected',
    appDesc:
        'If you use any form solutions like Google Forms or Typeform then Better Collected is a right platform for addressing the data rights of your form respondents. Better Collected integrates with those form solutions and opens up a portal for your users to view all of their data collected using forms and let them exercise the data rights like request for data deletion. This all happens without disrupting your normal workflow how you use the existing form solution. Better collected makes you a better data collector and help you prevent GDPR and CCPA fines.',
    title: environments.METATAG_TITLE || 'Better Collected',
    favIcon: 'favIcon',
    twitterHandle: '@BetterCollected',
    titleImg: 'titleImg',
    socialPreview: {
        url: `https://bettercollected.io/${environments.BASE_DEPLOY_PATH}`,
        title: environments.METATAG_TITLE || 'BetterCollected.',
        desc:
            environments.METATAG_DESCRIPTION ||
            'If you use any form solutions like Google Forms or Typeform then Better Collected is a right platform for addressing the data rights of your form respondents. Better Collected integrates with those form solutions and opens up a portal for your users to view all of their data collected using forms and let them exercise the data rights like request for data deletion. This all happens without disrupting your normal workflow how you use the existing form solution. Better collected makes you a better data collector and help you prevent GDPR and CCPA fines.',
        image: environments.METATAG_IMAGE || 'https://s3.eu-central-1.wasabisys.com/bettercollected/public/better-collected-social.png'
    },
    consoleWarningTitle: `%cStop!`,
    consoleWarningDescription: `%cThis is a browser feature intended for developers. If someone told you to copy-paste something here to enable a feature, it is a scam and will give them access to your sensitive information.`,

    videoTypes: ['video/H261', 'video/H263', 'video/H264', 'video/H265', 'video/mp4', 'video/ogg', 'video/quicktime', 'video/mov', 'video/x-msvideo', 'video/x-ms-wmv'],
    imageTypes: ['image/jpg', 'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml'],
    modelTypes: ['model/gltf-binary', 'model/gltf+json', '.glb'],
    audioTypes: ['audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/ogg']
};

export default globalConstants;
