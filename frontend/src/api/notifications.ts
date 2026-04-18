import { api } from './client';

export type Channel = 'email' | 'sms' | 'push';
export type Severity = 'INFO' | 'WARNING' | 'CRITICAL' | 'EVACUATION';

export interface Subscription {
  id: string;
  user_id: string;
  site_id: string;
  channel: Channel;
  min_severity: Severity;
  active: boolean;
  created_at: string;
}

export interface SubscriberRow {
  user_id: string;
  user_email: string;
  user_name: string;
  site_id: string;
  channel: Channel;
  min_severity: Severity;
  active: boolean;
}

export interface ProfileOut {
  id: string;
  name: string;
  email: string;
  phone_number: string | null;
  role: string;
}

export function listMySubscriptions(): Promise<Subscription[]> {
  return api.get<Subscription[]>('/subscriptions');
}

export function upsertSubscription(
  site_id: string,
  channel: Channel,
  min_severity: Severity,
  active: boolean,
): Promise<Subscription> {
  return api.put<Subscription>('/subscriptions', {
    site_id,
    channel,
    min_severity,
    active,
  });
}

export function deleteSubscription(id: string): Promise<void> {
  return api.del<void>(`/subscriptions/${id}`);
}

export function sendTestAlert(
  site_id: string,
  channel: Channel,
  message?: string,
): Promise<{ accepted: boolean; channel: Channel }> {
  return api.post<{ accepted: boolean; channel: Channel }>('/subscriptions/test', {
    site_id,
    channel,
    ...(message ? { message } : {}),
  });
}

export function updateProfile(body: {
  name?: string;
  phone_number?: string | null;
}): Promise<ProfileOut> {
  return api.patch<ProfileOut>('/profile', body);
}

export function listSubscribers(): Promise<SubscriberRow[]> {
  return api.get<SubscriberRow[]>('/admin/subscribers');
}
