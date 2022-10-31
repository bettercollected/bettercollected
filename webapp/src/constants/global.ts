/**
 * Created By: Rupan Chaulagain
 * Date: 2022-10-11
 * Time: 14:33
 * Project: formintegratorwebapp
 * Organization: Sireto Technology
 */
import environments from '@app/configs/environments';

// import environments from '@app/configs/environments';

const globalConstants = {
    appName: 'Better Collected',
    appDesc: 'Better collected.',
    title: 'Better Collected',
    favIcon: 'favIcon',
    twitterHandle: '',
    titleImg: 'titleImg',
    socialPreview: {
        url: `https://bettercollected.io/${environments.BASE_DEPLOY_PATH}`,
        title: 'BetterCollected.',
        desc: 'Better Collected',
        image: 'imageUrl'
    },
    consoleWarningTitle: `%cStop!`,
    consoleWarningDescription: `%cThis is a browser feature intended for developers. If someone told you to copy-paste something here to enable a feature, it is a scam and will give them access to your sensitive information.`,

    videoTypes: ['video/H261', 'video/H263', 'video/H264', 'video/H265', 'video/mp4', 'video/ogg', 'video/quicktime', 'video/mov', 'video/x-msvideo', 'video/x-ms-wmv'],
    imageTypes: ['image/jpg', 'image/jpeg', 'image/png', 'image/gif', 'image/svg+xml'],
    modelTypes: ['model/gltf-binary', 'model/gltf+json', '.glb'],
    audioTypes: ['audio/mpeg', 'audio/mp3', 'audio/mp4', 'audio/ogg']
};

export default globalConstants;
