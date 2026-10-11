import { api } from './client';

export interface CommunityOptInRequest {
  phone_number: string;
  site_id: string;
}

export interface CommunityOptInResponse {
  phone_number: string;
  site_id: string;
  expires_at: string;
  debug_code: string | null;
}

export interface CommunityConfirmRequest {
  phone_number: string;
  site_id: string;
  code: string;
}

export interface CommunityConfirmResponse {
  user_id: string;
  subscription_id: string;
}

export async function subscribeCommunity(
  body: CommunityOptInRequest,
): Promise<CommunityOptInResponse> {
  return api.post('/community/subscribe', body);
}

export async function confirmCommunity(
  body: CommunityConfirmRequest,
): Promise<CommunityConfirmResponse> {
  return api.post('/community/confirm', body);
}
