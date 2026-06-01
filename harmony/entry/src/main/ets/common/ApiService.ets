// 梦眠阁 — API 服务 (HarmonyOS)
import http from '@ohos.net.http';
import { API_BASE } from './Constants';

export class ApiService {
  private token: string = '';

  setToken(t: string) { this.token = t; }

  private async request(method: http.RequestMethod, path: string, data?: object): Promise<object> {
    const req = http.createHttp();
    const opts: http.HttpRequestOptions = {
      method: method,
      header: {
        'Content-Type': 'application/json',
        'Authorization': this.token ? `Bearer ${this.token}` : '',
      },
      extraData: data,
      connectTimeout: 30000,
      readTimeout: 30000,
    };
    try {
      const resp = await req.request(`${API_BASE}${path}`, opts);
      req.destroy();
      if (resp.responseCode === 200) return JSON.parse(resp.result as string);
      throw new Error(`${resp.responseCode}`);
    } catch (e) {
      req.destroy();
      throw e;
    }
  }

  get(path: string): Promise<object> { return this.request(http.RequestMethod.GET, path); }
  post(path: string, data?: object): Promise<object> { return this.request(http.RequestMethod.POST, path, data); }
  put(path: string, data?: object): Promise<object> { return this.request(http.RequestMethod.PUT, path, data); }
  del(path: string): Promise<object> { return this.request(http.RequestMethod.DELETE, path); }
}
