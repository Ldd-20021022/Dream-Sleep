const app = getApp();

Page({
  data: {
    isRegister: false, username: '', password: '', showPwd: false, error: '', loading: false, serverUrl: '', lockCountdown: 0,
    regUser: '', regEmail: '', regPwd: '', regNick: '', showPwdReg: false, regErr: '', regLoading: false, regValid: false, pwStrength: 0,
  },

  onLoad() {
    this.setData({ serverUrl: app.globalData.apiBase });
  },

  // Login
  setUname(e) { this.setData({ username: e.detail.value, error: '' }); },
  setPwd(e) { this.setData({ password: e.detail.value, error: '' }); },
  togglePwd() { this.setData({ showPwd: !this.data.showPwd }); },
  switchToRegister() { this.setData({ isRegister: true, error: '' }); },
  switchToLogin() { this.setData({ isRegister: false, regErr: '' }); },

  async handleLogin() {
    const { username, password, lockCountdown } = this.data;
    if (!username || !password) { this.setData({ error: '请输入用户名和密码' }); return; }
    if (lockCountdown > 0) return;
    this.setData({ loading: true, error: '' });
    try {
      await app.login(username, password);
      wx.switchTab({ url: '/pages/index/index' });
    } catch (e) {
      let msg = e.message || '登录失败';
      if (msg.includes('网络') || msg.includes('timeout') || msg.includes('fail')) {
        msg = '网络错误 — 请确认:\n1. 电脑已启动服务器\n2. 手机与电脑同一WiFi\n3. app.js中DEV_HOST是电脑IP';
      }
      this.setData({ error: msg });
      if (msg.includes('用户名或密码错误') || msg.includes('401')) {
        const fails = (wx.getStorageSync('login_fails') || 0) + 1;
        wx.setStorageSync('login_fails', fails);
        if (fails >= 5) {
          let cd = 60;
          this.setData({ lockCountdown: cd });
          const iv = setInterval(() => { cd--; this.setData({ lockCountdown: cd }); if (cd <= 0) { clearInterval(iv); wx.setStorageSync('login_fails', 0); } }, 1000);
        }
      }
    }
    this.setData({ loading: false });
  },

  // Register
  setRegUser(e) { this.setData({ regUser: e.detail.value, regErr: '' }); this.checkReg(); },
  setRegEmail(e) { this.setData({ regEmail: e.detail.value, regErr: '' }); this.checkReg(); },
  setRegPwd(e) { this.setData({ regPwd: e.detail.value, regErr: '' }); this.checkReg(); },
  setRegNick(e) { this.setData({ regNick: e.detail.value }); },
  togglePwdReg() { this.setData({ showPwdReg: !this.data.showPwdReg }); },

  checkReg() {
    const { regUser, regEmail, regPwd } = this.data;
    const valid = regUser.length >= 2 && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(regEmail) && regPwd.length >= 6 && /[a-zA-Z]/.test(regPwd) && /[0-9]/.test(regPwd);
    let s = 0;
    if (regPwd.length >= 8) s++; if (regPwd.length >= 12) s++; if (/[a-z]/.test(regPwd) && /[A-Z]/.test(regPwd)) s++; if (/[^a-zA-Z0-9]/.test(regPwd)) s++;
    this.setData({ regValid: valid, pwStrength: Math.min(s, 4) });
  },

  async handleRegister() {
    const { regUser, regEmail, regPwd, regNick } = this.data;
    if (!this.data.regValid) return;
    this.setData({ regLoading: true, regErr: '' });
    try {
      const reqBody = { username: regUser, email: regEmail, password: regPwd, nickname: regNick || regUser };
      await app.request('POST', '/api/v1/auth/register', reqBody, false);
      await app.login(regUser, regPwd);
      wx.switchTab({ url: '/pages/index/index' });
    } catch (e) {
      this.setData({ regErr: e.message || '注册失败' });
    }
    this.setData({ regLoading: false });
  },
});
