import { GoogleFormDto } from './googleForm';

export interface CompanyJsonDto {
    companyBanner: string;
    companyProfile: string;
    companyTitle: string;
    companyDescription: string;
    companyDomain: string;
    forms: Array<GoogleFormDto>;
}
