/**
 * 梦眠 - AI智能睡眠管理 微信小程序
 * API 连接到 FastAPI 后端:
 */
// 开发: 真机用局域网IP, 模拟器用127.0.0.1
const DEV_HOST = 'http://192.168.3.64:8000';
// 生产: 替换为你的 HTTPS 域名
const PROD_HOST = 'https://your-domain.com';
const USE_PROD = false;

App({
  globalData: {
    apiBase: USE_PROD ? PROD_HOST : DEV_HOST,
    token: '',
    refreshToken: '',
    userInfo: null,
  },

  onLaunch() {
    const token = wx.getStorageSync('access_token');
    if (token) {
      this.globalData.token = token;
      this.globalData.refreshToken = wx.getStorageSync('refresh_token') || '';
    }
  },

  request(method, path, data = {}, needAuth = true) {
    return new Promise((resolve, reject) => {
      const header = { 'Content-Type': 'application/json' };
      if (needAuth && this.globalData.token) {
        header['Authorization'] = 'Bearer ' + this.globalData.token;
      }
      wx.request({
        url: this.globalData.apiBase + path,
        method: method,
        data: method === 'GET' ? undefined : data,
        header: header,
        success: (res) => {
          if (res.statusCode === 401 && this.globalData.refreshToken) {
            this.refreshToken().then(() => {
              this.request(method, path, data, needAuth).then(resolve).catch(reject);
            }).catch(() => {
              this.logout();
              reject(new Error('登录已过期'));
            });
            return;
          }
          if (res.statusCode >= 400) {
            reject(new Error(res.data?.detail || res.data?.error || '请求失败(' + res.statusCode + ')'));
            return;
          }
          resolve(res.data);
        },
        fail: (err) => {
          reject(new Error('网络错误: ' + (err.errMsg || '无法连接服务器')));
        },
      });
    });
  },

  // GET 请求
  get(path, needAuth = true) {
    return this.request('GET', path, {}, needAuth);
  },

  // POST 请求
  post(path, data, needAuth = true) {
    return this.request('POST', path, data, needAuth);
  },

  // PUT 请求
  put(path, data, needAuth = true) {
    return this.request('PUT', path, data, needAuth);
  },

  // DELETE 请求
  del(path, data, needAuth = true) {
    return this.request('DELETE', path, data, needAuth);
  },

  // 刷新 Token
  async refreshToken() {
    const res = await this.post('/api/v1/auth/refresh', {
      refresh_token: this.globalData.refreshToken,
    }, false);
    this.globalData.token = res.access_token;
    wx.setStorageSync('access_token', res.access_token);
    return res;
  },

  // 检查登录状态
  async checkLogin() {
    try {
      const user = await this.get('/api/v1/auth/me');
      this.globalData.userInfo = user;
      wx.setStorageSync('userInfo', user);
    } catch {
      this.logout();
    }
  },

  // 登录
  async login(username, password) {
    const res = await this.post('/api/v1/auth/login', { username, password }, false);
    this.globalData.token = res.access_token;
    this.globalData.refreshToken = res.refresh_token;
    wx.setStorageSync('access_token', res.access_token);
    wx.setStorageSync('refresh_token', res.refresh_token);
    await this.checkLogin();
    return this.globalData.userInfo;
  },

  // 退出
  logout() {
    this.globalData.token = '';
    this.globalData.refreshToken = '';
    this.globalData.userInfo = null;
    wx.removeStorageSync('access_token');
    wx.removeStorageSync('refresh_token');
    wx.removeStorageSync('userInfo');
  },
});
